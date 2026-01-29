from django.db import models
from django.contrib.auth.models import User

class Category(models.Model):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        unique_together = ['name', 'user']

    def __str__(self):
        return self.name

class Word(models.Model):
    POS_CHOICES = [
        ('noun', 'Существительное'),
        ('verb', 'Глагол'),
        ('adj', 'Прилагательное'),
        ('adv', 'Наречие'),
        ('phrase', 'Фраза'),
        ('other', 'Другое'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='words')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True, related_name='words')
    
    term = models.CharField(max_length=255)
    translation = models.CharField(max_length=255)
    definition = models.TextField(blank=True, null=True)
    example = models.TextField(blank=True, null=True)
    pos = models.CharField(max_length=10, choices=POS_CHOICES, default='other')
    
    is_learned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.term} - {self.translation}"

    class Meta:
        ordering = ['-created_at']
