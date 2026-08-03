"""
Ginning Module Tests — Lots, GOT calculation, stock updates, bales.
"""
from decimal import Decimal
from django.test import TestCase, Client
from apps.authentication.models import User
from apps.products.models import Product, Category, UnitOfMeasurement
from apps.ginning.models import GinningLot, Bale


class GinningLotModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='test12345', first_name='Test'
        )
        self.category = Category.objects.create(name='Cotton', code='CT-G')
        self.unit = UnitOfMeasurement.objects.create(
            name='Maund', abbreviation='MdG', conversion_to_base=Decimal('40')
        )
        self.raw_cotton = Product.objects.create(
            name='Phutti', code='PHT-G001', category=self.category,
            unit=self.unit, current_stock=Decimal('500'),
        )
        self.lint = Product.objects.create(
            name='Lint', code='LNT-G001', category=self.category,
            unit=self.unit, current_stock=Decimal('0'),
        )
        self.seed = Product.objects.create(
            name='Seed', code='SED-G001', category=self.category,
            unit=self.unit, current_stock=Decimal('0'),
        )

    def test_lot_number_generation(self):
        num = GinningLot.generate_number()
        self.assertTrue(num.startswith('LOT-'))

    def test_got_calculation(self):
        lot = GinningLot(
            lot_number='LOT-TEST-0001', input_product=self.raw_cotton,
            input_quantity=Decimal('100'), input_unit=self.unit,
            lint_product=self.lint, lint_quantity=Decimal('35'),
            seed_product=self.seed, seed_quantity=Decimal('55'),
            created_by=self.user,
        )
        lot.calculate_got()
        self.assertEqual(lot.got_percentage, Decimal('35'))

    def test_lot_completion_updates_stock(self):
        """Completing a lot should reduce input stock and increase output stock."""
        lot = GinningLot.objects.create(
            lot_number='LOT-TEST-0002', input_product=self.raw_cotton,
            input_quantity=Decimal('100'), input_unit=self.unit,
            lint_product=self.lint, lint_quantity=Decimal('35'),
            seed_product=self.seed, seed_quantity=Decimal('55'),
            created_by=self.user,
        )
        lot.complete()
        self.raw_cotton.refresh_from_db()
        self.lint.refresh_from_db()
        self.seed.refresh_from_db()
        self.assertEqual(self.raw_cotton.current_stock, Decimal('400'))  # 500 - 100
        self.assertEqual(self.lint.current_stock, Decimal('35'))
        self.assertEqual(self.seed.current_stock, Decimal('55'))

    def test_total_cost_calculation(self):
        lot = GinningLot(
            lot_number='LOT-TEST-0003', input_product=self.raw_cotton,
            input_quantity=Decimal('100'), input_unit=self.unit,
            electricity_cost=Decimal('5000'), labour_cost=Decimal('3000'),
            maintenance_cost=Decimal('1000'), other_cost=Decimal('500'),
            created_by=self.user,
        )
        lot.calculate_got()
        self.assertEqual(lot.total_cost, Decimal('9500'))


class GinningViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='admin', password='admin123456', first_name='Admin'
        )
        self.client.login(username='admin', password='admin123456')

    def test_lot_list_page(self):
        response = self.client.get('/ginning/')
        self.assertEqual(response.status_code, 200)

    def test_lot_create_page(self):
        response = self.client.get('/ginning/create/')
        self.assertEqual(response.status_code, 200)

    def test_bale_register_page(self):
        response = self.client.get('/ginning/bales/')
        self.assertEqual(response.status_code, 200)
