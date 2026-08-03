"""
Verify and fix all party balances by recalculating from scratch.
Shows detailed breakdown for EVERY party so you can compare with your books.

Usage:
    python manage.py verify_balances              # Show all balances with breakdown
    python manage.py verify_balances --fix        # Fix any wrong balances
    python manage.py verify_balances --party "Ali"  # Check specific party
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Sum


ZERO = Decimal('0')


class Command(BaseCommand):
    help = 'Verify all party balances with detailed transaction breakdown'

    def add_arguments(self, parser):
        parser.add_argument('--fix', action='store_true',
                            help='Fix any wrong balances')
        parser.add_argument('--party', type=str, default='',
                            help='Check a specific party by name (partial match)')
        parser.add_argument('--wrong-only', action='store_true',
                            help='Show only parties with wrong balances')

    def handle(self, *args, **options):
        from apps.parties.models import Party
        from apps.purchases.models import Purchase
        from apps.sales.models import Sale
        from apps.finance.models import PaymentVoucher, ReceiptVoucher

        fix = options['fix']
        party_filter = options['party'].strip()
        wrong_only = options['wrong_only']

        self.stdout.write('')
        self.stdout.write('═' * 80)
        self.stdout.write('  PARTY BALANCE VERIFICATION — پارٹی بیلنس کی تصدیق')
        self.stdout.write('═' * 80)
        self.stdout.write('')

        parties = Party.objects.all().order_by('name')
        if party_filter:
            parties = parties.filter(name__icontains=party_filter)
            self.stdout.write(f'  Filtering for: "{party_filter}" ({parties.count()} matches)')
            self.stdout.write('')

        wrong_count = 0
        total_checked = 0

        for p in parties:
            # Calculate from scratch
            opening = p.opening_balance or ZERO
            if p.opening_balance_type == 'credit':
                opening = -opening

            # Sum of all finalized purchases where this party is supplier
            purchases_total = Purchase.objects.filter(
                supplier=p, status='final'
            ).aggregate(t=Sum('grand_total'))['t'] or ZERO

            # Sum of all finalized sales where this party is customer
            sales_total = Sale.objects.filter(
                customer=p, status='final'
            ).aggregate(t=Sum('grand_total'))['t'] or ZERO

            # Sum of all finalized payments to this party
            payments_total = PaymentVoucher.objects.filter(
                party=p, status='final'
            ).aggregate(t=Sum('amount'))['t'] or ZERO

            # Sum of all finalized receipts from this party
            receipts_total = ReceiptVoucher.objects.filter(
                party=p, status='final'
            ).aggregate(t=Sum('amount'))['t'] or ZERO

            # Expected balance:
            # Opening + Sales (they owe us more) - Purchases (we owe them more)
            # + Payments (we paid, reducing what we owe) - Receipts (they paid, reducing what they owe us)
            calculated = opening - purchases_total + sales_total + payments_total - receipts_total

            stored = p.current_balance
            is_wrong = calculated != stored

            if is_wrong:
                wrong_count += 1

            if wrong_only and not is_wrong:
                total_checked += 1
                continue

            total_checked += 1

            # Display
            status = '❌ WRONG' if is_wrong else '✅ OK'
            bal_type = 'Receivable' if stored > 0 else ('Payable' if stored < 0 else 'Zero')

            self.stdout.write(f'  {p.name} ({p.code}) — {p.get_party_type_display()}')
            self.stdout.write(f'  {status}')
            self.stdout.write(f'    Opening Balance:    {opening:>15,.2f}')

            if purchases_total:
                count = Purchase.objects.filter(supplier=p, status='final').count()
                self.stdout.write(f'    Purchases ({count:>3}):   -{purchases_total:>14,.2f}')
            if sales_total:
                count = Sale.objects.filter(customer=p, status='final').count()
                self.stdout.write(f'    Sales ({count:>3}):       +{sales_total:>14,.2f}')
            if payments_total:
                count = PaymentVoucher.objects.filter(party=p, status='final').count()
                self.stdout.write(f'    Payments ({count:>3}):    +{payments_total:>14,.2f}')
            if receipts_total:
                count = ReceiptVoucher.objects.filter(party=p, status='final').count()
                self.stdout.write(f'    Receipts ({count:>3}):    -{receipts_total:>14,.2f}')

            self.stdout.write(f'    {"─" * 35}')
            self.stdout.write(f'    Calculated:         {calculated:>15,.2f}')
            self.stdout.write(f'    Stored:             {stored:>15,.2f}  ({bal_type})')

            if is_wrong:
                diff = stored - calculated
                self.stdout.write(self.style.ERROR(
                    f'    DIFFERENCE:         {diff:>15,.2f}'
                ))

                if fix:
                    p.current_balance = calculated
                    p.save(update_fields=['current_balance'])
                    self.stdout.write(self.style.SUCCESS(
                        f'    ✅ FIXED → {calculated:,.2f}'
                    ))

            self.stdout.write('')

        # Summary
        self.stdout.write('═' * 80)
        if wrong_count == 0:
            self.stdout.write(self.style.SUCCESS(
                f'  ✅ All {total_checked} parties have correct balances!'
            ))
        else:
            if fix:
                self.stdout.write(self.style.SUCCESS(
                    f'  ✅ Fixed {wrong_count} out of {total_checked} parties'
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f'  ❌ {wrong_count} out of {total_checked} parties have WRONG balances'
                ))
                self.stdout.write(f'     Run with --fix to correct them:')
                self.stdout.write(f'     python manage.py verify_balances --fix')
        self.stdout.write('═' * 80)
        self.stdout.write('')
