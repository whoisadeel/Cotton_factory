"""
Finance Module Tests — Covers payment/receipt finalization,
party balance updates, void operations, and balance conventions.
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from apps.authentication.models import User
from apps.parties.models import Party
from apps.finance.models import PaymentVoucher, ReceiptVoucher, Expense


def _make_party_with_balance(name, code, party_type, balance):
    """Create a party and force-set current_balance (bypassing save() override)."""
    party = Party.objects.create(name=name, code=code, party_type=party_type)
    Party.objects.filter(pk=party.pk).update(current_balance=balance)
    party.refresh_from_db()
    return party


class PaymentModelTest(TestCase):
    """Test PaymentVoucher model logic."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='test12345', first_name='Test', last_name='User'
        )
        self.supplier = _make_party_with_balance(
            'Test Supplier', 'SUP-FIN-001', 'supplier', Decimal('-50000')
        )

    def test_voucher_number_auto_generated(self):
        """Voucher number should be auto-generated."""
        pv = PaymentVoucher(party=self.supplier, amount=Decimal('10000'), created_by=self.user)
        pv.save()
        self.assertTrue(pv.voucher_number.startswith('PAY-'))

    def test_finalize_updates_status(self):
        pv = PaymentVoucher(party=self.supplier, amount=Decimal('10000'), created_by=self.user)
        pv.save()
        pv.finalize()
        self.assertEqual(pv.status, 'final')

    def test_payment_increases_supplier_balance(self):
        """Payment should increase supplier balance toward 0 (reduce debt)."""
        pv = PaymentVoucher(party=self.supplier, amount=Decimal('10000'), created_by=self.user)
        pv.save()
        pv.finalize()
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.current_balance, Decimal('-40000'))

    def test_payment_full_settlement(self):
        """Full payment should bring balance to 0."""
        pv = PaymentVoucher(party=self.supplier, amount=Decimal('50000'), created_by=self.user)
        pv.save()
        pv.finalize()
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.current_balance, Decimal('0'))

    def test_overpayment_makes_positive(self):
        """Overpayment should make supplier balance positive (they owe us)."""
        pv = PaymentVoucher(party=self.supplier, amount=Decimal('60000'), created_by=self.user)
        pv.save()
        pv.finalize()
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.current_balance, Decimal('10000'))


class ReceiptModelTest(TestCase):
    """Test ReceiptVoucher model logic."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='test12345', first_name='Test', last_name='User'
        )
        self.customer = _make_party_with_balance(
            'Test Customer', 'CUS-FIN-001', 'customer', Decimal('70000')
        )

    def test_receipt_decreases_customer_balance(self):
        """Receipt should decrease customer balance (reduce receivable)."""
        rv = ReceiptVoucher(party=self.customer, amount=Decimal('20000'), created_by=self.user)
        rv.save()
        rv.finalize()
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.current_balance, Decimal('50000'))

    def test_receipt_full_settlement(self):
        """Full receipt should bring balance to 0."""
        rv = ReceiptVoucher(party=self.customer, amount=Decimal('70000'), created_by=self.user)
        rv.save()
        rv.finalize()
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.current_balance, Decimal('0'))

    def test_overpayment_by_customer(self):
        """Customer overpayment should make balance negative (we owe them)."""
        rv = ReceiptVoucher(party=self.customer, amount=Decimal('80000'), created_by=self.user)
        rv.save()
        rv.finalize()
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.current_balance, Decimal('-10000'))


class BalanceConventionTest(TestCase):
    """
    End-to-end balance convention test.

    Convention:
        Positive balance = Dr = They owe us (receivable)
        Negative balance = Cr = We owe them (payable)
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='test12345', first_name='Test', last_name='User'
        )

    def test_supplier_lifecycle(self):
        """Full supplier lifecycle: purchase → payment → zero balance."""
        supplier = Party.objects.create(
            name='Lifecycle Supplier', code='SUP-LC-001', party_type='supplier',
        )
        self.assertEqual(supplier.current_balance, Decimal('0'))

        # Simulate purchase finalize: balance -= 100,000
        Party.objects.filter(pk=supplier.pk).update(
            current_balance=supplier.current_balance - Decimal('100000')
        )
        supplier.refresh_from_db()
        self.assertEqual(supplier.current_balance, Decimal('-100000'))

        # Simulate payment finalize: balance += 100,000
        Party.objects.filter(pk=supplier.pk).update(
            current_balance=supplier.current_balance + Decimal('100000')
        )
        supplier.refresh_from_db()
        self.assertEqual(supplier.current_balance, Decimal('0'))

    def test_customer_lifecycle(self):
        """Full customer lifecycle: sale → receipt → zero balance."""
        customer = Party.objects.create(
            name='Lifecycle Customer', code='CUS-LC-001', party_type='customer',
        )
        self.assertEqual(customer.current_balance, Decimal('0'))

        # Simulate sale finalize: balance += 200,000
        Party.objects.filter(pk=customer.pk).update(
            current_balance=customer.current_balance + Decimal('200000')
        )
        customer.refresh_from_db()
        self.assertEqual(customer.current_balance, Decimal('200000'))

        # Simulate receipt finalize: balance -= 200,000
        Party.objects.filter(pk=customer.pk).update(
            current_balance=customer.current_balance - Decimal('200000')
        )
        customer.refresh_from_db()
        self.assertEqual(customer.current_balance, Decimal('0'))


