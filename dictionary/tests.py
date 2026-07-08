import json
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.utils import timezone

from .models import Category, Word


class LearningApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="azim", password="pass-12345")
        self.other = User.objects.create_user(username="other", password="pass-12345")
        self.client = Client()
        self.client.login(username="azim", password="pass-12345")

    def create_word(self, **kwargs):
        defaults = {
            "user": self.user,
            "term": "apple",
            "translation": "яблоко",
            "example": "I ate an apple.",
            "pos": "noun",
        }
        defaults.update(kwargs)
        return Word.objects.create(**defaults)

    def post_json(self, path, payload):
        return self.client.post(path, data=json.dumps(payload), content_type="application/json")

    def test_review_scheduling_for_all_grades(self):
        for grade in ["forgot", "hard", "good", "easy"]:
            word = self.create_word(term=f"word-{grade}", review_due_at=timezone.now())
            response = self.post_json(f"/api/review/{word.id}/answer/", {"grade": grade})
            self.assertEqual(response.status_code, 200)
            word.refresh_from_db()
            self.assertEqual(word.review_count, 1)
            self.assertIsNotNone(word.review_due_at)
            self.assertGreaterEqual(word.review_interval_days, 1)

    def test_review_due_is_user_scoped(self):
        mine = self.create_word(term="mine", review_due_at=timezone.now())
        Word.objects.create(user=self.other, term="other", translation="другой", review_due_at=timezone.now())

        response = self.client.get("/api/review/due/")
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()["words"]]
        self.assertIn(mine.id, ids)
        self.assertEqual(len(ids), 1)

    @patch("dictionary.api.groq_chat_json")
    def test_bulk_import_creates_and_skips_duplicates(self, mock_groq):
        self.create_word(term="apple")
        mock_groq.return_value = {
            "items": [
                {"word": "run", "translation": "бежать", "pos": "verb", "example": "I run daily."},
                {"word": "beautiful", "translation": "красивый", "pos": "adj", "example": "A beautiful day."},
            ]
        }

        response = self.post_json("/api/words/bulk-ai/", {"words": "apple\nrun\nbeautiful"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["created"]), 2)
        self.assertEqual(data["skipped"], ["apple"])
        self.assertTrue(Word.objects.filter(user=self.user, term="run").exists())

    def test_word_create_truncates_long_translation(self):
        long_translation = "а" * 300
        response = self.post_json(
            "/api/words/add/",
            {"word": "men", "ru": long_translation, "example": None, "category_id": None},
        )
        self.assertEqual(response.status_code, 201)
        word = Word.objects.get(user=self.user, term="men")
        self.assertEqual(len(word.translation), 255)

    def test_word_create_rejects_invalid_category(self):
        other_category = Category.objects.create(user=self.other, name="Other category")
        response = self.post_json("/api/words/add/", {"word": "men", "ru": "мужчины", "category_id": other_category.id})
        self.assertEqual(response.status_code, 400)

    def test_profile_requires_login(self):
        self.client.logout()
        response = self.client.get("/profile/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_profile_updates_username(self):
        response = self.client.post("/profile/", {"form_type": "username", "username": "newazim"})
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "newazim")

    def test_profile_rejects_duplicate_username(self):
        response = self.client.post("/profile/", {"form_type": "username", "username": "other"})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "azim")
        self.assertContains(response, "Это имя уже занято.")

    def test_profile_changes_password_and_keeps_session(self):
        response = self.client.post(
            "/profile/",
            {
                "form_type": "password",
                "old_password": "pass-12345",
                "new_password1": "fresh-pass-67890",
                "new_password2": "fresh-pass-67890",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.client.get("/profile/").wsgi_request.user.is_authenticated)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("fresh-pass-67890"))

    @patch("dictionary.api.get_groq_key", return_value=None)
    def test_word_suggestions_are_user_scoped(self, _mock_key):
        self.create_word(term="apple")
        self.create_word(term="application")
        Word.objects.create(user=self.other, term="apricot", translation="абрикос")

        response = self.client.get("/api/word-suggestions/?q=app")

        self.assertEqual(response.status_code, 200)
        suggestions = response.json()["suggestions"]
        self.assertEqual([item["word"] for item in suggestions], ["apple", "application"])
        self.assertTrue(all(item["source"] == "saved" for item in suggestions))
        self.assertEqual([item["pos"] for item in suggestions], ["noun", "noun"])

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"})
    @patch("dictionary.api.groq_chat_json")
    def test_word_suggestions_add_ai_completions(self, mock_groq):
        self.create_word(term="apple")
        mock_groq.return_value = {
            "suggestions": [
                {"word": "apple", "pos": "noun"},
                {"word": "application", "pos": "noun"},
                {"word": "app store", "pos": "phrase"},
                {"word": "banana", "pos": "noun"},
                {"word": "app\nbad", "pos": "other"},
            ]
        }

        response = self.client.get("/api/word-suggestions/?q=app")

        self.assertEqual(response.status_code, 200)
        suggestions = response.json()["suggestions"]
        self.assertEqual([item["word"] for item in suggestions], ["apple", "application", "app store"])
        self.assertEqual([item["source"] for item in suggestions], ["saved", "ai", "ai"])
        self.assertEqual([item["pos"] for item in suggestions], ["noun", "noun", "phrase"])

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"})
    @patch("dictionary.api.groq_chat_json")
    def test_word_suggestions_can_return_spelling_fixes(self, mock_groq):
        mock_groq.return_value = {
            "suggestions": [
                {"word": "apple", "pos": "noun"},
                {"word": "apply", "pos": "verb"},
            ]
        }

        response = self.client.get("/api/word-suggestions/?q=applr")

        self.assertEqual(response.status_code, 200)
        suggestions = response.json()["suggestions"]
        self.assertEqual([item["word"] for item in suggestions], ["apple", "apply"])
        self.assertEqual([item["source"] for item in suggestions], ["fix", "fix"])
        self.assertEqual([item["pos"] for item in suggestions], ["noun", "verb"])

    @patch("dictionary.api.groq_chat_json")
    def test_ai_lookup_rejects_misspelled_word_with_correction(self, mock_groq):
        mock_groq.return_value = {
            "is_valid": False,
            "correction": "apple",
            "translation": "",
            "pos": "noun",
            "example": "",
        }

        response = self.post_json("/api/ai-lookup/", {"word": "applr"})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["correction"], "apple")
        self.assertEqual(response.json()["pos"], "noun")
        self.assertEqual(response.json()["suggestions"], [{"word": "apple", "source": "fix", "pos": "noun"}])

    def test_quiz_generation_is_user_scoped(self):
        for idx in range(5):
            self.create_word(term=f"mine-{idx}", translation=f"перевод-{idx}")
        Word.objects.create(user=self.other, term="secret", translation="секрет")

        response = self.post_json("/api/quiz/generate/", {"count": 5, "difficulty": "hard"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["difficulty"], "hard")
        self.assertEqual(data["count"], 5)
        word_ids = {item["word_id"] for item in data["questions"]}
        self.assertTrue(word_ids)
        self.assertFalse(Word.objects.filter(user=self.other, id__in=word_ids).exists())

    def test_quiz_submit_updates_weak_stats(self):
        word = self.create_word(term="run", translation="бежать")
        response = self.post_json(
            "/api/quiz/submit/",
            {
                "answers": [
                    {
                        "word_id": word.id,
                        "type": "multiple_choice",
                        "prompt": "Choose the translation for run",
                        "expected": "бежать",
                        "answer": "wrong",
                    }
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual(result["word"], "run")
        self.assertEqual(result["prompt"], "Choose the translation for run")
        self.assertEqual(result["expected"], "бежать")
        self.assertEqual(result["answer"], "wrong")
        self.assertFalse(result["correct"])
        word.refresh_from_db()
        self.assertEqual(word.quiz_wrong_count, 1)

    def test_pronunciation_rejects_missing_and_large_audio(self):
        word = self.create_word(term="hello")
        missing = self.client.post("/api/pronunciation/check/", data={"word_id": word.id})
        self.assertEqual(missing.status_code, 400)

        large_file = SimpleUploadedFile("big.webm", b"x" * (4 * 1024 * 1024 + 1), content_type="audio/webm")
        large = self.client.post("/api/pronunciation/check/", data={"word_id": word.id, "audio": large_file})
        self.assertEqual(large.status_code, 400)

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"})
    @patch("dictionary.api.requests.post")
    def test_pronunciation_success_uses_mocked_groq(self, mock_post):
        word = self.create_word(term="hello")
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"text": "hello"}
        mock_post.return_value = mock_response
        audio = SimpleUploadedFile("speech.webm", b"audio", content_type="audio/webm")

        response = self.client.post("/api/pronunciation/check/", data={"word_id": word.id, "audio": audio})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "correct")
