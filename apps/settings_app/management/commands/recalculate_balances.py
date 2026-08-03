"""
Recalculate all party balances from scratch based on finalized transactions.
Useful for data integrity verification and fixing any balance drift.
Usage: python manage.py recalculate_balances
       python manage.py recalculate_balances --dry-run
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Sum


class Command(BaseCommand):
    help = 'Recalculate all party balances from finalized transactions — بیلنس دوبارہ حساب کریں'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without actually changing anything'
        )

    def handle(self, *args, **options):
        from apps.parties.models import Party
        from apps.purchases.models import Purchase
        from apps.sales.models import Sale
        from apps.finance.models import PaymentVoucher, ReceiptVoucher

        dry_run = options['dry_run']
        self.stdout.write('\n' + ('DRY RUN — ' if dry_run else '') + 'Recalculating all party balances...\n')

        fixed = 0
        total = 0

        for party in Party.objects.all():
            total += 1
            # Start from opening balance
            if party.opening_balance_type == 'debit':
                expected = party.opening_balance
            else:
                expected = -party.opening_balance

            # Purchases: we owe supplier → balance decreases (use grand_total, NOT balance_due)
            purchases_total = Purchase.objects.filter(
                supplier=party, status='final'
            ).aggregate(t=Sum('grand_total'))['t'] or Decimal('0')
            expected -= purchases_total

            # Sales: customer owes us → balance increases (use grand_total)
            sales_total = Sale.objects.filter(
                customer=party, status='final'
            ).aggregate(t=Sum('grand_total'))['t'] or Decimal('0')
            expected += sales_total

            # Payments: we paid → balance increases toward 0
            payments_total = PaymentVoucher.objects.filter(
                party=party, status='final'
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
            expected += payments_total

            # Receipts: they paid → balance decreases toward 0
            receipts_total = ReceiptVoucher.objects.filter(
                party=party, status='final'
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
            expected -= receipts_total

            # Note: Cross-party adjustments are already counted above because
            # they auto-create Receipt + Payment vouchers. No separate handling needed.

            # Check for drift
            drift = party.current_balance - expected
            if drift != 0:
                fixed += 1
                self.stdout.write(self.style.WARNING(
                    f'  ⚠️  {party.name} ({party.code}): '
                    f'stored={party.current_balance:,.2f} → calculated={expected:,.2f} '
                    f'(drift: {drift:+,.2f})'
                ))
                if not dry_run:
                    Party.objects.filter(pk=party.pk).update(current_balance=expected)

        if fixed == 0:
            self.stdout.write(self.style.SUCCESS(f'\n  ✅ All {total} parties have correct balances — سب درست ہے'))
        else:
            verb = 'would be' if dry_run else 'were'
            self.stdout.write(self.style.WARNING(
                f'\n  {fixed} of {total} parties {verb} corrected.'
            ))
            if dry_run:
                self.stdout.write('  Run without --dry-run to apply fixes.')

        # Also recalculate bank balances
        self.stdout.write('\nRecalculating bank balances...')
        from apps.finance.models import BankAccount
        bank_fixed = 0
        for bank in BankAccount.objects.filter(owner_type='own'):
            pay_total = PaymentVoucher.objects.filter(
                bank_account=bank, status='final',
                payment_method__in=['bank', 'cheque', 'online']
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
            rcv_total = ReceiptVoucher.objects.filter(
                bank_account=bank, status='final',
                payment_method__in=['bank', 'cheque', 'online']
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
            expected_bank = bank.opening_balance - pay_total + rcv_total
            if bank.current_balance != expected_bank:
                bank_fixed += 1
                self.stdout.write(self.style.WARNING(
                    f'  ⚠️  {bank.bank_name} ({bank.account_number}): '
                    f'stored={bank.current_balance:,.2f} → calculated={expected_bank:,.2f}'
                ))
                if not dry_run:
                    BankAccount.objects.filter(pk=bank.pk).update(current_balance=expected_bank)

        if bank_fixed == 0:
            self.stdout.write(self.style.SUCCESS('  ✅ All bank balances correct'))
        else:
            self.stdout.write(self.style.WARNING(f'  {bank_fixed} bank(s) corrected.'))
