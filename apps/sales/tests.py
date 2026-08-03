"""
Sale Module Tests — Covers sale creation, finalization,
stock reduction, negative stock prevention, and customer balance.
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from apps.authentication.models import User
from apps.parties.models import Party
from apps.products.models import Product, Category, UnitOfMeasurement
from apps.sales.models import Sale, SaleItem


class SaleModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='test12345', first_name='Test', last_name='User'
        )
        self.customer = Party.objects.create(
            name='Test Customer', code='CUS-TEST-001', party_type='customer',
        )
        self.category = Category.objects.create(name='Cotton Lint', code='CL')
        self.unit = UnitOfMeasurement.objects.create(
            name='Maund', abbreviation='Md', conversion_to_base=Decimal('40')
        )
        self.product = Product.objects.create(
            name='Rooi', code='ROO-001', category=self.category,
            unit=self.unit, current_stock=Decimal('100'),
            default_purchase_price=Decimal('5000'), default_sale_price=Decimal('7000'),
        )

    def test_sale_number_auto_generated(self):
        sale = Sale(customer=self.customer, created_by=self.user)
        sale.save()
        self.assertTrue(sale.invoice_number.startswith('INV-'))

    def test_sale_starts_as_draft(self):
        sale = Sale(customer=self.customer, created_by=self.user)
        sale.save()
        self.assertEqual(sale.status, 'draft')

    def test_finalize_updates_stock(self):
        sale = Sale(customer=self.customer, created_by=self.user)
        sale.save()
        SaleItem.objects.create(
            sale=sale, product=self.product, unit=self.unit,
            quantity=Decimal('10'), rate=Decimal('7000'),
        )
        sale.finalize()
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal('90'))

    def test_finalize_updates_customer_balance(self):
        sale = Sale(customer=self.customer, created_by=self.user)
        sale.save()
        SaleItem.objects.create(
            sale=sale, product=self.product, unit=self.unit,
            quantity=Decimal('10'), rate=Decimal('7000'),
        )
        sale.finalize()
        self.customer.refresh_from_db()
        self.assertGreater(self.customer.current_balance, Decimal('0'))

    def test_balance_convention_sale(self):
        """Sale should increase customer balance (positive = they owe us)."""
        sale = Sale(customer=self.customer, created_by=self.user)
        sale.save()
        SaleItem.objects.create(
            sale=sale, product=self.product, unit=self.unit,
            quantity=Decimal('10'), rate=Decimal('7000'),
        )
        sale.finalize()
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.current_balance, Decimal('70000'))

    def test_recalculate_totals(self):
        sale = Sale(customer=self.customer, created_by=self.user)
        sale.save()
        SaleItem.objects.create(
            sale=sale, product=self.product, unit=self.unit,
            quantity=Decimal('10'), rate=Decimal('7000'),
        )
        sale.recalculate()
        self.assertEqual(sale.subtotal, Decimal('70000'))
        self.assertEqual(sale.grand_total, Decimal('70000'))


class SaleViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='admin', password='admin123456', first_name='Admin'
        )
        self.client.login(username='admin', password='admin123456')
        self.customer = Party.objects.create(
            name='View Test Customer', code='CUS-VT-001', party_type='customer',
        )
        self.category = Category.objects.create(name='Cotton', code='CT')
        self.unit = UnitOfMeasurement.objects.create(
            name='Maund', abbreviation='Md', conversion_to_base=Decimal('40')
        )
        self.product = Product.objects.create(
            name='Rooi', code='ROO-VT-001', category=self.category,
            unit=self.unit, current_stock=Decimal('50'),
        )

    def test_sale_list_page(self):
        response = self.client.get('/sales/')
        self.assertEqual(response.status_code, 200)

    def test_finalize_empty_sale_rejected(self):
        sale = Sale(customer=self.customer, created_by=self.user)
        sale.save()
        response = self.client.post(f'/sales/{sale.pk}/finalize/')
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'draft')

    def test_negative_stock_prevention(self):
        """Cannot finalize sale that would cause negative stock."""
        from apps.settings_app.models import CompanySettings
        settings = CompanySettings.get_settings()
        if hasattr(settings, 'negative_stock_allowed'):
            settings.negative_stock_allowed = False
            settings.save()

        sale = Sale(customer=self.customer, created_by=self.user)
        sale.save()
        SaleItem.objects.create(
            sale=sale, product=self.product, unit=self.unit,
            quantity=Decimal('999'), rate=Decimal('7000'),
        )
        response = self.client.post(f'/sales/{sale.pk}/finalize/')
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'draft')
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal('50'))
