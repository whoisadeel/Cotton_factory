"""
Setup database from scratch — bypasses migration issues on Windows.
Usage: python manage.py setup_db
"""
import os
import sys
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Set up fresh database: migrate + create admin + seed data'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Delete existing db.sqlite3 first')

    def handle(self, *args, **options):
        from django.conf import settings

        db_path = settings.DATABASES['default'].get('NAME', 'db.sqlite3')

        if options['force'] and os.path.exists(db_path):
            os.remove(db_path)
            self.stdout.write(self.style.WARNING(f'Deleted {db_path}'))

        if os.path.exists(db_path):
            self.stdout.write(self.style.ERROR(
                f'{db_path} already exists. Use --force to delete it first,'
                f' or delete it manually.'
            ))
            sys.exit(1)

        self.stdout.write(self.style.NOTICE('\n1. Running migrations...'))
        try:
            call_command('migrate', verbosity=1)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\nMigration failed: {e}'))
            self.stdout.write(self.style.WARNING(
                '\nThis usually means migration files were regenerated.'
                '\nFix: Delete all apps/*/migrations/0*.py files, then re-download'
                '\nthe correct migration files from the project source.'
                '\n\nAlternatively, run: python manage.py setup_db_raw'
            ))
            sys.exit(1)

        self.stdout.write(self.style.NOTICE('\n2. Creating admin user...'))
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@factory.local',
                password='admin123456',
                first_name='Admin',
            )
            self.stdout.write(self.style.SUCCESS('   Admin created (admin / admin123456)'))
        else:
            self.stdout.write('   Admin already exists')

        self.stdout.write(self.style.NOTICE('\n3. Seeding chart of accounts...'))
        call_command('seed_accounts')

        self.stdout.write(self.style.NOTICE('\n4. Seeding sample data...'))
        call_command('seed_data')

        self.stdout.write(self.style.NOTICE('\n5. Collecting static files...'))
        call_command('collectstatic', '--noinput', verbosity=0)

        self.stdout.write(self.style.SUCCESS(
            '\n' + '=' * 50 +
            '\n  ✅ Setup complete!'
            '\n  Login: admin / admin123456'
            '\n  Run: python manage.py runserver'
            '\n' + '=' * 50
        ))
