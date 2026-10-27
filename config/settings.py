import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get('DEBUG', '0') == '1'
SECRET_KEY = os.environ.get('SECRET_KEY', '')
if len(SECRET_KEY) < 50:
    raise RuntimeError('Set SECRET_KEY to at least 50 random characters.')
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
CSRF_TRUSTED_ORIGINS = [x for x in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if x]
PUBLIC_URL = os.environ.get('PUBLIC_URL', 'http://localhost:8000').rstrip('/')
INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'map.apps.MapConfig']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.locale.LocaleMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware', 'map.middleware.PrivacyHeadersMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
if os.environ.get('SQLITE_TEST') == '1':
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'test.sqlite3'}}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': os.environ.get('POSTGRES_DB', 'map'), 'USER': os.environ.get('POSTGRES_USER', 'map'), 'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''), 'HOST': os.environ.get('POSTGRES_HOST', 'db'), 'PORT': '5432', 'CONN_MAX_AGE': 60}}
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}, {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}}, {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}, {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE = 'de'
TIME_ZONE = 'Europe/Berlin'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = Path(os.environ.get('STATIC_ROOT', str(BASE_DIR / 'staticfiles')))
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'mailpit')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '1025'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', '0') == '1'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', '0') == '1'
EMAIL_TIMEOUT = 20
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'map@example.org')
SECURE_SSL_REDIRECT = os.environ.get('HTTPS', '0') == '1'
SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
SECURE_HSTS_SECONDS = 31536000 if SECURE_SSL_REDIRECT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
DATA_UPLOAD_MAX_MEMORY_SIZE = 262144
TOKEN_MAX_AGE = int(os.environ.get('TOKEN_MAX_AGE', '2592000'))

# MAP: German interface for every account and browser.
LANGUAGE_CODE = 'de'
LANGUAGES = [('de', 'Deutsch')]

STATICFILES_DIRS = [BASE_DIR / 'static']

# MAP: Account recovery
PASSWORD_RESET_TIMEOUT = 3600

# MAP: MVP security audit 12
MAP_TRUSTED_PROXY_HOSTS=[value.strip() for value in os.environ.get('MAP_TRUSTED_PROXY_HOSTS','').split(',') if value.strip()]
MAP_TRUSTED_PROXY_NETWORKS=[value.strip() for value in os.environ.get('MAP_TRUSTED_PROXY_NETWORKS','').split(',') if value.strip()]
CSRF_FAILURE_VIEW='map.error_views.csrf_failure'
CSRF_COOKIE_HTTPONLY=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE='Lax'
SESSION_COOKIE_AGE=7200
SESSION_EXPIRE_AT_BROWSER_CLOSE=True
DATA_UPLOAD_MAX_NUMBER_FILES=0

# MAP association roles and common navigation
AUTHENTICATION_BACKENDS=['map.auth_backend.RoleBackend']
if 'map.roles.portal_context' not in TEMPLATES[0]['OPTIONS']['context_processors']:
    TEMPLATES[0]['OPTIONS']['context_processors'].append('map.roles.portal_context')

# Operator identity is deployment configuration, never embedded in public source.
MAP_ORGANIZATION = os.environ.get('MAP_ORGANIZATION', 'Dein Pfadfinderstamm')
MAP_SITE_TITLE = os.environ.get('MAP_SITE_TITLE', 'Veranstaltungsanmeldungen')
MAP_MAIL_SENDER_NAME = os.environ.get('MAP_MAIL_SENDER_NAME', 'Anmeldungsverwaltung')
MAP_CONTACT_EMAIL = os.environ.get('MAP_CONTACT_EMAIL', '')
MAP_RESPONSIBLE_NAME = os.environ.get('MAP_RESPONSIBLE_NAME', '')
MAP_RESPONSIBLE_ADDRESS = os.environ.get('MAP_RESPONSIBLE_ADDRESS', '')
MAP_IMPRINT_TEXT = os.environ.get('MAP_IMPRINT_TEXT', '')
MAP_IMPRINT_URL = os.environ.get('MAP_IMPRINT_URL', '')
MAP_HOSTING_DESCRIPTION = os.environ.get('MAP_HOSTING_DESCRIPTION', 'Der Hostinganbieter wurde noch nicht eingetragen.')
MAP_MAIL_DESCRIPTION = os.environ.get('MAP_MAIL_DESCRIPTION', 'Der verwendete Maildienst wurde noch nicht eingetragen.')
MAP_PRIVACY_LEGAL_TEXT = os.environ.get('MAP_PRIVACY_LEGAL_TEXT', '')
MAP_PRIVACY_AUTHORITY = os.environ.get('MAP_PRIVACY_AUTHORITY', '')
MAP_PHOTO_DISPLAY_LABEL = os.environ.get('MAP_PHOTO_DISPLAY_LABEL', 'Aushang von Bildern in den Veranstaltungsräumen')
MAP_LOGO_PATH = os.environ.get('MAP_LOGO_PATH', 'map/logo.svg')
MAP_FAVICON_PATH = os.environ.get('MAP_FAVICON_PATH', 'map/logo.svg')
MAP_PRODUCTION = os.environ.get('MAP_PRODUCTION', '0') == '1'
TEMPLATES[0]['OPTIONS']['context_processors'].append('map.site_config.site_context')

if (BASE_DIR / 'operator-assets').is_dir(): STATICFILES_DIRS.append(BASE_DIR / 'operator-assets')
