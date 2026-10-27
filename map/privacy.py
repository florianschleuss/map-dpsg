from django.conf import settings
from django.shortcuts import render
from django.views.decorators.http import require_GET

@require_GET
def privacy(request):
    return render(request,'privacy.html',{'session_days':max(1,settings.SESSION_COOKIE_AGE//86400),'csrf_days':max(1,settings.CSRF_COOKIE_AGE//86400)})

@require_GET
def imprint(request):
    return render(request,'imprint.html')
