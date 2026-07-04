from django.urls import path
from . import views, api

urlpatterns = [
    path('', views.index, name='index'),
    path('signup/', views.signup, name='signup'),
    
    # API Endpoints
    path('api/words/', api.api_words_list, name='api_words_list'),
    path('api/words/add/', api.api_word_create, name='api_word_create'),
    path('api/words/bulk-ai/', api.api_words_bulk_ai, name='api_words_bulk_ai'),
    path('api/categories/', api.api_categories_list, name='api_categories_list'),
    path('api/categories/add/', api.api_category_create, name='api_category_create'),
    path('api/categories/<int:pk>/delete/', api.api_category_delete, name='api_category_delete'),
    
    path('api/words/<int:pk>/update/', api.api_word_update, name='api_word_update'),
    path('api/words/<int:pk>/delete/', api.api_word_delete, name='api_word_delete'),
    
    path('api/ai-lookup/', api.api_ai_lookup, name='api_ai_lookup'),
    path('api/tts/', api.api_tts, name='api_tts'),
    path('api/review/due/', api.api_review_due, name='api_review_due'),
    path('api/review/<int:pk>/answer/', api.api_review_answer, name='api_review_answer'),
    path('api/quiz/generate/', api.api_quiz_generate, name='api_quiz_generate'),
    path('api/quiz/submit/', api.api_quiz_submit, name='api_quiz_submit'),
    path('api/pronunciation/check/', api.api_pronunciation_check, name='api_pronunciation_check'),
    
    # PWA
    path('manifest.json', views.pwa_manifest, name='pwa_manifest'),
    path('sw.js', views.pwa_sw, name='pwa_sw'),
]
