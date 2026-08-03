"""
Product Module Tests — Product CRUD, stock values, categories.
"""
from decimal import Decimal
from django.test import TestCase, Client
from apps.authentication.models import User
from apps.products.models import Product, Category, UnitOfMeasurement


class ProductModelTest(TestCase):

    def setUp(self):
        self.category = Category.objects.create(name='Cotton', code='CT')
        self.unit = UnitOfMeasurement.objects.create(
            name='Maund', abbreviation='Md', conversion_to_base=Decimal('40')
        )

    def test_stock_value_calculation(self):
        """Stock value = current_stock × default_purchase_price."""
        product = Product.objects.create(
            name='Phutti', code='PHT-SV-001', category=self.category,
            unit=self.unit, current_stock=Decimal('100'),
            default_purchase_price=Decimal('5000'),
        )
        self.assertEqual(product.stock_value, Decimal('500000'))

    def test_zero_stock_value(self):
        product = Product.objects.create(
            name='Empty', code='EMP-001', category=self.category,
            unit=self.unit, current_stock=Decimal('0'),
            default_purchase_price=Decimal('5000'),
        )
        self.assertEqual(product.stock_value, Decimal('0'))

    def test_low_stock_detection(self):
        """Product below minimum stock should be detectable."""
        product = Product.objects.create(
            name='Low Stock', code='LOW-001', category=self.category,
            unit=self.unit, current_stock=Decimal('5'),
            minimum_stock=Decimal('10'),
        )
        self.assertTrue(product.is_low_stock)


class ProductViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='admin', password='admin123456', first_name='Admin'
        )
        self.client.login(username='admin', password='admin123456')

    def test_product_list_page(self):
        response = self.client.get('/products/')
        self.assertEqual(response.status_code, 200)

    def test_product_create_page(self):
        response = self.client.get('/products/create/')
        self.assertEqual(response.status_code, 200)
