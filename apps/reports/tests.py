"""
Reports Module Tests — All report pages load, CSV export, new reports.
"""
from decimal import Decimal
from django.test import TestCase, Client
from apps.authentication.models import User
from apps.parties.models import Party


def _make_party_with_balance(name, code, party_type, balance):
    party = Party.objects.create(name=name, code=code, party_type=party_type)
    Party.objects.filter(pk=party.pk).update(current_balance=balance)
    party.refresh_from_db()
    return party


class ReportViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='admin', password='admin123456', first_name='Admin'
        )
        self.client.login(username='admin', password='admin123456')

    def test_reports_index(self):
        r = self.client.get('/reports/')
        self.assertEqual(r.status_code, 200)

    def test_purchase_register(self):
        r = self.client.get('/reports/purchases/')
        self.assertEqual(r.status_code, 200)

    def test_sales_register(self):
        r = self.client.get('/reports/sales/')
        self.assertEqual(r.status_code, 200)

    def test_profit_loss(self):
        r = self.client.get('/reports/profit-loss/')
        self.assertEqual(r.status_code, 200)

    def test_day_book(self):
        r = self.client.get('/reports/day-book/')
        self.assertEqual(r.status_code, 200)

    def test_cash_book(self):
        r = self.client.get('/reports/cash-book/')
        self.assertEqual(r.status_code, 200)

    def test_payables(self):
        r = self.client.get('/reports/payables/')
        self.assertEqual(r.status_code, 200)

    def test_receivables(self):
        r = self.client.get('/reports/receivables/')
        self.assertEqual(r.status_code, 200)

    def test_stock_report(self):
        r = self.client.get('/reports/stock/')
        self.assertEqual(r.status_code, 200)

    def test_trial_balance(self):
        r = self.client.get('/reports/trial-balance/')
        self.assertEqual(r.status_code, 200)

    def test_monthly_comparison(self):
        r = self.client.get('/reports/monthly/')
        self.assertEqual(r.status_code, 200)

    def test_party_ledger(self):
        r = self.client.get('/reports/party-ledger/')
        self.assertEqual(r.status_code, 200)

    # New reports
    def test_aging_report(self):
        _make_party_with_balance('Aging Sup', 'AG-S1', 'supplier', Decimal('-50000'))
        _make_party_with_balance('Aging Cus', 'AG-C1', 'customer', Decimal('30000'))
        r = self.client.get('/reports/aging/')
        self.assertEqual(r.status_code, 200)

    def test_overdue_invoices(self):
        r = self.client.get('/reports/overdue/')
        self.assertEqual(r.status_code, 200)

    def test_expense_analysis(self):
        r = self.client.get('/reports/expense-analysis/')
        self.assertEqual(r.status_code, 200)

    # CSV exports
    def test_csv_purchases(self):
        r = self.client.get('/reports/export/purchases/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'text/csv')

    def test_csv_sales(self):
        r = self.client.get('/reports/export/sales/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'text/csv')

    def test_csv_stock(self):
        r = self.client.get('/reports/export/stock/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'text/csv')

    def test_stock_reconciliation(self):
        r = self.client.get('/reports/stock-reconciliation/')
        self.assertEqual(r.status_code, 200)

    def test_purchase_by_supplier(self):
        r = self.client.get('/reports/purchases/by-supplier/')
        self.assertEqual(r.status_code, 200)

    def test_sales_by_customer(self):
        r = self.client.get('/reports/sales/by-customer/')
        self.assertEqual(r.status_code, 200)

    def test_bank_book(self):
        r = self.client.get('/reports/bank-book/')
        self.assertEqual(r.status_code, 200)

    def test_broker_commission(self):
        r = self.client.get('/reports/broker-commission/')
        self.assertEqual(r.status_code, 200)

    def test_ginning_report(self):
        r = self.client.get('/reports/ginning/')
        self.assertEqual(r.status_code, 200)
