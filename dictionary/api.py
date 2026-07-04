import json
import os
import random
import re
from datetime import timedelta

import requests
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from .models import Word, Category


GROQ_CHAT_MODEL = "llama-3.3-70b-versatile"
GROQ_TTS_MODEL = "canopylabs/orpheus-v1-english"
GROQ_STT_MODEL = "whisper-large-v3-turbo"
GROQ_TTS_VOICE = "hannah"
GROQ_TTS_MAX_CHARS = 200
GROQ_API_BASE = "https://api.groq.com/openai/v1"
BULK_IMPORT_LIMIT = 30
QUIZ_MIN_WORDS = 5


def get_groq_key():
    return os.environ.get("GROQ_API_KEY")


def normalize_pos(pos):
    aliases = {
        "noun": "noun",
        "verb": "verb",
        "adj": "adj",
        "adjective": "adj",
        "adv": "adv",
        "adverb": "adv",
        "phrase": "phrase",
        "expression": "phrase",
        "phrasal verb": "phrase",
        "other": "other",
        "interjection": "other",
    }
    return aliases.get(str(pos or "").lower().strip(), "other")


def normalize_text(value):
    return re.sub(r"[^\w]+", " ", str(value or "").lower(), flags=re.UNICODE).strip()


def word_to_dict(word):
    return {
        "id": word.id,
        "word": word.term,
        "translation": word.translation,
        "example": word.example,
        "pos": word.pos,
        "learned": word.is_learned,
        "category_id": word.category_id,
        "review_due_at": word.review_due_at.isoformat() if word.review_due_at else None,
        "review_interval_days": word.review_interval_days,
        "review_ease": word.review_ease,
        "review_count": word.review_count,
        "lapse_count": word.lapse_count,
        "quiz_correct_count": word.quiz_correct_count,
        "quiz_wrong_count": word.quiz_wrong_count,
        "is_difficult": word.is_difficult,
    }


def strip_json_markdown(content):
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines)
    return content


def groq_chat_json(prompt, system_content, timeout=25):
    groq_key = get_groq_key()
    if not groq_key:
        raise RuntimeError("Server config missing: GROQ_API_KEY")

    response = requests.post(
        f"{GROQ_API_BASE}/chat/completions",
        json={
            "model": GROQ_CHAT_MODEL,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
        },
        headers={
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json",
        },
        timeout=timeout,
    )
    if response.status_code != 200:
        raise RuntimeError("AI provider error")
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(strip_json_markdown(content))


def schedule_review(word, grade):
    now = timezone.now()
    previous_interval = max(word.review_interval_days, 0)
    ease = max(word.review_ease or 2.5, 1.3)

    if grade == "forgot":
        next_interval = 1
        ease = max(1.3, ease - 0.2)
        word.lapse_count += 1
        word.is_learned = False
    elif grade == "hard":
        next_interval = max(1, round(previous_interval * 1.2) if previous_interval else 1)
        ease = max(1.3, ease - 0.15)
        word.is_learned = False
    elif grade == "good":
        next_interval = 2 if previous_interval == 0 else max(2, round(previous_interval * ease))
        word.is_learned = True
    elif grade == "easy":
        next_interval = 4 if previous_interval == 0 else max(4, round(previous_interval * (ease + 0.5)))
        ease = min(3.2, ease + 0.15)
        word.is_learned = True
    else:
        raise ValueError("Invalid review grade")

    word.review_interval_days = next_interval
    word.review_ease = round(ease, 2)
    word.review_count += 1
    word.last_reviewed_at = now
    word.review_due_at = now + timedelta(days=next_interval)
    word.is_difficult = word.lapse_count + word.quiz_wrong_count > word.quiz_correct_count + 1
    word.save()
    return word


@login_required
@require_http_methods(["GET"])
def api_categories_list(request):
    categories = Category.objects.filter(user=request.user)
    data = [{"id": c.id, "name": c.name} for c in categories]
    return JsonResponse({"categories": data})


@login_required
@require_http_methods(["POST"])
def api_category_create(request):
    try:
        data = json.loads(request.body)
        name = data.get("name", "").strip()
        if not name:
            return JsonResponse({"error": "Name required"}, status=400)

        cat = Category.objects.create(user=request.user, name=name)
        return JsonResponse({"id": cat.id, "name": cat.name})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_category_delete(request, pk):
    try:
        cat = Category.objects.get(pk=pk, user=request.user)
        cat.delete()
        return JsonResponse({"status": "success"})
    except Category.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)


@login_required
@require_http_methods(["GET"])
def api_words_list(request):
    words = Word.objects.filter(user=request.user).order_by("-created_at")
    return JsonResponse({"words": [word_to_dict(w) for w in words]})


