"""
Purchase Module Tests — Covers purchase creation, finalization,
stock updates, supplier balance, and return workflows.
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from apps.authentication.models import User
from apps.parties.models import Party
from apps.products.models import Product, Category, UnitOfMeasurement
from apps.purchases.models import Purchase, PurchaseItem
from apps.inventory.models import StockMovement


class PurchaseModelTest(TestCase):
    """Test Purchase model logic."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='test12345', first_name='Test', last_name='User'
        )
        self.supplier = Party.objects.create(
            name='Test Supplier', code='SUP-TEST-001', party_type='supplier',
        )
        self.category = Category.objects.create(name='Raw Cotton', code='RC')
        self.unit = UnitOfMeasurement.objects.create(
            name='Maund', abbreviation='Md', conversion_to_base=Decimal('40')
        )
        self.product = Product.objects.create(
            name='Phutti', code='PHT-001', category=self.category,
            unit=self.unit, current_stock=Decimal('0'),
            default_purchase_price=Decimal('5000'), default_sale_price=Decimal('7000'),
        )

    def test_purchase_number_auto_generated(self):
        purchase = Purchase(supplier=self.supplier, created_by=self.user, date=timezone.now().date())
        purchase.save()
        self.assertTrue(purchase.purchase_number.startswith('PUR-'))

    def test_purchase_number_unique(self):
        p1 = Purchase(supplier=self.supplier, created_by=self.user)
        p1.save()
        p2 = Purchase(supplier=self.supplier, created_by=self.user)
        p2.save()
        self.assertNotEqual(p1.purchase_number, p2.purchase_number)

    def test_purchase_starts_as_draft(self):
        purchase = Purchase(supplier=self.supplier, created_by=self.user)
        purchase.save()
        self.assertEqual(purchase.status, 'draft')

    def test_recalculate_totals(self):
        purchase = Purchase(supplier=self.supplier, created_by=self.user)
        purchase.save()
        PurchaseItem.objects.create(
            purchase=purchase, product=self.product, unit=self.unit,
            quantity=Decimal('10'), rate=Decimal('5000'),
        )
        PurchaseItem.objects.create(
            purchase=purchase, product=self.product, unit=self.unit,
            quantity=Decimal('5'), rate=Decimal('6000'),
        )
        purchase.recalculate()
        self.assertEqual(purchase.subtotal, Decimal('80000'))
        self.assertEqual(purchase.grand_total, Decimal('80000'))

    def test_recalculate_with_charges(self):
        purchase = Purchase(
            supplier=self.supplier, created_by=self.user,
            freight_charges=Decimal('2000'), hamali_charges=Decimal('500'),
        )
        purchase.save()
        PurchaseItem.objects.create(
            purchase=purchase, product=self.product, unit=self.unit,
            quantity=Decimal('10'), rate=Decimal('5000'),
        )
        purchase.recalculate()
        self.assertEqual(purchase.grand_total, Decimal('52500'))

    def test_recalculate_with_discount(self):
        purchase = Purchase(
            supplier=self.supplier, created_by=self.user,
            total_discount=Decimal('1000'),
        )
        purchase.save()
        PurchaseItem.objects.create(
            purchase=purchase, product=self.product, unit=self.unit,
            quantity=Decimal('10'), rate=Decimal('5000'),
        )
        purchase.recalculate()
        self.assertEqual(purchase.grand_total, Decimal('49000'))

    def test_finalize_updates_status(self):
        purchase = Purchase(supplier=self.supplier, created_by=self.user)
        purchase.save()
        PurchaseItem.objects.create(
            purchase=purchase, product=self.product, unit=self.unit,
            quantity=Decimal('10'), rate=Decimal('5000'),
        )
        purchase.finalize()
        self.assertEqual(purchase.status, 'final')
        self.assertIsNotNone(purchase.finalized_at)

    def test_finalize_updates_stock(self):
        self.assertEqual(self.product.current_stock, Decimal('0'))
        purchase = Purchase(supplier=self.supplier, created_by=self.user)
        purchase.save()
        PurchaseItem.objects.create(
            purchase=purchase, product=self.product, unit=self.unit,
            quantity=Decimal('10'), rate=Decimal('5000'),
        )
        purchase.finalize()
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal('10'))

    def test_finalize_creates_stock_movement(self):
        purchase = Purchase(supplier=self.supplier, created_by=self.user)
        purchase.save()
        PurchaseItem.objects.create(
            purchase=purchase, product=self.product, unit=self.unit,
            quantity=Decimal('10'), rate=Decimal('5000'),
        )
        purchase.finalize()
        movements = StockMovement.objects.filter(product=self.product)
        self.assertTrue(movements.exists())

    def test_finalize_updates_supplier_balance(self):
        purchase = Purchase(supplier=self.supplier, created_by=self.user)
        purchase.save()
        PurchaseItem.objects.create(
            purchase=purchase, product=self.product, unit=self.unit,
            quantity=Decimal('10'), rate=Decimal('5000'),
        )
        purchase.finalize()
        self.supplier.refresh_from_db()
        self.assertLess(self.supplier.current_balance, Decimal('0'))

    def test_balance_convention_purchase(self):
        """Purchase should decrease supplier balance (negative = we owe them)."""
        purchase = Purchase(supplier=self.supplier, created_by=self.user)
        purchase.save()
        PurchaseItem.objects.create(
            purchase=purchase, product=self.product, unit=self.unit,
            quantity=Decimal('10'), rate=Decimal('5000'),
        )
        purchase.finalize()
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.current_balance, Decimal('-50000'))


class PurchaseViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='admin', password='admin123456', first_name='Admin'
        )
        self.client.login(username='admin', password='admin123456')
        self.supplier = Party.objects.create(
            name='View Test Supplier', code='SUP-VT-001', party_type='supplier',
        )
        self.category = Category.objects.create(name='Cotton', code='CT')
        self.unit = UnitOfMeasurement.objects.create(
            name='Maund', abbreviation='Md', conversion_to_base=Decimal('40')
        )
        self.product = Product.objects.create(
            name='Phutti', code='PHT-VT-001', category=self.category,
            unit=self.unit, current_stock=Decimal('100'),
        )

    def test_purchase_list_page(self):
        response = self.client.get('/purchases/')
        self.assertEqual(response.status_code, 200)

    def test_purchase_create_page(self):
        """Purchase create auto-creates draft and redirects to editor."""
        response = self.client.get('/purchases/create/')
        self.assertIn(response.status_code, [200, 302])

    def test_finalize_empty_purchase_rejected(self):
        purchase = Purchase(supplier=self.supplier, created_by=self.user)
        purchase.save()
        response = self.client.post(f'/purchases/{purchase.pk}/finalize/')
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, 'draft')

    def test_finalize_draft_purchase(self):
        purchase = Purchase(supplier=self.supplier, created_by=self.user)
        purchase.save()
        PurchaseItem.objects.create(
            purchase=purchase, product=self.product, unit=self.unit,
            quantity=Decimal('5'), rate=Decimal('5000'),
        )
        response = self.client.post(f'/purchases/{purchase.pk}/finalize/')
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, 'final')

    def test_cannot_finalize_already_final(self):
        purchase = Purchase(supplier=self.supplier, created_by=self.user)
        purchase.save()
        PurchaseItem.objects.create(
            purchase=purchase, product=self.product, unit=self.unit,
            quantity=Decimal('5'), rate=Decimal('5000'),
        )
        purchase.finalize()
        response = self.client.post(f'/purchases/{purchase.pk}/finalize/')
        self.assertEqual(response.status_code, 302)

    def test_delete_draft_purchase(self):
        purchase = Purchase(supplier=self.supplier, created_by=self.user)
        purchase.save()
        pk = purchase.pk
        response = self.client.post(f'/purchases/{pk}/delete/')
        self.assertFalse(Purchase.objects.filter(pk=pk).exists())

    def test_login_required(self):
        self.client.logout()
        response = self.client.get('/purchases/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
