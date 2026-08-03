"""Fix any corrupted decimal values in purchase_items and sale_items."""
from django.core.management.base import BaseCommand
from django.db import connection
from decimal import Decimal, InvalidOperation


class Command(BaseCommand):
    help = 'Fix corrupted decimal values in purchase_items and sale_items tables'

    def handle(self, *args, **options):
        cursor = connection.cursor()

        for table, fields in [
            ('purchase_items', [
                ('quantity', 12, 3), ('rate', 12, 2), ('net_weight', 12, 3),
                ('gross_weight', 12, 3), ('tare_weight', 12, 3),
                ('amount', 15, 2), ('net_amount', 15, 2), ('discount', 12, 2),
                ('bags_count', 10, 0), ('weight_per_bag', 10, 3),
                ('moisture_pct', 5, 2), ('trash_pct', 5, 2), ('staple_length', 5, 2),
            ]),
            ('sale_items', [
                ('quantity', 12, 3), ('rate', 12, 2), ('net_weight', 12, 3),
                ('gross_weight', 12, 3), ('tare_weight', 12, 3),
                ('amount', 15, 2), ('net_amount', 15, 2), ('discount', 12, 2),
                ('bags_count', 10, 0), ('weight_per_bag', 10, 3),
                ('moisture_pct', 5, 2), ('trash_pct', 5, 2),
            ]),
        ]:
            self.stdout.write(f'\nChecking {table}...')
            try:
                cols = ', '.join(['id'] + [f[0] for f in fields])
                cursor.execute(f'SELECT {cols} FROM {table}')
                rows = cursor.fetchall()
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Cannot read table: {e}'))
                continue

            fixed = 0
            for row in rows:
                pk = row[0]
                updates = {}
                for i, (fname, max_digits, dec_places) in enumerate(fields):
                    val = row[i + 1]
                    if val is None:
                        continue
                    try:
                        d = Decimal(str(val))
                        q = Decimal('0.' + '0' * dec_places) if dec_places > 0 else Decimal('1')
                        quantized = d.quantize(q)
                        # Check if it would overflow
                        max_int = max_digits - dec_places
                        if abs(quantized) >= Decimal(10) ** max_int:
                            updates[fname] = 0
                            self.stdout.write(self.style.WARNING(
                                f'  Row {pk}: {fname}={val} OVERFLOW → reset to 0'))
                        elif str(quantized) != str(val):
                            updates[fname] = str(quantized)
                    except (InvalidOperation, Exception):
                        updates[fname] = 0
                        self.stdout.write(self.style.WARNING(
                            f'  Row {pk}: {fname}={val} INVALID → reset to 0'))

                if updates:
                    set_clause = ', '.join(f'{k}={v}' for k, v in updates.items())
                    cursor.execute(f'UPDATE {table} SET {set_clause} WHERE id={pk}')
                    fixed += 1

            if fixed:
                self.stdout.write(self.style.SUCCESS(f'  Fixed {fixed} rows'))
            else:
                self.stdout.write(self.style.SUCCESS(f'  All {len(rows)} rows OK'))

        # Also fix purchase and sale header tables
        for table, fields in [
            ('purchases', [
                ('subtotal', 15, 2), ('grand_total', 15, 2), ('balance_due', 15, 2),
                ('amount_paid', 15, 2), ('commission_amount', 12, 2), ('sales_tax_amount', 12, 2),
                ('wht_amount', 12, 2), ('bardana_charges', 12, 2), ('hamali_charges', 12, 2),
                ('tulai_charges', 12, 2), ('mandi_fee', 12, 2), ('freight_charges', 12, 2),
                ('other_charges', 12, 2), ('total_discount', 12, 2),
            ]),
            ('sales', [
                ('subtotal', 15, 2), ('grand_total', 15, 2), ('balance_due', 15, 2),
                ('amount_received', 15, 2), ('commission_amount', 12, 2), ('sales_tax_amount', 12, 2),
                ('wht_amount', 12, 2), ('bardana_charges', 12, 2), ('hamali_charges', 12, 2),
                ('tulai_charges', 12, 2), ('freight_charges', 12, 2),
                ('other_charges', 12, 2), ('total_discount', 12, 2),
            ]),
        ]:
            self.stdout.write(f'\nChecking {table}...')
            try:
                cols = ', '.join(['id'] + [f[0] for f in fields])
                cursor.execute(f'SELECT {cols} FROM {table}')
                rows = cursor.fetchall()
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Cannot read: {e}'))
                continue

            fixed = 0
            for row in rows:
                pk = row[0]
                updates = {}
                for i, (fname, max_digits, dec_places) in enumerate(fields):
                    val = row[i + 1]
                    if val is None:
                        continue
                    try:
                        d = Decimal(str(val))
                        q = Decimal('0.' + '0' * dec_places) if dec_places > 0 else Decimal('1')
                        d.quantize(q)
                    except (InvalidOperation, Exception):
                        updates[fname] = 0
                        self.stdout.write(self.style.WARNING(
                            f'  Row {pk}: {fname}={val} INVALID → reset to 0'))
                if updates:
                    set_clause = ', '.join(f'{k}={v}' for k, v in updates.items())
                    cursor.execute(f'UPDATE {table} SET {set_clause} WHERE id={pk}')
                    fixed += 1

            if fixed:
                self.stdout.write(self.style.SUCCESS(f'  Fixed {fixed} rows'))
            else:
                self.stdout.write(self.style.SUCCESS(f'  All {len(rows)} rows OK'))

        self.stdout.write(self.style.SUCCESS('\n✓ Done!'))
