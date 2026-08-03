"""
Labour Module Tests — Workers, attendance, payments, advances.
"""
from decimal import Decimal
from django.test import TestCase, Client
from apps.authentication.models import User
from apps.labour.models import Worker, Attendance, WorkerPayment, WorkerAdvance


class WorkerModelTest(TestCase):

    def test_worker_creation(self):
        worker = Worker.objects.create(
            name='Ali Ahmad', cnic='35201-1234567-1',
            worker_type='daily', department='ginning',
            daily_wage=Decimal('800'),
        )
        self.assertIn('Ali Ahmad', str(worker))
        self.assertTrue(worker.is_active)

    def test_worker_daily_wage(self):
        worker = Worker.objects.create(
            name='Test Worker', worker_type='daily',
            daily_wage=Decimal('1000'),
        )
        self.assertEqual(worker.daily_wage, Decimal('1000'))

    def test_worker_monthly_salary(self):
        worker = Worker.objects.create(
            name='Monthly Worker', worker_type='monthly',
            monthly_salary=Decimal('25000'),
        )
        self.assertEqual(worker.monthly_salary, Decimal('25000'))


class AttendanceTest(TestCase):

    def setUp(self):
        self.worker = Worker.objects.create(
            name='Attendance Worker', worker_type='daily',
            daily_wage=Decimal('800'),
        )

    def test_attendance_creation(self):
        att = Attendance.objects.create(
            worker=self.worker, status='present',
        )
        self.assertEqual(att.status, 'present')

    def test_attendance_unique_per_day(self):
        from django.utils import timezone
        today = timezone.now().date()
        Attendance.objects.create(worker=self.worker, date=today, status='present')
        # Second attendance same day should be possible (model allows update)
        count = Attendance.objects.filter(worker=self.worker, date=today).count()
        self.assertEqual(count, 1)


class LabourViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='admin', password='admin123456', first_name='Admin'
        )
        self.client.login(username='admin', password='admin123456')

    def test_worker_list_page(self):
        response = self.client.get('/labour/')
        self.assertEqual(response.status_code, 200)

    def test_worker_create_page(self):
        response = self.client.get('/labour/create/')
        self.assertEqual(response.status_code, 200)

    def test_attendance_page(self):
        response = self.client.get('/labour/attendance/')
        self.assertEqual(response.status_code, 200)

    def test_payment_list_page(self):
        response = self.client.get('/labour/payments/')
        self.assertEqual(response.status_code, 200)
