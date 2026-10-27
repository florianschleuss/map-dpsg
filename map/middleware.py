class PrivacyHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        if request.method == 'POST' and request.path in ['/accounts/login/', '/admin/login/']:
            from .request_security import login_allowed
            if not login_allowed(request):
                from .error_views import error_response
                return error_response(429)
        from django.utils import translation
        with translation.override('de'):
            request.LANGUAGE_CODE='de'
            response = self.get_response(request)
        response['Content-Language']='de'
        response['Referrer-Policy'] = 'strict-origin' if request.path.startswith(('/manage/','/confirm/','/konto/passwort/')) else 'same-origin'
        response['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        response['Cache-Control'] = 'no-store'
        response['X-Robots-Tag'] = 'noindex, nofollow'
        response['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; object-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
        return response
