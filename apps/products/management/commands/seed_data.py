"""
Management command to seed initial data for the cotton factory.
Creates default categories, units, and company settings.
"""
from django.core.management.base import BaseCommand
from apps.products.models import Category, UnitOfMeasurement
from apps.settings_app.models import CompanySettings, FinancialYear
from datetime import date


class Command(BaseCommand):
    help = 'Seed initial data for Cotton Factory (categories, units, settings)'

    def handle(self, *args, **options):
        self.stdout.write('Seeding initial data...\n')

        # ── Categories ──
        categories = [
            {'name': 'Raw Cotton (Phutti)', 'name_urdu': 'کچی روئی / پھٹی', 'code': 'PHUTTI', 'sort_order': 1},
            {'name': 'Cotton Lint (Rooi)', 'name_urdu': 'روئی', 'code': 'ROOI', 'sort_order': 2},
            {'name': 'Cotton Seed (Binola)', 'name_urdu': 'بنولہ', 'code': 'BINOLA', 'sort_order': 3},
            {'name': 'Cottonseed Cake (Banola)', 'name_urdu': 'بنولہ کھل', 'code': 'BANOLA', 'sort_order': 4},
            {'name': 'Cotton Waste (Jhaar)', 'name_urdu': 'جھاڑ', 'code': 'JHAAR', 'sort_order': 5},
            {'name': 'Packaging Materials', 'name_urdu': 'پیکنگ', 'code': 'PKG', 'sort_order': 6},
            {'name': 'Other Products', 'name_urdu': 'دیگر', 'code': 'OTHER', 'sort_order': 7},
        ]
        for cat_data in categories:
            obj, created = Category.objects.get_or_create(
                code=cat_data['code'],
                defaults={**cat_data, 'is_default': True, 'is_active': True}
            )
            status = 'Created' if created else 'Exists'
            self.stdout.write(f'  Category: {obj.name} - {status}')

        # ── Units of Measurement (cotton factory specific) ──
        units = [
            # Base weight
            {'name': 'Kilogram', 'name_urdu': 'کلوگرام', 'abbreviation': 'KG',
             'unit_type': 'weight', 'conversion_to_base': 1, 'is_base_unit': True, 'sort_order': 1},
            # Traditional weight
            {'name': 'Maund', 'name_urdu': 'من', 'abbreviation': 'MND',
             'unit_type': 'weight', 'conversion_to_base': 40, 'is_base_unit': False, 'sort_order': 2},
            {'name': 'Ton', 'name_urdu': 'ٹن', 'abbreviation': 'TON',
             'unit_type': 'weight', 'conversion_to_base': 1000, 'is_base_unit': False, 'sort_order': 3},
            # Cotton bale (~170 KG standard Pakistan)
            {'name': 'Bale (Cotton Lint)', 'name_urdu': 'گانٹھ (روئی)', 'abbreviation': 'BALE',
             'unit_type': 'weight', 'conversion_to_base': 170, 'is_base_unit': False, 'sort_order': 4},
            # Seed bags
            {'name': 'Bag (Seed)', 'name_urdu': 'بوری (بنولہ)', 'abbreviation': 'SEED-BAG',
             'unit_type': 'weight', 'conversion_to_base': 37.324, 'is_base_unit': False, 'sort_order': 5},
            # Khal bags
            {'name': 'Bag (Khal/Cake)', 'name_urdu': 'بوری (کھل)', 'abbreviation': 'KHAL-BAG',
             'unit_type': 'weight', 'conversion_to_base': 56, 'is_base_unit': False, 'sort_order': 6},
            # General bag
            {'name': 'Bag (General)', 'name_urdu': 'بوری', 'abbreviation': 'BAG',
             'unit_type': 'weight', 'conversion_to_base': 100, 'is_base_unit': False, 'sort_order': 7},
            # Phutti bag (~80-100 KG)
            {'name': 'Bag (Phutti)', 'name_urdu': 'بوری (پھٹی)', 'abbreviation': 'PHUTTI-BAG',
             'unit_type': 'weight', 'conversion_to_base': 85, 'is_base_unit': False, 'sort_order': 8},
            # Count
            {'name': 'Piece', 'name_urdu': 'عدد', 'abbreviation': 'PCS',
             'unit_type': 'quantity', 'conversion_to_base': 1, 'is_base_unit': False, 'sort_order': 9},
        ]
        for unit_data in units:
            obj, created = UnitOfMeasurement.objects.get_or_create(
                abbreviation=unit_data['abbreviation'],
                defaults={**unit_data, 'is_default': True, 'is_active': True}
            )
            status = 'Created' if created else 'Exists'
            self.stdout.write(f'  Unit: {obj.name} ({obj.abbreviation}) - {status}')

        # ── Company Settings ──
        settings, created = CompanySettings.objects.get_or_create(pk=1)
        if created:
            self.stdout.write('  Company Settings: Created with defaults')
        else:
            self.stdout.write('  Company Settings: Already exists')

        # ── Financial Year ──
        today = date.today()
        if today.month >= 7:
            fy_start = date(today.year, 7, 1)
            fy_end = date(today.year + 1, 6, 30)
            fy_name = f"{today.year}-{today.year + 1}"
        else:
            fy_start = date(today.year - 1, 7, 1)
            fy_end = date(today.year, 6, 30)
            fy_name = f"{today.year - 1}-{today.year}"

        fy, created = FinancialYear.objects.get_or_create(
            name=fy_name,
            defaults={
                'start_date': fy_start,
                'end_date': fy_end,
                'is_current': True,
                'status': 'open',
            }
        )
        status = 'Created' if created else 'Exists'
        self.stdout.write(f'  Financial Year: {fy.name} - {status}')

        self.stdout.write(self.style.SUCCESS('\n✓ Seed data complete!'))
