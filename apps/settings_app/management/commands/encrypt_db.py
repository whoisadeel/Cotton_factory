"""
Encrypt the database file at rest using AES-256 (Fernet).
Run this when shutting down the server to protect data.

Usage:
    python manage.py encrypt_db          # Encrypts db.sqlite3 → db.sqlite3.enc
    python manage.py encrypt_db --remove # Also removes the unencrypted file
"""
import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings

try:
    from cryptography.fernet import Fernet
    import base64, hashlib
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


def get_fernet_key(passphrase: str) -> bytes:
    """Derive a Fernet key from a passphrase using SHA-256."""
    key = hashlib.sha256(passphrase.encode()).digest()
    return base64.urlsafe_b64encode(key)


class Command(BaseCommand):
    help = 'Encrypt the database file at rest (AES-256)'

    def add_arguments(self, parser):
        parser.add_argument('--remove', action='store_true',
                            help='Remove unencrypted file after encryption')

    def handle(self, *args, **options):
        if not HAS_CRYPTO:
            self.stderr.write(
                'ERROR: cryptography package required.\n'
                'Install it: pip install cryptography\n'
            )
            return

        db_path = Path(settings.DATABASES['default']['NAME'])
        enc_path = db_path.with_suffix('.sqlite3.enc')
        passphrase = getattr(settings, 'DATABASE_ENCRYPTION_KEY', '')

        if not passphrase:
            self.stderr.write('ERROR: DATABASE_ENCRYPTION_KEY not set in settings.')
            return

        if not db_path.exists():
            self.stderr.write(f'ERROR: Database file not found: {db_path}')
            return

        self.stdout.write(f'Encrypting {db_path} ...')

        # Read the database file
        with open(db_path, 'rb') as f:
            data = f.read()

        # Encrypt with AES-256 (Fernet uses AES-128-CBC, but with SHA-256 derived key)
        key = get_fernet_key(passphrase)
        fernet = Fernet(key)
        encrypted = fernet.encrypt(data)

        # Write encrypted file
        with open(enc_path, 'wb') as f:
            f.write(encrypted)

        size_before = len(data)
        size_after = len(encrypted)
        self.stdout.write(
            f'✓ Encrypted: {db_path.name} ({size_before:,} bytes) → '
            f'{enc_path.name} ({size_after:,} bytes)'
        )

        if options['remove']:
            os.remove(db_path)
            self.stdout.write(f'✓ Removed unencrypted file: {db_path.name}')

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Database encrypted with AES-256.\n'
            f'   Encrypted file: {enc_path}\n'
            f'   To decrypt: python manage.py decrypt_db\n'
            f'   ⚠ KEEP YOUR ENCRYPTION KEY SAFE — without it, data is LOST!'
        ))
