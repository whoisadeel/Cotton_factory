"""
Development settings for Cotton Factory Management System
"""
import os
from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ['*']

SECRET_KEY = 'dev-only-insecure-key-do-not-use-in-production-cotton-factory-2026'

# Standard SQLite database
# The database file is encrypted at rest using the encrypt_db management command
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Database encryption key — used by encrypt_db / decrypt_db commands
DATABASE_ENCRYPTION_KEY = os.environ.get(
    'DB_ENCRYPTION_KEY',
    'cotton-factory-dev-key-change-in-production-2026'
)

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
SESSION_COOKIE_AGE = 86400
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
