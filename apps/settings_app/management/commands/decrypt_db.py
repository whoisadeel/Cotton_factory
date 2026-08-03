"""
Decrypt the database file to make it usable.
Run this before starting the server.

Usage:
    python manage.py decrypt_db     # Decrypts db.sqlite3.enc → db.sqlite3
"""
import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings

try:
    from cryptography.fernet import Fernet, InvalidToken
    import base64, hashlib
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


def get_fernet_key(passphrase: str) -> bytes:
    key = hashlib.sha256(passphrase.encode()).digest()
    return base64.urlsafe_b64encode(key)


class Command(BaseCommand):
    help = 'Decrypt the database file for use'

    def handle(self, *args, **options):
        if not HAS_CRYPTO:
            self.stderr.write('ERROR: pip install cryptography')
            return

        db_path = Path(settings.DATABASES['default']['NAME'])
        enc_path = db_path.with_suffix('.sqlite3.enc')
        passphrase = getattr(settings, 'DATABASE_ENCRYPTION_KEY', '')

        if not passphrase:
            self.stderr.write('ERROR: DATABASE_ENCRYPTION_KEY not set.')
            return

        if not enc_path.exists():
            if db_path.exists():
                self.stdout.write('Database is already decrypted (unencrypted file exists).')
            else:
                self.stderr.write(f'ERROR: No encrypted file found: {enc_path}')
            return

        self.stdout.write(f'Decrypting {enc_path} ...')

        with open(enc_path, 'rb') as f:
            encrypted = f.read()

        key = get_fernet_key(passphrase)
        fernet = Fernet(key)

        try:
            data = fernet.decrypt(encrypted)
        except InvalidToken:
            self.stderr.write(
                self.style.ERROR(
                    '\n❌ DECRYPTION FAILED — wrong encryption key!\n'
                    '   Check DB_ENCRYPTION_KEY environment variable.\n'
                    '   If you lost the key, the data cannot be recovered.'
                )
            )
            return

        with open(db_path, 'wb') as f:
            f.write(data)

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Database decrypted successfully.\n'
            f'   File: {db_path}\n'
            f'   You can now start the server: python manage.py runserver\n'
            f'   When done, encrypt again: python manage.py encrypt_db --remove'
        ))
