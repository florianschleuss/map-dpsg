from urllib.parse import urlencode
from django.contrib.auth.views import LoginView
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect
from django.views.decorators.http import require_GET

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

    def get_default_redirect_url(self):
        return '/dashboard/'

@require_GET
def admin_login(request):
    query = urlencode({'next': request.GET.get('next', '/dashboard/')})
    return redirect('/accounts/login/?' + query)
