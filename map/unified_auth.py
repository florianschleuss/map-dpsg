from urllib.parse import urlencode
from django.contrib.auth.views import LoginView
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect
from django.views.decorators.http import require_GET
from django.contrib.auth.views import LogoutView
from django.middleware.csrf import get_token
from django.http import JsonResponse
from django.shortcuts import render

class MapLogoutView(LogoutView):
    http_method_names=['get','post','options']
    next_page='login'

    def get(self,request,*args,**kwargs):
        if request.GET.get('fresh')=='1':
            response=JsonResponse({'csrfToken':get_token(request)})
            response['Cache-Control']='no-store'
            return response
        return render(request,'registration/logout_confirm.html')

class GermanAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Benutzername'
        self.fields['password'].label = 'Passwort'
        self.fields['username'].widget.attrs['autocomplete'] = 'username'
        self.fields['password'].widget.attrs['autocomplete'] = 'current-password'

class MapLoginView(LoginView):
    authentication_form = GermanAuthenticationForm
    template_name = 'registration/login.html'

    def get_context_data(self, **kwargs):
        from .sso import configuration
        context=super().get_context_data(**kwargs)
        config=configuration()
        context['sso_enabled']=bool(config and config.enabled)
        return context

    def get_default_redirect_url(self):
        return '/dashboard/'

@require_GET
def admin_login(request):
    query = urlencode({'next': request.GET.get('next', '/dashboard/')})
    return redirect('/accounts/login/?' + query)
