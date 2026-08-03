"""Seed Chart of Accounts for cotton factory."""
from django.core.management.base import BaseCommand
from apps.accounting.models import AccountGroup, Account


class Command(BaseCommand):
    help = 'Seed chart of accounts for cotton factory'

    def handle(self, *args, **options):
        groups_data = [
            ('100', 'Assets', 'اثاثے', 'asset', [
                ('1001', 'Cash in Hand', 'ہاتھ میں نقدی'),
                ('1002', 'Bank Accounts', 'بینک اکاؤنٹس'),
                ('1003', 'Accounts Receivable', 'واجب الوصول'),
                ('1004', 'Stock / Inventory', 'اسٹاک'),
                ('1005', 'Fixed Assets', 'مقررہ اثاثے'),
                ('1006', 'Advances Given', 'دی گئی پیشگی'),
            ]),
            ('200', 'Liabilities', 'واجبات', 'liability', [
                ('2001', 'Accounts Payable', 'واجب الادا'),
                ('2002', 'Loans', 'قرضے'),
                ('2003', 'Advances Received', 'وصول شدہ پیشگی'),
                ('2004', 'Sales Tax Payable', 'سیلز ٹیکس'),
                ('2005', 'WHT Payable', 'ود ہولڈنگ ٹیکس'),
            ]),
            ('300', 'Capital', 'سرمایہ', 'capital', [
                ('3001', "Owner's Equity", 'مالک کا سرمایہ'),
                ('3002', "Owner's Drawings", 'مالک کی نکاسی'),
                ('3003', 'Retained Earnings', 'برقرار آمدنی'),
            ]),
            ('400', 'Income', 'آمدنی', 'income', [
                ('4001', 'Sales - Cotton Lint', 'فروخت - روئی'),
                ('4002', 'Sales - Cotton Seed', 'فروخت - بنولہ'),
                ('4003', 'Sales - Waste', 'فروخت - جھاڑ'),
                ('4004', 'Commission Income', 'کمیشن آمدنی'),
                ('4005', 'Other Income', 'دیگر آمدنی'),
            ]),
            ('500', 'Cost of Goods', 'تجارتی لاگت', 'expense', [
                ('5001', 'Purchases - Raw Cotton', 'خریداری - پھٹی'),
                ('5002', 'Purchases - Other', 'خریداری - دیگر'),
                ('5003', 'Freight Inward', 'آمد بھاڑا'),
                ('5004', 'Commission Paid', 'ادا شدہ کمیشن'),
                ('5005', 'Bardana Charges', 'بردانہ'),
                ('5006', 'Hamali / Loading', 'حمالی'),
                ('5007', 'Tulai / Weighing', 'تلائی'),
                ('5008', 'Mandi Fee', 'منڈی فیس'),
            ]),
            ('600', 'Operating Expenses', 'آپریٹنگ اخراجات', 'expense', [
                ('6001', 'Electricity', 'بجلی'),
                ('6002', 'Gas / Fuel', 'گیس'),
                ('6003', 'Diesel', 'ڈیزل'),
                ('6004', 'Salaries & Wages', 'تنخواہ اور اجرت'),
                ('6005', 'Daily Labour', 'مزدوری'),
                ('6006', 'Repair & Maintenance', 'مرمت'),
                ('6007', 'Spare Parts', 'پرزے'),
                ('6008', 'Transportation', 'نقل و حمل'),
                ('6009', 'Office Supplies', 'دفتری سامان'),
                ('6010', 'Communication', 'فون / انٹرنیٹ'),
                ('6011', 'Rent', 'کرایہ'),
                ('6012', 'Insurance', 'بیمہ'),
                ('6013', 'Legal & Professional', 'قانونی'),
                ('6014', 'Govt Fees & Taxes', 'سرکاری فیس'),
                ('6015', 'Entertainment', 'مہمان نوازی'),
                ('6016', 'Miscellaneous', 'متفرق'),
            ]),
        ]

        for g_code, g_name, g_urdu, g_type, accounts in groups_data:
            group, created = AccountGroup.objects.get_or_create(
                code=g_code,
                defaults={'name': g_name, 'name_urdu': g_urdu, 'group_type': g_type, 'is_system': True}
            )
            self.stdout.write(f"  {'Created' if created else 'Exists'}: Group {g_code} — {g_name}")
            for a_code, a_name, a_urdu in accounts:
                _, a_created = Account.objects.get_or_create(
                    code=a_code,
                    defaults={'name': a_name, 'name_urdu': a_urdu, 'group': group, 'is_system': True}
                )
                if a_created:
                    self.stdout.write(f"    Created: {a_code} — {a_name}")

        self.stdout.write(self.style.SUCCESS('\n✓ Chart of Accounts seeded!'))
