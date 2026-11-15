import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Secrets are supplied by the process environment, never read from a tracked file.


def env_list(name, default=''):
    return [value.strip() for value in os.environ.get(name, default).split(',') if value.strip()]


SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not SECRET_KEY:
    raise ImproperlyConfigured('Set SECRET_KEY in the process environment.')
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
if DEBUG and os.environ.get('VERCEL'):
    raise ImproperlyConfigured('DEBUG must be False on Vercel.')
ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1' if DEBUG else '')
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')
# Vercel supplies this exact deployment hostname. Do not trust every vercel.app site.
if os.environ.get('VERCEL_URL'):
    ALLOWED_HOSTS.append(os.environ['VERCEL_URL'])
    CSRF_TRUSTED_ORIGINS.append('https://' + os.environ['VERCEL_URL'])
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('Set explicit ALLOWED_HOSTS (no catch-all wildcard).')

# ─── Apps ──────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'notes_app',
]

# ─── Middleware ─────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'IN16_Study_Manager.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'IN16_Study_Manager.wsgi.application'

# ─── Database ──────────────────────────────────────────────────────────────────
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    if not DEBUG:
        raise ImproperlyConfigured('Set DATABASE_URL for non-development environments.')
    database_url = 'sqlite:///' + str(BASE_DIR / 'db.sqlite3')
DATABASES = {'default': dj_database_url.parse(database_url, conn_max_age=0)}
if DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql':
    DATABASES['default'].setdefault('OPTIONS', {})['sslmode'] = 'require'
    # Supabase transaction poolers cannot support server-side cursors.
    DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True
elif not DEBUG:
    raise ImproperlyConfigured('Non-development environments require PostgreSQL.')

# ─── Password validation ────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── Localisation ───────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Africa/Nairobi'
USE_I18N      = True
USE_TZ        = True

# ─── Static files ───────────────────────────────────────────────────────────────
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# ─── Auth redirects ─────────────────────────────────────────────────────────────
LOGIN_URL             = '/login/'
LOGIN_REDIRECT_URL    = '/'
LOGOUT_REDIRECT_URL   = '/login/'

# ─── Vercel HTTPS proxy ──────────────────────────────────────────────────────────
SECURE_PROXY_SSL_HEADER        = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT            = not DEBUG
SECURE_HSTS_SECONDS            = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD            = True
SESSION_COOKIE_SECURE          = not DEBUG
CSRF_COOKIE_SECURE             = not DEBUG

# ─── Misc ───────────────────────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
