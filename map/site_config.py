"""Deployment-owned identity; no database or external requests needed."""
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.validators import validate_email, URLValidator
from django.core.exceptions import ValidationError
from pathlib import PurePosixPath


def local_asset(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or ':' in value or '\\' in value or '?' in value or '#' in value:
        raise ImproperlyConfigured('Logo und Favicon müssen relative lokale Static-Pfade sein.')
    return value


def site_context(request=None):
    return {'map_site': {
        'organization': settings.MAP_ORGANIZATION,
        'title': settings.MAP_SITE_TITLE,
        'contact_email': settings.MAP_CONTACT_EMAIL,
        'responsible_name': settings.MAP_RESPONSIBLE_NAME,
        'responsible_address': settings.MAP_RESPONSIBLE_ADDRESS,
        'imprint_text': settings.MAP_IMPRINT_TEXT,
        'imprint_url': settings.MAP_IMPRINT_URL,
        'hosting_description': settings.MAP_HOSTING_DESCRIPTION,
        'mail_description': settings.MAP_MAIL_DESCRIPTION,
        'legal_text': settings.MAP_PRIVACY_LEGAL_TEXT,
        'authority': settings.MAP_PRIVACY_AUTHORITY,
        'photo_display_label': settings.MAP_PHOTO_DISPLAY_LABEL,
        'logo_path': local_asset(settings.MAP_LOGO_PATH),
        'favicon_path': local_asset(settings.MAP_FAVICON_PATH),
    }}


def validate_operator():
    """Fail closed before production deployment with incomplete operator data."""
    errors = []
    for name in ['MAP_ORGANIZATION', 'MAP_RESPONSIBLE_NAME', 'MAP_RESPONSIBLE_ADDRESS', 'MAP_CONTACT_EMAIL', 'MAP_HOSTING_DESCRIPTION', 'MAP_MAIL_DESCRIPTION', 'MAP_PRIVACY_LEGAL_TEXT', 'MAP_PRIVACY_AUTHORITY']:
        if not getattr(settings, name, '').strip(): errors.append(name + ' fehlt.')
    if settings.MAP_ORGANIZATION == 'Dein Pfadfinderstamm': errors.append('Organisation ist noch die Beispielvorgabe.')
    try: validate_email(settings.MAP_CONTACT_EMAIL)
    except ValidationError: errors.append('Datenschutzkontakt ist keine gültige E-Mail-Adresse.')
    if not settings.MAP_IMPRINT_URL and not settings.MAP_IMPRINT_TEXT.strip(): errors.append('Impressumstext oder externer Impressumslink fehlt.')
    if settings.MAP_IMPRINT_URL:
        try: URLValidator(schemes=['https'])(settings.MAP_IMPRINT_URL)
        except ValidationError: errors.append('Impressumslink muss eine gültige HTTPS-Adresse sein.')
    for name in ['MAP_LOGO_PATH', 'MAP_FAVICON_PATH']:
        try: local_asset(getattr(settings, name))
        except ImproperlyConfigured as error: errors.append(str(error))
    if not settings.SECURE_SSL_REDIRECT or not settings.PUBLIC_URL.startswith('https://'): errors.append('HTTPS und eine öffentliche HTTPS-URL sind erforderlich.')
    if settings.DEBUG or '*' in settings.ALLOWED_HOSTS: errors.append('DEBUG oder uneingeschränkte Hosts sind im Produktivbetrieb nicht erlaubt.')
    from urllib.parse import urlsplit
    host = urlsplit(settings.PUBLIC_URL).hostname
    if host not in settings.ALLOWED_HOSTS or settings.PUBLIC_URL not in settings.CSRF_TRUSTED_ORIGINS: errors.append('PUBLIC_URL muss zu ALLOWED_HOSTS und CSRF_TRUSTED_ORIGINS passen.')
    if not settings.MAP_TRUSTED_PROXY_HOSTS and not settings.MAP_TRUSTED_PROXY_NETWORKS: errors.append('Vertrauenswürdiger Reverse Proxy ist nicht konfiguriert.')
    if not settings.EMAIL_USE_TLS and not settings.EMAIL_USE_SSL:
        from .models import MailConfiguration
        config = MailConfiguration.objects.first()
        if not config or not config.enabled or (config.provider == 'smtp' and config.security == 'plain'): errors.append('Produktivversand benötigt SMTP mit TLS oder Microsoft 365; in der UI einrichten.')
    return errors
