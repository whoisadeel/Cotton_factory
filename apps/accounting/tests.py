"""
Accounting Module Tests — Account CRUD, journal balancing, balance sheet.
"""
from decimal import Decimal
from django.test import TestCase, Client
from apps.authentication.models import User
from apps.accounting.models import AccountGroup, Account, JournalEntry, JournalLine


class AccountModelTest(TestCase):
    """Test Account model."""

    def setUp(self):
        self.group = AccountGroup.objects.create(
            name='Assets', code='1000', group_type='asset'
        )

    def test_account_creation(self):
        account = Account.objects.create(
            name='Cash', code='1001', group=self.group,
        )
        self.assertEqual(account.name, 'Cash')
        self.assertEqual(account.group.group_type, 'asset')
        self.assertTrue(account.is_active)


class JournalEntryTest(TestCase):
    """Test journal entry balancing."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='test12345', first_name='Test'
        )
        self.asset_group = AccountGroup.objects.create(
            name='Assets', code='1000', group_type='asset'
        )
        self.liability_group = AccountGroup.objects.create(
            name='Liabilities', code='2000', group_type='liability'
        )
        self.cash = Account.objects.create(name='Cash', code='1001', group=self.asset_group)
        self.payable = Account.objects.create(name='AP', code='2001', group=self.liability_group)

    def test_balanced_journal(self):
        """Journal with equal debits and credits should be balanced."""
        je = JournalEntry.objects.create(
            entry_number='JV-TEST-0001',
            date='2026-07-14',
            entry_type='journal',
            created_by=self.user,
        )
        JournalLine.objects.create(journal=je, account=self.cash, debit=Decimal('10000'), credit=Decimal('0'))
        JournalLine.objects.create(journal=je, account=self.payable, debit=Decimal('0'), credit=Decimal('10000'))
        self.assertTrue(je.is_balanced)

    def test_unbalanced_journal(self):
        """Journal with unequal debits/credits should not be balanced."""
        je = JournalEntry.objects.create(
            entry_number='JV-TEST-0002',
            date='2026-07-14',
            entry_type='journal',
            created_by=self.user,
        )
        JournalLine.objects.create(journal=je, account=self.cash, debit=Decimal('10000'), credit=Decimal('0'))
        JournalLine.objects.create(journal=je, account=self.payable, debit=Decimal('0'), credit=Decimal('5000'))
        self.assertFalse(je.is_balanced)


class AccountViewTest(TestCase):
    """Test account creation view (the bugfix)."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='admin', password='admin123456', first_name='Admin'
        )
        self.client.login(username='admin', password='admin123456')
        self.group = AccountGroup.objects.create(
            name='Assets', code='1000', group_type='asset'
        )

    def test_account_create_success(self):
        """Creating an account should NOT crash (the NameError bug)."""
        response = self.client.post('/accounting/account/create/', {
            'name': 'Test Account',
            'name_urdu': 'ٹیسٹ اکاؤنٹ',
            'code': 'TEST-001',
            'group': self.group.pk,
            'description': 'Test',
        })
        self.assertEqual(response.status_code, 302)  # Redirect on success
        self.assertTrue(Account.objects.filter(code='TEST-001').exists())

    def test_account_create_duplicate_code_rejected(self):
        """Duplicate account code should show error."""
        Account.objects.create(name='Existing', code='DUP-001', group=self.group)
        response = self.client.post('/accounting/account/create/', {
            'name': 'Duplicate', 'code': 'DUP-001',
            'group': self.group.pk,
        })
        self.assertEqual(response.status_code, 200)  # Re-renders form with error

    def test_account_create_empty_name_rejected(self):
        """Empty name should show error."""
        response = self.client.post('/accounting/account/create/', {
            'name': '', 'code': 'EMPTY-001',
            'group': self.group.pk,
        })
        self.assertEqual(response.status_code, 200)  # Re-renders form

    def test_chart_of_accounts_page(self):
        response = self.client.get('/accounting/chart/')
        self.assertEqual(response.status_code, 200)

    def test_journal_list_page(self):
        response = self.client.get('/accounting/journals/')
        self.assertEqual(response.status_code, 200)
