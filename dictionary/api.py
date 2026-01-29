import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .models import Word, Category

@login_required
@require_http_methods(["GET"])
def api_categories_list(request):
    categories = Category.objects.filter(user=request.user)
    data = [{'id': c.id, 'name': c.name} for c in categories]
    return JsonResponse({'categories': data})

@login_required
@require_http_methods(["POST"])
def api_category_create(request):
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        if not name:
             return JsonResponse({'error': 'Name required'}, status=400)
             
        cat = Category.objects.create(user=request.user, name=name)
        return JsonResponse({'id': cat.id, 'name': cat.name})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def api_category_delete(request, pk):
    try:
        cat = Category.objects.get(pk=pk, user=request.user)
        cat.delete()
        return JsonResponse({'status': 'success'})
    except Category.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

@login_required
@require_http_methods(["GET"])
def api_words_list(request):
    """
    Returns all words belonging to the current user.
    """
    words = Word.objects.filter(user=request.user).order_by('-created_at')
    
    # Convert DB objects to a list of dictionaries (JSON format)
    data = []
    for w in words:
        data.append({
            'id': w.id,
            'word': w.term,
            'translation': w.translation,
            'example': w.example,
            'pos': w.pos,
            'learned': w.is_learned,
            'category_id': w.category_id
        })
    
    return JsonResponse({'words': data})

@login_required
@require_http_methods(["POST"])
def api_word_create(request):
    """
    Creates a new word for the current user from JSON data.
    """
    try:
        data = json.loads(request.body)
        
        # Basic validation
        term = data.get('word', '').strip()
        translation = data.get('ru', '').strip()
        
        if not term:
            return JsonResponse({'error': 'Word is required'}, status=400)

        # Create the word in the Database
        category_id = data.get('category_id')
        new_word = Word.objects.create(
            user=request.user,
            term=term,
            translation=translation,
            example=data.get('example', ''),
            pos=data.get('pos', 'other'),
            is_learned=False,
            category_id=category_id if category_id else None
        )
        
        # Return the created word back to frontend (with its new ID)
        return JsonResponse({
            'id': new_word.id,
            'word': new_word.term,
            'translation': new_word.translation,
            'pos': new_word.pos,
            'status': 'success'
        }, status=201)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
@login_required
@require_http_methods(["POST"])
def api_word_update(request, pk):
    """
    Updates a word's status (learned/unlearned) or content.
    """
    try:
        word = Word.objects.get(pk=pk, user=request.user)
        data = json.loads(request.body)
        
        # Update fields if present in JSON
        if 'learned' in data:
            word.is_learned = data['learned']
        if 'word' in data:
            word.term = data['word']
        if 'example' in data:
            word.example = data['example']
        if 'ru' in data:
            word.translation = data['ru']
        if 'pos' in data:
            word.pos = data['pos']
            
        word.save()
        return JsonResponse({'status': 'success'})
    except Word.DoesNotExist:
        return JsonResponse({'error': 'Word not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["DELETE"])
def api_word_delete(request, pk):
    """
    Deletes a word.
    """
    try:
        word = Word.objects.get(pk=pk, user=request.user)
        word.delete()
        return JsonResponse({'status': 'success'})
    except Word.DoesNotExist:
        return JsonResponse({'error': 'Word not found'}, status=404)

import os
import requests

@login_required
@require_http_methods(["POST"])
def api_ai_lookup(request):
    try:
        data = json.loads(request.body)
        word = data.get('word', '').strip()
        
        if not word:
            return JsonResponse({'error': 'Word is required'}, status=400)

        # 1. Get API Key from environment
        pplx_key = os.environ.get('PERPLEXITY_API_KEY')
        if not pplx_key:
             return JsonResponse({'error': 'Server config missing: API Key'}, status=500)
             
        # 2. Build Prompt
        # Stronger system instruction to ensure pure JSON
        prompt = (
            f"Define '{word}' for a Russian speaker.\n"
            "Return JSON ONLY with these keys:\n"
            "- \"translation\": \"russian translation\"\n"
            "- \"pos\": \"noun\" (or verb, adj, adv, other)\n"
            "- \"example\": \"Short English sentence.\"\n"
            "NO markdown formatting. NO backticks."
        )

        headers = {
            "Authorization": f"Bearer {pplx_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "sonar-pro",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a backend API. Output raw JSON only. No markdown properties."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        # 3. Request
        response = requests.post("https://api.perplexity.ai/chat/completions", json=payload, headers=headers, timeout=12)
        
        if response.status_code != 200:
            return JsonResponse({'error': f'AI Provider Error: {response.text}'}, status=500)
            
        ai_resp = response.json()
        content = ai_resp['choices'][0]['message']['content'].strip()
        
        # Cleanup: Remove markdown code blocks if they appear
        if content.startswith("```"):
            lines = content.split('\n')
            # Remove first line if it's ```json and last if it's ```
            if lines[0].startswith("```"): lines = lines[1:]
            if lines[-1].startswith("```"): lines = lines[:-1]
            content = "\n".join(lines)
            
        result = json.loads(content)
        
        return JsonResponse(result)

    except json.JSONDecodeError:
        print(f"AI Raw Content: {content}") # Log for debug
        return JsonResponse({'error': 'AI Parse Error: Invalid JSON received'}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
