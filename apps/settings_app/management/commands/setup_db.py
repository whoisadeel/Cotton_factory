"""
Setup Database — handles all scenarios:
  1. Fresh install (no db.sqlite3) → migrate normally
  2. Old DB with old migrations → fix schema, fake migrations if needed
  3. After migration files were regenerated → sync django_migrations table

Usage:
    python manage.py setup_db              # Auto-detect and fix everything
    python manage.py setup_db --fresh      # Delete DB and start completely fresh
"""
import os
import sqlite3
from pathlib import Path
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings


OUR_APPS = [
    'authentication', 'products', 'parties', 'purchases', 'sales',
    'finance', 'accounting', 'ginning', 'inventory', 'labour',
    'transport', 'settings_app',
]


class Command(BaseCommand):
    help = 'Setup database — handles fresh install, old DB, and migration resets'

    def add_arguments(self, parser):
        parser.add_argument('--fresh', action='store_true',
                            help='Delete existing DB and start completely fresh')

    def handle(self, *args, **options):
        db_path = str(settings.DATABASES['default']['NAME'])
        db_exists = os.path.exists(db_path)

        self.stdout.write('')
        self.stdout.write('═' * 60)
        self.stdout.write('  COTTON FACTORY — DATABASE SETUP')
        self.stdout.write('═' * 60)
        self.stdout.write('')

        # ── Fresh start ──
        if options['fresh']:
            if db_exists:
                # Backup first
                backup_dir = os.path.join(settings.BASE_DIR, 'backups')
                os.makedirs(backup_dir, exist_ok=True)
                import shutil
                from datetime import datetime
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = os.path.join(backup_dir, f'pre_fresh_{ts}.sqlite3')
                shutil.copy2(db_path, backup_path)
                self.stdout.write(f'  📦 Old DB backed up to: {os.path.basename(backup_path)}')
                os.remove(db_path)
                self.stdout.write('  🗑️  Old DB deleted')

            self.stdout.write('  🔄 Running migrations...')
            call_command('migrate', verbosity=0)
            self.stdout.write(self.style.SUCCESS('  ✅ Fresh database created'))

            self.stdout.write('  🔄 Seeding accounts...')
            try:
                call_command('seed_accounts', verbosity=0)
                self.stdout.write(self.style.SUCCESS('  ✅ Chart of accounts seeded'))
            except Exception:
                self.stdout.write('  ⚠️  seed_accounts not available')

            self.stdout.write('  🔄 Seeding data...')
            try:
                call_command('seed_data', verbosity=0)
                self.stdout.write(self.style.SUCCESS('  ✅ Sample data seeded'))
            except Exception:
                self.stdout.write('  ⚠️  seed_data not available')

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('  ✅ Fresh setup complete!'))
            self.stdout.write('     Login: admin / admin123456')
            self.stdout.write('')
            return

        # ── Existing DB or no DB ──
        if not db_exists:
            self.stdout.write('  📋 No database found — creating fresh...')
            call_command('migrate', verbosity=1)
            self.stdout.write(self.style.SUCCESS('  ✅ Database created'))
            try:
                call_command('seed_accounts', verbosity=0)
                self.stdout.write('  ✅ Chart of accounts seeded')
            except Exception:
                pass
            self.stdout.write('')
            return

        # ── DB exists — check if migrations are in sync ──
        self.stdout.write(f'  📋 Database found: {db_path}')
        self.stdout.write(f'     Size: {os.path.getsize(db_path) // 1024} KB')
        self.stdout.write('')

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if django_migrations table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='django_migrations'")
        has_migrations_table = bool(cursor.fetchone())

        if not has_migrations_table:
            conn.close()
            self.stdout.write('  ⚠️  No django_migrations table — running migrate...')
            call_command('migrate', verbosity=1)
            self.stdout.write(self.style.SUCCESS('  ✅ Migrations applied'))
            self.stdout.write('')
            return

        # Check what migrations are recorded
        cursor.execute("SELECT app, name FROM django_migrations")
        recorded = {(row[0], row[1]) for row in cursor.fetchall()}

        # Check what migration files exist on disk
        from django.apps import apps as django_apps
        disk_migrations = set()
        for app_config in django_apps.get_app_configs():
            app_label = app_config.label
            migrations_dir = os.path.join(app_config.path, 'migrations')
            if os.path.exists(migrations_dir):
                for f in os.listdir(migrations_dir):
                    if f.endswith('.py') and f != '__init__.py':
                        name = f[:-3]  # Remove .py
                        disk_migrations.add((app_label, name))

        # Find migrations on disk but not in DB
        unapplied = disk_migrations - recorded
        # Find migrations in DB but not on disk (deleted/regenerated)
        orphaned = {(a, n) for a, n in recorded if a in OUR_APPS} - disk_migrations

        self.stdout.write(f'  Recorded migrations: {len(recorded)}')
        self.stdout.write(f'  Disk migration files: {len(disk_migrations)}')

        if orphaned:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                f'  ⚠️  {len(orphaned)} migration(s) in DB but NOT on disk (regenerated?):'))
            for app, name in sorted(orphaned):
                self.stdout.write(f'     {app}.{name}')

            # Remove orphaned records and add current ones
            self.stdout.write('')
            self.stdout.write('  🔄 Syncing migration records...')
            for app, name in orphaned:
                cursor.execute("DELETE FROM django_migrations WHERE app=? AND name=?", (app, name))
                self.stdout.write(f'     Removed: {app}.{name}')

            # Now fake-apply the current migration files for those apps
            affected_apps = {a for a, n in orphaned}
            for app in affected_apps:
                current_files = [(a, n) for a, n in disk_migrations if a == app]
                for a, n in current_files:
                    if (a, n) not in recorded or (a, n) in orphaned:
                        cursor.execute(
                            "INSERT INTO django_migrations (app, name, applied) VALUES (?, ?, datetime('now'))",
                            (a, n))
                        self.stdout.write(f'     Added: {a}.{n}')

            conn.commit()
            self.stdout.write(self.style.SUCCESS('  ✅ Migration records synced'))

        if unapplied:
            # Filter out the ones we just synced via orphan handling
            synced_apps = {a for a, _ in orphaned} if orphaned else set()
            still_unapplied = {(a, n) for a, n in unapplied if a not in synced_apps}
            if still_unapplied:
                self.stdout.write('')
                self.stdout.write(f'  🔄 {len(still_unapplied)} unapplied migration(s) found...')
                conn.close()
                # Try migrate first; if it fails (tables exist), fake it
                from io import StringIO as SIO
                import sys
                try:
                    call_command('migrate', verbosity=0)
                    self.stdout.write(self.style.SUCCESS('  ✅ Migrations applied'))
                except Exception as e:
                    err_msg = str(e).lower()
                    if 'duplicate column' in err_msg or 'already exists' in err_msg or 'table' in err_msg:
                        self.stdout.write('  ⚠️  Tables already exist — fake-applying migrations...')
                        # Fake-apply all unapplied
                        try:
                            call_command('migrate', '--fake', verbosity=0)
                            self.stdout.write(self.style.SUCCESS('  ✅ Migrations fake-applied'))
                        except Exception as e2:
                            self.stdout.write(self.style.ERROR(f'  ❌ Fake-apply failed: {e2}'))
                    else:
                        self.stdout.write(self.style.ERROR(f'  ❌ Migration failed: {e}'))
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

        conn.close()

        # Now fix any missing columns
        self.stdout.write('')
        self.stdout.write('  🔄 Checking schema...')
        from io import StringIO
        out = StringIO()
        call_command('fix_old_db', '--apply', stdout=out)
        fix_output = out.getvalue()
        if 'no fixes needed' in fix_output:
            self.stdout.write(self.style.SUCCESS('  ✅ Schema is up-to-date'))
        else:
            # Count fixes
            fix_count = fix_output.count('✅ Added')
            self.stdout.write(self.style.SUCCESS(f'  ✅ {fix_count} schema fix(es) applied'))

        # Verify
        self.stdout.write('')
        self.stdout.write('  🔄 Verifying...')
        try:
            import django
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
            # Test a few key models
            from apps.parties.models import Party
            from apps.products.models import UnitOfMeasurement
            from apps.finance.models import PaymentVoucher
            pc = Party.objects.count()
            uc = UnitOfMeasurement.objects.count()
            self.stdout.write(f'     Parties: {pc}, Units: {uc}')
            self.stdout.write(self.style.SUCCESS('  ✅ Database verified — working correctly'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ Verification failed: {e}'))

        self.stdout.write('')
        self.stdout.write('═' * 60)
        self.stdout.write('')
