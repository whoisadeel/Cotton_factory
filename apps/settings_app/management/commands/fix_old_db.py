"""
Fix Old Database — safely adds any missing columns/tables
when restoring from an older SQLite backup.

Usage:
    python manage.py fix_old_db              # Show what would change (dry-run)
    python manage.py fix_old_db --apply      # Apply fixes

This handles the case where 0001_initial.py was edited in-place
and the old DB thinks migrations are applied but is missing columns.
"""
import sqlite3
from django.core.management.base import BaseCommand
from django.conf import settings
from django.apps import apps


class Command(BaseCommand):
    help = 'Fix an old SQLite database — add any missing columns/tables'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Actually apply fixes (default is dry-run)')

    def handle(self, *args, **options):
        apply = options['apply']
        db_path = str(settings.DATABASES['default']['NAME'])

        self.stdout.write('')
        self.stdout.write('═' * 60)
        if apply:
            self.stdout.write('  FIX OLD DATABASE — APPLYING CHANGES')
        else:
            self.stdout.write('  FIX OLD DATABASE — DRY RUN (use --apply to fix)')
        self.stdout.write('═' * 60)
        self.stdout.write('')

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all existing tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        # Get existing columns for each table
        def get_columns(table):
            cursor.execute(f'PRAGMA table_info({table})')
            return {row[1] for row in cursor.fetchall()}

        fixes = []
        errors = []

        # Check each model
        for model in apps.get_models():
            table = model._meta.db_table
            if table.startswith('django_') or table.startswith('auth_') or table.startswith('sqlite_'):
                continue

            if table not in existing_tables:
                fixes.append(('TABLE', table, f'Table {table} is MISSING'))
                continue

            existing_cols = get_columns(table)

            for field in model._meta.get_fields():
                # Skip relations (reverse FKs, M2M)
                if not hasattr(field, 'column') or field.column is None:
                    continue

                col_name = field.column

                if col_name not in existing_cols:
                    # Determine SQL type and default
                    field_type = field.get_internal_type()
                    sql_type = {
                        'AutoField': 'INTEGER', 'BigAutoField': 'INTEGER',
                        'CharField': f'varchar({field.max_length})',
                        'TextField': 'TEXT',
                        'IntegerField': 'INTEGER', 'SmallIntegerField': 'INTEGER',
                        'BigIntegerField': 'bigint',
                        'DecimalField': 'decimal',
                        'FloatField': 'real',
                        'BooleanField': 'bool',
                        'DateField': 'date', 'DateTimeField': 'datetime',
                        'TimeField': 'time',
                        'EmailField': f'varchar({field.max_length})',
                        'URLField': f'varchar({field.max_length})',
                        'FileField': f'varchar({field.max_length})',
                        'ImageField': f'varchar({field.max_length})',
                        'ForeignKey': 'bigint', 'OneToOneField': 'bigint',
                    }.get(field_type, 'TEXT')

                    # Determine default value
                    if field.has_default():
                        default = field.default
                        if callable(default):
                            default = default()
                        if isinstance(default, bool):
                            default_sql = '1' if default else '0'
                        elif isinstance(default, (int, float)):
                            default_sql = str(default)
                        elif isinstance(default, str):
                            default_sql = f"'{default}'"
                        else:
                            default_sql = f"'{default}'"
                    elif field.null:
                        default_sql = 'NULL'
                    elif field_type in ('CharField', 'TextField', 'EmailField', 'URLField'):
                        default_sql = "''"
                    elif field_type in ('IntegerField', 'SmallIntegerField', 'BigIntegerField'):
                        default_sql = '0'
                    elif field_type in ('DecimalField', 'FloatField'):
                        default_sql = '0'
                    elif field_type == 'BooleanField':
                        default_sql = '0'
                    elif field_type in ('DateField', 'DateTimeField'):
                        default_sql = 'NULL' if field.null else "'2026-01-01'"
                    else:
                        default_sql = "''"

                    nullable = 'NULL' if field.null else 'NOT NULL'

                    sql = f'ALTER TABLE {table} ADD COLUMN {col_name} {sql_type} {nullable} DEFAULT {default_sql}'
                    fixes.append(('COLUMN', f'{table}.{col_name}', sql))

        # Report findings
        if not fixes:
            self.stdout.write(self.style.SUCCESS(
                '  ✅ Database schema is up-to-date — no fixes needed!\n'
                '     ڈیٹا بیس اسکیما بالکل درست ہے'
            ))
        else:
            self.stdout.write(f'  Found {len(fixes)} issue(s):\n')

            for fix_type, target, detail in fixes:
                if fix_type == 'TABLE':
                    self.stdout.write(self.style.WARNING(f'  ⚠️  MISSING TABLE: {target}'))
                    if apply:
                        self.stdout.write(self.style.ERROR(
                            f'     Cannot auto-create table {target}. Run: python manage.py migrate'
                        ))
                        errors.append(target)
                else:
                    self.stdout.write(f'  📝 MISSING COLUMN: {target}')
                    if apply:
                        try:
                            cursor.execute(detail)
                            self.stdout.write(self.style.SUCCESS(f'     ✅ Added: {detail}'))
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f'     ❌ Failed: {e}'))
                            errors.append(target)
                    else:
                        self.stdout.write(f'     SQL: {detail}')

            if apply:
                conn.commit()
                self.stdout.write('')
                if errors:
                    self.stdout.write(self.style.ERROR(
                        f'  ⚠️  {len(errors)} error(s). You may need to run: python manage.py migrate'
                    ))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✅ All {len(fixes)} fix(es) applied successfully!'
                    ))

        # Also check django_apscheduler tables
        if 'django_apscheduler_djangojob' not in existing_tables:
            self.stdout.write('')
            self.stdout.write('  ℹ️  django_apscheduler tables missing — this is OK if not using scheduled emails')
            self.stdout.write('     Run: python manage.py migrate django_apscheduler')

        conn.close()

        self.stdout.write('')
        self.stdout.write('═' * 60)
        self.stdout.write('')
