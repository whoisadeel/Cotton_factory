"""
Settings Module Tests — Company settings, financial year, management commands.
"""
from django.test import TestCase, Client
from apps.authentication.models import User
from apps.settings_app.models import CompanySettings, FinancialYear


class CompanySettingsTest(TestCase):

    def test_get_settings_creates_default(self):
        """get_settings() should create a default entry if none exists."""
        settings = CompanySettings.get_settings()
        self.assertIsNotNone(settings)
        self.assertEqual(settings.currency, 'PKR')

    def test_singleton_enforcement(self):
        """Only one CompanySettings should exist."""
        s1 = CompanySettings.get_settings()
        s2 = CompanySettings.get_settings()
        self.assertEqual(s1.pk, s2.pk)

    def test_default_values(self):
        settings = CompanySettings.get_settings()
        self.assertEqual(settings.currency_symbol, '₨')
        self.assertEqual(settings.maund_to_kg, 40)


class SettingsViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='admin', password='admin123456', first_name='Admin'
        )
        self.client.login(username='admin', password='admin123456')

    def test_settings_page(self):
        response = self.client.get('/settings/')
        self.assertEqual(response.status_code, 200)


class ManagementCommandTest(TestCase):
    """Test management commands run without errors."""

    def test_health_check_runs(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('health_check', stdout=out)
        output = out.getvalue()
        self.assertIn('Database connection', output)

    def test_backup_db_runs(self):
        """Backup command should run — may skip if test DB is in-memory."""
        from django.core.management import call_command
        from django.conf import settings
        from io import StringIO
        import os
        db_path = settings.DATABASES['default']['NAME']
        if not os.path.exists(str(db_path)):
            # In-memory test DB — just verify command doesn't crash
            out = StringIO()
            err = StringIO()
            call_command('backup_db', stdout=out, stderr=err)
            return
        out = StringIO()
        call_command('backup_db', stdout=out)
        output = out.getvalue()
        self.assertIn('Backup created', output)

    def test_recalculate_balances_dry_run(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('recalculate_balances', dry_run=True, stdout=out)
        output = out.getvalue()
        self.assertIn('Recalculating', output)
