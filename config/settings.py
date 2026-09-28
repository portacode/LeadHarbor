import json
import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
# JSON avoids shell interpolation of passwords, branding and multiline inputs.
RUNTIME_FILE = Path(os.environ.get('RUNTIME_FILE', BASE_DIR / '.private/runtime.json'))
RUNTIME = json.loads(RUNTIME_FILE.read_text()) if RUNTIME_FILE.exists() else {}
def env(name, default=''):
    return os.environ.get(name, RUNTIME.get(name, default))
def flag(name, default=False):
    return str(env(name, default)).lower() in {'1', 'true', 'yes'}
DEBUG = flag('DEBUG')
SECRET_KEY = env('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError('Run scripts/configure.py first or set DJANGO_SECRET_KEY.')
ALLOWED_HOSTS = env('ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]').split(',')
PUBLIC_URL = env('PUBLIC_URL', 'http://localhost:8000').rstrip('/')
CSRF_TRUSTED_ORIGINS = [PUBLIC_URL]
INSTALLED_APPS = ['unfold', 'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
                  'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
                  'axes', 'website', 'analytics']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware',
              'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware',
              'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware',
              'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware',
              'axes.middleware.AxesMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'],
              'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request',
              'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': dj_database_url.parse(env('DATABASE_URL', f'sqlite:///{BASE_DIR / "db.sqlite3"}'), conn_max_age=60)}
AUTH_PASSWORD_VALIDATORS = [{'NAME': f'django.contrib.auth.password_validation.{name}'} for name in
                           ['UserAttributeSimilarityValidator', 'MinimumLengthValidator', 'CommonPasswordValidator', 'NumericPasswordValidator']]
AUTHENTICATION_BACKENDS = ['axes.backends.AxesStandaloneBackend', 'django.contrib.auth.backends.ModelBackend']
AXES_FAILURE_LIMIT = 8
AXES_COOLOFF_TIME = 1
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address']
LANGUAGE_CODE = 'en-us'
TIME_ZONE = env('TIME_ZONE', 'UTC')
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'
LOGIN_URL = '/admin/login/'
SECURE_SSL_REDIRECT = flag('SECURE_SSL_REDIRECT', PUBLIC_URL.startswith('https://'))
SESSION_COOKIE_SECURE = PUBLIC_URL.startswith('https://')
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_HSTS_SECONDS = 31536000 if SESSION_COOKIE_SECURE else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SESSION_COOKIE_SECURE
SECURE_HSTS_PRELOAD = SESSION_COOKIE_SECURE
# Application port binds loopback behind the generated nginx proxy only.
if flag('TRUST_PROXY'):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
TRUST_X_FORWARDED_FOR = flag('TRUST_PROXY')
TELEGRAM_BOT_TOKEN = env('TELEGRAM_BOT_TOKEN')
ANALYTICS_DIGEST_DELAY_SECONDS = 15
ANALYTICS_RETENTION_DAYS = int(env('ANALYTICS_RETENTION_DAYS', 180))
GEOIP_ENABLED = flag('GEOIP_ENABLED', True)
DATA_UPLOAD_MAX_MEMORY_SIZE = 128 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
UNFOLD = {'SITE_TITLE': 'LeadHarbor', 'SITE_HEADER': 'LeadHarbor',
          'SITE_SUBHEADER': 'Your business, in focus', 'SITE_URL': '/',
          'DASHBOARD_CALLBACK': 'website.dashboard.admin_dashboard'}
