"""
Database Restore Command — Restores from a backup file.
Usage: python manage.py restore_db backups/backup_20260714_120000.sqlite3
"""
import os
import shutil
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Restore database from a backup file — بیک اپ سے ڈیٹا بیس بحال کریں'

    def add_arguments(self, parser):
        parser.add_argument(
            'backup_file',
            type=str,
            help='Path to the backup file to restore from'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompt'
        )

    def handle(self, *args, **options):
        backup_file = options['backup_file']
        if not os.path.exists(backup_file):
            self.stderr.write(self.style.ERROR(f'Backup file not found: {backup_file}'))
            return

        db_path = settings.DATABASES['default']['NAME']

        if not options['force']:
            self.stdout.write(self.style.WARNING(
                f'\n⚠️  WARNING: This will REPLACE the current database!\n'
                f'   Current DB: {db_path}\n'
                f'   Restore from: {backup_file}\n'
            ))
            confirm = input('   Type "RESTORE" to confirm: ')
            if confirm != 'RESTORE':
                self.stdout.write('   Cancelled.')
                return

        # Auto-backup current database first
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        auto_backup = os.path.join(backup_dir, f'pre_restore_{timestamp}.sqlite3')
        if os.path.exists(db_path):
            shutil.copy2(db_path, auto_backup)
            self.stdout.write(f'   Auto-backup of current DB: {auto_backup}')

        # Restore
        shutil.copy2(backup_file, db_path)
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Database restored successfully!\n'
            f'   Restored from: {backup_file}\n'
            f'   ڈیٹا بیس کامیابی سے بحال ہو گیا\n'
            f'   ⚠️  Please restart the server.\n'
        ))
