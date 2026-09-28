import os
os.environ.setdefault('DJANGO_SECRET_KEY', 'test-only-never-use-in-production-' + 'x' * 40)
from .settings import *
DATABASES = {'default': dj_database_url.parse(os.environ['TEST_DATABASE_URL']) if os.environ.get('TEST_DATABASE_URL') else {'ENGINE':'django.db.backends.sqlite3', 'NAME':':memory:'}}
ALLOWED_HOSTS = ['testserver','localhost','127.0.0.1']
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
STORAGES = {'default': {'BACKEND':'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
AXES_ENABLED = False
GEOIP_ENABLED = False
TELEGRAM_BOT_TOKEN = ''
