"""
Dashboard Tests — Page load, balance calculations, search.
"""
from decimal import Decimal
from django.test import TestCase, Client
from apps.authentication.models import User
from apps.parties.models import Party


def _make_party_with_balance(name, code, party_type, balance):
    """Create a party and force-set current_balance (bypassing save() override)."""
    party = Party.objects.create(name=name, code=code, party_type=party_type)
    Party.objects.filter(pk=party.pk).update(current_balance=balance)
    party.refresh_from_db()
    return party


class DashboardViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='admin', password='admin123456', first_name='Admin'
        )
        self.client.login(username='admin', password='admin123456')

    def test_dashboard_loads(self):
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)

    def test_dashboard_shows_correct_payables(self):
        """Payables = parties with negative balance (we owe them)."""
        _make_party_with_balance('Owed Supplier', 'SUP-DASH-001', 'supplier', Decimal('-100000'))
        _make_party_with_balance('Overpaid Supplier', 'SUP-DASH-002', 'supplier', Decimal('5000'))
        response = self.client.get('/dashboard/')
        payables = response.context['total_payables']
        # Only the negative-balance supplier should count
        self.assertEqual(payables, Decimal('100000'))

    def test_dashboard_shows_correct_receivables(self):
        """Receivables = parties with positive balance (they owe us)."""
        _make_party_with_balance('Owing Customer', 'CUS-DASH-001', 'customer', Decimal('50000'))
        _make_party_with_balance('Overpaid Customer', 'CUS-DASH-002', 'customer', Decimal('-10000'))
        response = self.client.get('/dashboard/')
        receivables = response.context['total_receivables']
        # Only the positive-balance customer should count
        self.assertEqual(receivables, Decimal('50000'))

    def test_global_search(self):
        Party.objects.create(name='Searchable Party', code='SRCH-001', party_type='supplier')
        response = self.client.get('/dashboard/search/?q=Searchable')
        self.assertEqual(response.status_code, 200)

    def test_global_search_short_query(self):
        response = self.client.get('/dashboard/search/?q=x')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['results']), 0)
