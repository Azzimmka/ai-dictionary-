from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.contrib.auth.decorators import login_required
from django.urls import reverse

from .forms import UsernameChangeForm

@login_required
def index(request):
    return render(request, 'dictionary/index.html')

@login_required
def profile(request):
    username_form = UsernameChangeForm(instance=request.user)
    password_form = PasswordChangeForm(request.user)
    saved = request.GET.get('saved')

    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        saved = None

        if form_type == 'username':
            username_form = UsernameChangeForm(request.POST, instance=request.user)
            if username_form.is_valid():
                username_form.save()
                return redirect(f"{reverse('profile')}?saved=username")
        elif form_type == 'password':
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                return redirect(f"{reverse('profile')}?saved=password")

    return render(
        request,
        'dictionary/profile.html',
        {
            'username_form': username_form,
            'password_form': password_form,
            'saved': saved,
        },
    )

def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

from django.http import HttpResponse
from django.conf import settings
import os

def pwa_manifest(request):
    path = os.path.join(settings.BASE_DIR, 'dictionary/static/dictionary/manifest.json')
    with open(path, 'rb') as f:
        return HttpResponse(f.read(), content_type='application/json')

def pwa_sw(request):
    path = os.path.join(settings.BASE_DIR, 'dictionary/static/dictionary/sw.js')
    with open(path, 'rb') as f:
        return HttpResponse(f.read(), content_type='application/javascript')