class PaymentViewTest(TestCase):
    """Test payment views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='admin', password='admin123456', first_name='Admin'
        )
        self.client.login(username='admin', password='admin123456')

    def test_payment_list_page(self):
        response = self.client.get('/finance/payments/')
        self.assertEqual(response.status_code, 200)

    def test_receipt_list_page(self):
        response = self.client.get('/finance/receipts/')
        self.assertEqual(response.status_code, 200)

    def test_expense_list_page(self):
        response = self.client.get('/finance/expenses/')
        self.assertEqual(response.status_code, 200)

    def test_cheque_list_page(self):
        response = self.client.get('/finance/cheques/')
        self.assertEqual(response.status_code, 200)

    def test_bank_account_list_page(self):
        response = self.client.get('/finance/bank-accounts/')
        self.assertEqual(response.status_code, 200)


class VoidTest(TestCase):
    """Test void operations reverse balance correctly."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='admin', password='admin123456', first_name='Admin'
        )
        self.client = Client()
        self.client.login(username='admin', password='admin123456')

    def test_payment_void_reverses_balance(self):
        """Voiding a finalized payment should reverse the balance change."""
        supplier = _make_party_with_balance(
            'Void Supplier', 'SUP-VOID-001', 'supplier', Decimal('-50000')
        )
        pv = PaymentVoucher(party=supplier, amount=Decimal('20000'), created_by=self.user)
        pv.save()
        pv.finalize()
        supplier.refresh_from_db()
        self.assertEqual(supplier.current_balance, Decimal('-30000'))

        # Void via view
        response = self.client.post(f'/finance/payments/{pv.pk}/void/')
        supplier.refresh_from_db()
        pv.refresh_from_db()
        self.assertEqual(pv.status, 'void')
        self.assertEqual(supplier.current_balance, Decimal('-50000'))  # Restored

    def test_receipt_void_reverses_balance(self):
        """Voiding a finalized receipt should reverse the balance change."""
        customer = _make_party_with_balance(
            'Void Customer', 'CUS-VOID-001', 'customer', Decimal('70000')
        )
        rv = ReceiptVoucher(party=customer, amount=Decimal('30000'), created_by=self.user)
        rv.save()
        rv.finalize()
        customer.refresh_from_db()
        self.assertEqual(customer.current_balance, Decimal('40000'))

        response = self.client.post(f'/finance/receipts/{rv.pk}/void/')
        customer.refresh_from_db()
        rv.refresh_from_db()
        self.assertEqual(rv.status, 'void')
        self.assertEqual(customer.current_balance, Decimal('70000'))  # Restored