@login_required
@require_http_methods(["POST"])
def api_word_create(request):
    try:
        data = json.loads(request.body)
        term = data.get("word", "").strip()
        translation = data.get("ru", "").strip()

        if not term:
            return JsonResponse({"error": "Word is required"}, status=400)

        new_word = Word.objects.create(
            user=request.user,
            term=term,
            translation=translation,
            example=data.get("example", ""),
            pos=normalize_pos(data.get("pos", "other")),
            is_learned=False,
            category_id=data.get("category_id") or None,
        )
        payload = word_to_dict(new_word)
        payload["status"] = "success"
        return JsonResponse(payload, status=201)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


@login_required
@require_http_methods(["POST"])
def api_word_update(request, pk):
    try:
        word = Word.objects.get(pk=pk, user=request.user)
        data = json.loads(request.body)

        if "learned" in data:
            word.is_learned = data["learned"]
        if "word" in data:
            word.term = data["word"]
        if "example" in data:
            word.example = data["example"]
        if "ru" in data:
            word.translation = data["ru"]
        if "pos" in data:
            word.pos = normalize_pos(data["pos"])

        word.save()
        return JsonResponse({"status": "success"})
    except Word.DoesNotExist:
        return JsonResponse({"error": "Word not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["DELETE"])
def api_word_delete(request, pk):
    try:
        word = Word.objects.get(pk=pk, user=request.user)
        word.delete()
        return JsonResponse({"status": "success"})
    except Word.DoesNotExist:
        return JsonResponse({"error": "Word not found"}, status=404)


@login_required
@require_http_methods(["POST"])
def api_ai_lookup(request):
    try:
        data = json.loads(request.body)
        word = data.get("word", "").strip()

        if not word:
            return JsonResponse({"error": "Word is required"}, status=400)

        prompt = (
            f"Translate and explain the English word or phrase: {word!r}.\n"
            "Target learner language: Russian.\n"
            "Return JSON ONLY with these keys:\n"
            "- \"translation\": Russian translation, with 2-3 common meanings if useful, comma separated.\n"
            "- \"pos\": exactly one of: noun, verb, adj, adv, phrase, other.\n"
            "- \"example\": one short natural English sentence using the word.\n"
            "Do not include markdown, comments, citations, or backticks."
        )
        result = groq_chat_json(
            prompt,
            (
                "You are a precise dictionary API for Russian-speaking English learners. "
                "Return a single raw JSON object only."
            ),
            timeout=12,
        )
        result["pos"] = normalize_pos(result.get("pos"))
        return JsonResponse(result)
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=500)
    except json.JSONDecodeError:
        return JsonResponse({"error": "AI Parse Error: Invalid JSON received"}, status=500)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_tts(request):
    try:
        data = json.loads(request.body)
        text = data.get("text", "").strip()

        if not text:
            return JsonResponse({"error": "Text is required"}, status=400)
        if len(text) > GROQ_TTS_MAX_CHARS:
            return JsonResponse({"error": f"Text must be {GROQ_TTS_MAX_CHARS} characters or fewer"}, status=400)

        groq_key = get_groq_key()
        if not groq_key:
            return JsonResponse({"error": "Server config missing: GROQ_API_KEY"}, status=500)

        response = requests.post(
            f"{GROQ_API_BASE}/audio/speech",
            json={
                "model": GROQ_TTS_MODEL,
                "voice": GROQ_TTS_VOICE,
                "input": text,
                "response_format": "wav",
            },
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        if response.status_code != 200:
            return JsonResponse({"error": "TTS provider error"}, status=500)

        audio = HttpResponse(response.content, content_type="audio/wav")
        audio["Cache-Control"] = "private, max-age=86400"
        audio["Content-Disposition"] = 'inline; filename="word.wav"'
        return audio
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except requests.RequestException:
        return JsonResponse({"error": "TTS provider unavailable"}, status=502)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def api_review_due(request):
    now = timezone.now()
    limit = min(max(int(request.GET.get("limit", 20)), 1), 50)

    new_words = list(
        Word.objects.filter(user=request.user, review_due_at__isnull=True).order_by("created_at")[:limit]
    )
    remaining = max(limit - len(new_words), 0)
    due_words = []
    if remaining:
        due_words = list(
            Word.objects.filter(user=request.user, review_due_at__lte=now).order_by("review_due_at")[:remaining]
        )

    words = new_words + due_words
    return JsonResponse({"words": [word_to_dict(w) for w in words], "count": len(words)})


@login_required
@require_http_methods(["POST"])
def api_review_answer(request, pk):
    try:
        data = json.loads(request.body)
        word = Word.objects.get(pk=pk, user=request.user)
        schedule_review(word, data.get("grade"))
        return JsonResponse({"word": word_to_dict(word), "status": "success"})
    except Word.DoesNotExist:
        return JsonResponse({"error": "Word not found"}, status=404)
    except ValueError:
        return JsonResponse({"error": "Invalid review grade"}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


@login_required
@require_http_methods(["POST"])
def api_words_bulk_ai(request):
    try:
        data = json.loads(request.body)
        raw_lines = data.get("words", [])
        if isinstance(raw_lines, str):
            raw_lines = raw_lines.splitlines()

        terms = []
        seen = set()
        for line in raw_lines:
            term = str(line).strip()
            key = term.lower()
            if term and key not in seen:
                terms.append(term[:255])
                seen.add(key)

        if not terms:
            return JsonResponse({"error": "No words provided"}, status=400)
        if len(terms) > BULK_IMPORT_LIMIT:
            return JsonResponse({"error": f"Maximum {BULK_IMPORT_LIMIT} words per import"}, status=400)

        skipped = []
        import_terms = []
        for term in terms:
            if Word.objects.filter(user=request.user, term__iexact=term).exists():
                skipped.append(term)
            else:
                import_terms.append(term)

        created = []
        failed = []
        if import_terms:
            prompt = (
                "Create dictionary entries for these English words or phrases for Russian-speaking learners.\n"
                "Return JSON only in this shape: "
                "{\"items\":[{\"word\":\"...\",\"translation\":\"...\",\"pos\":\"noun|verb|adj|adv|phrase|other\",\"example\":\"...\"}]}.\n"
                f"Words: {json.dumps(import_terms, ensure_ascii=False)}"
            )
            result = groq_chat_json(prompt, "You are a precise dictionary API. Return raw JSON only.")
            items = result.get("items", [])
            by_term = {str(item.get("word", "")).strip().lower(): item for item in items}

            for term in import_terms:
                item = by_term.get(term.lower())
                if not item:
                    failed.append(term)
                    continue
                word = Word.objects.create(
                    user=request.user,
                    term=term,
                    translation=str(item.get("translation", "")).strip()[:255],
                    example=str(item.get("example", "")).strip(),
                    pos=normalize_pos(item.get("pos")),
                    category_id=data.get("category_id") or None,
                )
                created.append(word_to_dict(word))

        return JsonResponse({"created": created, "skipped": skipped, "failed": failed})
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=500)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def build_local_quiz(words, count):
    words = list(words)
    random.shuffle(words)
    selected = words[:count]
    questions = []

    for index, word in enumerate(selected):
        qtype = ["translation_choice", "fill_blank", "pos_choice"][index % 3]
        if qtype == "translation_choice":
            distractors = [w.translation for w in words if w.id != word.id and w.translation][:3]
            options = distractors + [word.translation]
            random.shuffle(options)
            prompt = f'Выберите перевод слова "{word.term}"'
            answer = word.translation
        elif qtype == "fill_blank":
            sentence = word.example or f"I use {word.term} in a sentence."
            prompt = sentence.replace(word.term, "____", 1) if word.term in sentence else f"Fill the blank: ____ = {word.translation}"
            options = []
            answer = word.term
        else:
            options = ["noun", "verb", "adj", "adv", "phrase", "other"]
            prompt = f'Какая часть речи у "{word.term}"?'
            answer = word.pos

        questions.append({
            "id": f"q{index + 1}",
            "word_id": word.id,
            "type": qtype,
            "prompt": prompt,
            "options": options,
            "answer": answer,
        })
    return questions


def sanitize_quiz_questions(items, words_by_id, count):
    questions = []
    for item in items:
        try:
            word_id = int(item.get("word_id"))
        except (TypeError, ValueError):
            continue
        word = words_by_id.get(word_id)
        if not word:
            continue
        qtype = item.get("type")
        if qtype not in {"translation_choice", "fill_blank", "pos_choice"}:
            continue
        answer = str(item.get("answer", "")).strip()
        if not answer:
            continue
        questions.append({
            "id": f"q{len(questions) + 1}",
            "word_id": word.id,
            "type": qtype,
            "prompt": str(item.get("prompt", "")).strip()[:500],
            "options": [str(opt).strip()[:255] for opt in item.get("options", []) if str(opt).strip()][:6],
            "answer": answer[:255],
        })
        if len(questions) >= count:
            break
    return questions


def build_quiz(words, count):
    words = list(words)
    if not get_groq_key():
        return build_local_quiz(words, count)

    compact_words = [
        {
            "id": word.id,
            "word": word.term,
            "translation": word.translation,
            "pos": word.pos,
            "example": word.example,
        }
        for word in words
    ]
    prompt = (
        "Create a Russian-language vocabulary quiz from these saved dictionary words.\n"
        f"Return exactly {count} questions as JSON: "
        "{\"questions\":[{\"word_id\":1,\"type\":\"translation_choice|fill_blank|pos_choice\","
        "\"prompt\":\"...\",\"options\":[\"...\"],\"answer\":\"...\"}]}.\n"
        "Use only the provided word_id values. Multiple choice questions need 4 options. "
        "Fill-in-the-blank questions may have an empty options array.\n"
        f"Words: {json.dumps(compact_words, ensure_ascii=False)}"
    )
    try:
        result = groq_chat_json(prompt, "You generate precise short vocabulary quizzes. Return raw JSON only.")
        questions = sanitize_quiz_questions(result.get("questions", []), {word.id: word for word in words}, count)
        if len(questions) >= min(count, len(words)):
            return questions
    except Exception:
        pass
    return build_local_quiz(words, count)


@login_required
@require_http_methods(["POST"])
def api_quiz_generate(request):
    try:
        data = json.loads(request.body or "{}")
        count = min(max(int(data.get("count", 5)), 5), 10)
        words = Word.objects.filter(user=request.user).exclude(translation="")
        if data.get("category_id"):
            words = words.filter(category_id=data.get("category_id"))
        words = list(words)
        if len(words) < QUIZ_MIN_WORDS:
            return JsonResponse({"error": f"At least {QUIZ_MIN_WORDS} words are required"}, status=400)

        questions = build_quiz(words, min(count, len(words)))
        return JsonResponse({"questions": questions})
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


@login_required
@require_http_methods(["POST"])
def api_quiz_submit(request):
    try:
        data = json.loads(request.body)
        answers = data.get("answers", [])
        correct = 0
        results = []

        for answer in answers:
            word_id = answer.get("word_id")
            expected = normalize_text(answer.get("expected"))
            given = normalize_text(answer.get("answer"))
            is_correct = bool(expected and given == expected)
            try:
                word = Word.objects.get(pk=word_id, user=request.user)
            except Word.DoesNotExist:
                continue

            if is_correct:
                word.quiz_correct_count += 1
                correct += 1
            else:
                word.quiz_wrong_count += 1
            word.is_difficult = word.lapse_count + word.quiz_wrong_count > word.quiz_correct_count + 1
            word.save()
            results.append({"word_id": word.id, "correct": is_correct})

        return JsonResponse({"score": correct, "total": len(results), "results": results})
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


def pronunciation_status(target, transcript):
    target_norm = normalize_text(target)
    transcript_norm = normalize_text(transcript)
    if not target_norm or not transcript_norm:
        return "retry"
    if target_norm == transcript_norm:
        return "correct"
    target_parts = set(target_norm.split())
    transcript_parts = set(transcript_norm.split())
    if target_parts and target_parts.issubset(transcript_parts):
        return "close"
    return "retry"


@login_required
@require_http_methods(["POST"])
def api_pronunciation_check(request):
    audio_file = request.FILES.get("audio")
    target = request.POST.get("target", "").strip()
    word_id = request.POST.get("word_id")

    if word_id:
        try:
            target = Word.objects.get(pk=word_id, user=request.user).term
        except Word.DoesNotExist:
            return JsonResponse({"error": "Word not found"}, status=404)
    if not target:
        return JsonResponse({"error": "Target is required"}, status=400)
    if not audio_file:
        return JsonResponse({"error": "Audio is required"}, status=400)
    if audio_file.size > 4 * 1024 * 1024:
        return JsonResponse({"error": "Audio file is too large"}, status=400)

    groq_key = get_groq_key()
    if not groq_key:
        return JsonResponse({"error": "Server config missing: GROQ_API_KEY"}, status=500)

    try:
        response = requests.post(
            f"{GROQ_API_BASE}/audio/transcriptions",
            headers={"Authorization": f"Bearer {groq_key}"},
            data={"model": GROQ_STT_MODEL, "language": "en"},
            files={"file": (audio_file.name or "speech.webm", audio_file.read(), audio_file.content_type or "audio/webm")},
            timeout=30,
        )
        if response.status_code != 200:
            return JsonResponse({"error": "Speech provider error"}, status=500)

        transcript = response.json().get("text", "").strip()
        status = pronunciation_status(target, transcript)
        feedback = {
            "correct": "Отлично, звучит правильно.",
            "close": "Почти правильно, попробуй еще раз чуть четче.",
            "retry": "Пока не похоже, послушай слово и повтори еще раз.",
        }[status]
        return JsonResponse({"status": status, "transcript": transcript, "feedback": feedback})
    except requests.RequestException:
        return JsonResponse({"error": "Speech provider unavailable"}, status=502)
