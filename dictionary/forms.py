from django import forms
from django.contrib.auth import get_user_model


class UsernameChangeForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ["username"]
        labels = {"username": "Имя пользователя"}

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        User = get_user_model()
        existing = User.objects.filter(username__iexact=username)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("Это имя уже занято.")
        return username
