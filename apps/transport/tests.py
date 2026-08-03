"""
Transport Module Tests — Vehicles, freight, gate entries.
"""
from decimal import Decimal
from django.test import TestCase, Client
from apps.authentication.models import User
from apps.transport.models import Vehicle


class VehicleModelTest(TestCase):

    def test_vehicle_creation(self):
        v = Vehicle.objects.create(
            vehicle_number='BWP-1234', vehicle_type='truck',
            capacity_maund=Decimal('150'),
            driver_name='Muhammad Ali', driver_phone='0300-1234567',
        )
        self.assertIn('BWP-1234', str(v))
        self.assertTrue(v.is_active)

    def test_vehicle_unique_number(self):
        Vehicle.objects.create(vehicle_number='UNQ-001', vehicle_type='truck')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Vehicle.objects.create(vehicle_number='UNQ-001', vehicle_type='tractor')


class TransportViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='admin', password='admin123456', first_name='Admin'
        )
        self.client.login(username='admin', password='admin123456')

    def test_vehicle_list_page(self):
        response = self.client.get('/transport/vehicles/')
        self.assertEqual(response.status_code, 200)

    def test_vehicle_create_page(self):
        response = self.client.get('/transport/vehicles/create/')
        self.assertEqual(response.status_code, 200)

    def test_freight_list_page(self):
        response = self.client.get('/transport/freight/')
        self.assertEqual(response.status_code, 200)

    def test_gate_entry_list_page(self):
        response = self.client.get('/transport/gate/')
        self.assertEqual(response.status_code, 200)
