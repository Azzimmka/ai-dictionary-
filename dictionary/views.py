from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required

@login_required
def index(request):
    return render(request, 'dictionary/index.html')

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
