from django.contrib import admin
from .models import Word, Category

@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ('term', 'translation', 'pos', 'is_learned', 'user', 'created_at')
    list_filter = ('is_learned', 'pos', 'created_at', 'user')
    search_fields = ('term', 'translation', 'user__username')
    list_editable = ('is_learned',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at')
    list_filter = ('user',)
    search_fields = ('name',)
