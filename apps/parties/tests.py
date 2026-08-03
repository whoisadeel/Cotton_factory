"""
Party Module Tests — Creation, balance conventions, opening balance, CNIC validation.
"""
from decimal import Decimal
from django.test import TestCase, Client
from apps.authentication.models import User
from apps.parties.models import Party


class PartyModelTest(TestCase):
    """Test Party model logic."""

    def test_opening_balance_debit(self):
        """Debit opening balance should set positive current_balance."""
        party = Party.objects.create(
            name='Debit Party', code='PTY-DB-001',
            party_type='customer',
            opening_balance=Decimal('25000'),
            opening_balance_type='debit',
        )
        self.assertEqual(party.current_balance, Decimal('25000'))

    def test_opening_balance_credit(self):
        """Credit opening balance should set negative current_balance."""
        party = Party.objects.create(
            name='Credit Party', code='PTY-CR-001',
            party_type='supplier',
            opening_balance=Decimal('50000'),
            opening_balance_type='credit',
        )
        self.assertEqual(party.current_balance, Decimal('-50000'))

    def test_balance_display_debit(self):
        party = Party(name='Test', code='T1', current_balance=Decimal('10000'))
        self.assertIn('Dr', party.balance_display)

    def test_balance_display_credit(self):
        party = Party(name='Test', code='T2', current_balance=Decimal('-10000'))
        self.assertIn('Cr', party.balance_display)

    def test_balance_display_zero(self):
        party = Party(name='Test', code='T3', current_balance=Decimal('0'))
        self.assertIn('0.00', party.balance_display)

    def test_auto_code_generation(self):
        """Code generator should produce unique codes."""
        code1 = Party.generate_code('supplier')
        self.assertTrue(code1.startswith('SUP-'))
        Party.objects.create(name='Auto1', code=code1, party_type='supplier')
        code2 = Party.generate_code('supplier')
        self.assertNotEqual(code1, code2)

    def test_credit_limit_supplier(self):
        """Supplier is over credit limit when negative balance exceeds limit."""
        party = Party(
            name='Test', code='T4', party_type='supplier',
            current_balance=Decimal('-100000'),
            credit_limit=Decimal('50000'),
        )
        self.assertTrue(party.is_over_credit_limit)

    def test_credit_limit_customer(self):
        """Customer is over credit limit when positive balance exceeds limit."""
        party = Party(
            name='Test', code='T5', party_type='customer',
            current_balance=Decimal('100000'),
            credit_limit=Decimal('50000'),
        )
        self.assertTrue(party.is_over_credit_limit)

    def test_not_over_credit_limit(self):
        """Within credit limit should return False."""
        party = Party(
            name='Test', code='T6', party_type='customer',
            current_balance=Decimal('10000'),
            credit_limit=Decimal('50000'),
        )
        self.assertFalse(party.is_over_credit_limit)


class PartyViewTest(TestCase):
    """Test party views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='admin', password='admin123456', first_name='Admin'
        )
        self.client.login(username='admin', password='admin123456')

    def test_party_list_page(self):
        response = self.client.get('/parties/')
        self.assertEqual(response.status_code, 200)

    def test_party_create_page(self):
        response = self.client.get('/parties/create/')
        self.assertEqual(response.status_code, 200)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get('/parties/')
        self.assertEqual(response.status_code, 302)
