"""
Cotton Factory Management System - Base Settings
"""
import os
from pathlib import Path
from django.core.management.utils import get_random_secret_key

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# In production, always set DJANGO_SECRET_KEY environment variable.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', get_random_secret_key())

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False  # Overridden in development.py

ALLOWED_HOSTS = []

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
]

THIRD_PARTY_APPS = [
    'django_htmx',
]

# Optional: django-apscheduler for automated backup/report emails
# Install with: pip install django-apscheduler
try:
    import django_apscheduler  # noqa: F401
    THIRD_PARTY_APPS.append('django_apscheduler')
except ImportError:
    pass

LOCAL_APPS = [
    'apps.authentication',
    'apps.dashboard',
    'apps.products',
    'apps.parties',
    'apps.purchases',
    'apps.sales',
    'apps.finance',
    'apps.inventory',
    'apps.accounting',
    'apps.ginning',
    'apps.labour',
    'apps.transport',
    'apps.reports',
    'apps.settings_app',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'apps.authentication.middleware.SessionTimeoutMiddleware',
    'apps.authentication.middleware.AuditLogMiddleware',
    'apps.authentication.role_middleware.RoleAccessMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.settings_app.context_processors.company_settings',
                'apps.settings_app.context_processors.date_presets',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database - default SQLite; override per environment
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Custom User Model
AUTH_USER_MODEL = 'authentication.User'

# Internationalization
LANGUAGE_CODE = 'en'
TIME_ZONE = 'Asia/Karachi'
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ('en', 'English'),
    ('ur', 'Urdu'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login URLs
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/auth/login/'

# Session settings
SESSION_COOKIE_AGE = 86400  # 24 hours (factory stays open all day)
CSRF_FAILURE_VIEW = 'django.views.csrf.csrf_failure'

# Database encryption key — used by encrypt_db / decrypt_db commands
# IMPORTANT: Set DB_ENCRYPTION_KEY environment variable in production!
DATABASE_ENCRYPTION_KEY = os.environ.get(
    'DB_ENCRYPTION_KEY',
    'cotton-factory-default-key-CHANGE-THIS-IN-PRODUCTION'
)
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Security settings
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]

# Security headers (safe defaults for all environments)
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# Login attempt settings
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_DURATION = 15  # minutes

# Cotton Factory Business Settings
FINANCIAL_YEAR_START_MONTH = 7  # July
DEFAULT_CURRENCY = 'PKR'
DEFAULT_WEIGHT_UNIT = 'MAUND'
MAUND_TO_KG = 40  # 1 Maund = 40 kg

# File upload limits (security)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
