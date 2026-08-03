"""
Authentication Tests — Login, logout, audit logging, security.
"""
from django.test import TestCase, Client
from apps.authentication.models import User, AuditLog


class LoginTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='admin', password='admin123456', first_name='Admin', last_name='User'
        )

    def test_login_page_loads(self):
        response = self.client.get('/auth/login/')
        self.assertEqual(response.status_code, 200)

    def test_valid_login(self):
        response = self.client.post('/auth/login/', {
            'username': 'admin', 'password': 'admin123456'
        })
        self.assertEqual(response.status_code, 302)  # Redirect on success

    def test_invalid_login(self):
        response = self.client.post('/auth/login/', {
            'username': 'admin', 'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)  # Re-renders form

    def test_logout(self):
        self.client.login(username='admin', password='admin123456')
        response = self.client.post('/auth/logout/')  # POST-only for CSRF safety
        self.assertIn(response.status_code, [200, 302])

    def test_unauthenticated_redirect(self):
        """Unauthenticated users should be redirected to login."""
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


class AuditLogTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='admin', password='admin123456', first_name='Admin'
        )

    def test_audit_log_creation(self):
        AuditLog.log(
            user=self.user, action='CREATE', model_name='Test',
            object_id=1, object_repr='Test Object',
        )
        self.assertEqual(AuditLog.objects.count(), 1)

    def test_audit_log_fields(self):
        AuditLog.log(
            user=self.user, action='UPDATE', model_name='Party',
            object_id=42, object_repr='Test Party',
            description='Updated phone number',
        )
        log = AuditLog.objects.first()
        self.assertEqual(log.action, 'UPDATE')
        self.assertEqual(log.model_name, 'Party')
        self.assertEqual(str(log.object_id), '42')
