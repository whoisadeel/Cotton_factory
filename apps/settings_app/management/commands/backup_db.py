"""
Database Backup Command — Creates timestamped SQLite backup.
Usage: python manage.py backup_db
       python manage.py backup_db --output /path/to/backup.sqlite3
"""
import os
import shutil
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Create a backup of the SQLite database — ڈیٹا بیس کا بیک اپ بنائیں'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output', '-o',
            type=str,
            default='',
            help='Output file path (default: backups/backup_YYYYMMDD_HHMMSS.sqlite3)'
        )

    def handle(self, *args, **options):
        db_path = settings.DATABASES['default']['NAME']
        if not os.path.exists(db_path):
            self.stderr.write(self.style.ERROR(f'Database not found: {db_path}'))
            return

        # Create backups directory
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        # Determine output path
        output = options['output']
        if not output:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output = os.path.join(backup_dir, f'backup_{timestamp}.sqlite3')

        # Copy database file
        shutil.copy2(db_path, output)
        file_size = os.path.getsize(output)
        size_mb = file_size / (1024 * 1024)

        self.stdout.write(self.style.SUCCESS(
            f'✅ Backup created successfully!\n'
            f'   File: {output}\n'
            f'   Size: {size_mb:.2f} MB\n'
            f'   بیک اپ کامیابی سے بن گیا'
        ))

        # Clean old backups — keep only last 10
        backups = sorted([
            os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
            if f.startswith('backup_') and f.endswith('.sqlite3')
        ])
        if len(backups) > 10:
            for old in backups[:-10]:
                os.remove(old)
                self.stdout.write(f'   Removed old backup: {os.path.basename(old)}')
