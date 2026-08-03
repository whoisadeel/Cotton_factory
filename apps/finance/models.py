"""
Finance Models — Payment vouchers, receipt vouchers, expenses.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class PaymentVoucher(models.Model):
    """Money going OUT (ادائیگی)."""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash (نقد)'),
        ('bank', 'Bank Transfer (بینک)'),
        ('cheque', 'Cheque (چیک)'),
        ('online', 'Online / JazzCash / EasyPaisa'),
        ('adjustment', 'Adjustment (ایڈجسٹمنٹ)'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('final', 'Final'),
        ('void', 'Void'),
    ]

    voucher_number = models.CharField(max_length=30, unique=True, editable=False)
    date = models.DateField(default=timezone.now)
    party = models.ForeignKey(
        'parties.Party', on_delete=models.PROTECT, related_name='payments_received'
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=15, choices=PAYMENT_METHOD_CHOICES, default='cash')

    # Bank/Cheque details
    bank_name = models.CharField(max_length=100, blank=True)
    cheque_number = models.CharField(max_length=30, blank=True)
    cheque_date = models.DateField(null=True, blank=True)
    transaction_ref = models.CharField('Reference #', max_length=50, blank=True)

    # Bank account (our account used for bank/cheque/online payments)
    bank_account = models.ForeignKey(
        'finance.BankAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payment_vouchers',
        help_text='Our bank account used for this payment'
    )

    # Linking
    purchase = models.ForeignKey(
        'purchases.Purchase', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payments'
    )
    # Cash-specific fields
    received_by = models.CharField('Received By — کس نے وصول کیا', max_length=200, blank=True,
        help_text='Name of person who received the cash')
    handed_by = models.CharField('Handed By — کس نے دیا', max_length=200, blank=True,
        help_text='Name of person from our side who gave the cash')
    receipt_number = models.CharField('Receipt/Voucher # — رسید نمبر', max_length=50, blank=True)
    cash_given_date = models.DateField('Date Cash Given — نقد دینے کی تاریخ', null=True, blank=True)
    cash_given_time = models.TimeField('Time Cash Given — نقد دینے کا وقت', null=True, blank=True)

    # Recipient bank details (party's bank where we send money)
    recipient_bank_name = models.CharField('Recipient Bank — وصول کنندہ کا بینک', max_length=100, blank=True)
    recipient_account_title = models.CharField('Account Title — اکاؤنٹ ٹائٹل', max_length=200, blank=True)
    recipient_account_number = models.CharField('Account Number — اکاؤنٹ نمبر', max_length=30, blank=True)
    recipient_iban = models.CharField('IBAN', max_length=34, blank=True)
    
    narration = models.TextField('Description (تفصیل)', blank=True)
    attachment = models.FileField(upload_to='vouchers/payments/', blank=True, null=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment_vouchers'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.voucher_number} — ₨{self.amount} to {self.party.name}"

    def save(self, *args, **kwargs):
        if not self.voucher_number:
            self.voucher_number = self._generate_number('PAY')
        super().save(*args, **kwargs)

    def finalize(self):
        self.status = 'final'
        self.save()
        # Reduce what we owe: supplier balance goes towards 0
        party = self.party
        party.current_balance += self.amount  # We paid, so debt decreases
        party.save(update_fields=['current_balance'])
        # Update bank balance if paid via bank
        if self.bank_account and self.payment_method in ('bank', 'cheque', 'online'):
            self.bank_account.current_balance -= self.amount
            self.bank_account.save(update_fields=['current_balance'])
        # Auto-journal
        try:
            from apps.accounting.auto_journal import journal_for_payment
            journal_for_payment(self)
        except Exception:
            pass

    @classmethod
    def _generate_number(cls, prefix):
        today = timezone.now()
        pfx = f"{prefix}-{today.strftime('%y%m')}"
        last = cls.objects.filter(voucher_number__startswith=pfx).order_by('-voucher_number').first()
        if last:
            try:
                seq = int(last.voucher_number.split('-')[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{pfx}-{seq:04d}"


class ReceiptVoucher(models.Model):
    """Money coming IN (وصولی)."""
    PAYMENT_METHOD_CHOICES = PaymentVoucher.PAYMENT_METHOD_CHOICES
    STATUS_CHOICES = PaymentVoucher.STATUS_CHOICES

    voucher_number = models.CharField(max_length=30, unique=True, editable=False)
    date = models.DateField(default=timezone.now)
    party = models.ForeignKey(
        'parties.Party', on_delete=models.PROTECT, related_name='receipts_given'
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=15, choices=PAYMENT_METHOD_CHOICES, default='cash')

    # Bank account (our account used for bank/cheque/online receipts)
    bank_account = models.ForeignKey(
        'finance.BankAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='receipt_vouchers',
        help_text='Our bank account where money was received'
    )

    bank_name = models.CharField(max_length=100, blank=True)
    cheque_number = models.CharField(max_length=30, blank=True)
    cheque_date = models.DateField(null=True, blank=True)
    transaction_ref = models.CharField('Reference #', max_length=50, blank=True)

    sale = models.ForeignKey(
        'sales.Sale', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='receipts'
    )
    # Cash-specific fields
    paid_by = models.CharField('Paid By — کس نے ادا کیا', max_length=200, blank=True)
    received_by_us = models.CharField('Received By Us — ہم نے کس سے لیا', max_length=200, blank=True)
    receipt_number = models.CharField('Receipt # — رسید نمبر', max_length=50, blank=True)
    cash_received_date = models.DateField('Date Cash Received — نقد ملنے کی تاریخ', null=True, blank=True)
    cash_received_time = models.TimeField('Time Cash Received — نقد ملنے کا وقت', null=True, blank=True)

    # Sender bank details (party's bank they sent from)
    sender_bank_name = models.CharField('Sender Bank — بھیجنے والے کا بینک', max_length=100, blank=True)
    sender_account_title = models.CharField('Account Title — اکاؤنٹ ٹائٹل', max_length=200, blank=True)
    sender_account_number = models.CharField('Account Number — اکاؤنٹ نمبر', max_length=30, blank=True)
    sender_iban = models.CharField('IBAN', max_length=34, blank=True)
    
    narration = models.TextField('Description', blank=True)
    attachment = models.FileField(upload_to='vouchers/receipts/', blank=True, null=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'receipt_vouchers'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.voucher_number} — ₨{self.amount} from {self.party.name}"

    def save(self, *args, **kwargs):
        if not self.voucher_number:
            self.voucher_number = self._generate_number('RCV')
        super().save(*args, **kwargs)

    def finalize(self):
        self.status = 'final'
        self.save()
        party = self.party
        party.current_balance -= self.amount  # Customer paid, so receivable decreases
        party.save(update_fields=['current_balance'])
        # Update bank balance if received via bank
        if self.bank_account and self.payment_method in ('bank', 'cheque', 'online'):
            self.bank_account.current_balance += self.amount
            self.bank_account.save(update_fields=['current_balance'])
        # Auto-journal
        try:
            from apps.accounting.auto_journal import journal_for_receipt
            journal_for_receipt(self)
        except Exception:
            pass

    @classmethod
    def _generate_number(cls, prefix):
        today = timezone.now()
        pfx = f"{prefix}-{today.strftime('%y%m')}"
        last = cls.objects.filter(voucher_number__startswith=pfx).order_by('-voucher_number').first()
        if last:
            try:
                seq = int(last.voucher_number.split('-')[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{pfx}-{seq:04d}"


class Expense(models.Model):
    """Daily expense tracking (اخراجات)."""
    CATEGORY_CHOICES = [
        ('electricity', 'Electricity (بجلی)'),
        ('gas_fuel', 'Gas / Fuel (گیس)'),
        ('diesel', 'Diesel (ڈیزل)'),
        ('salary', 'Salaries (تنخواہ)'),
        ('daily_labour', 'Daily Labour (مزدوری)'),
        ('repair', 'Repair & Maintenance (مرمت)'),
        ('spare_parts', 'Spare Parts (پرزے)'),
        ('transport', 'Transportation (نقل و حمل)'),
        ('office', 'Office Supplies (دفتری)'),
        ('communication', 'Phone / Internet'),
        ('rent', 'Rent (کرایہ)'),
        ('insurance', 'Insurance (بیمہ)'),
        ('legal', 'Legal / Professional'),
        ('govt_fees', 'Govt Fees / Taxes'),
        ('entertainment', 'Entertainment (مہمان نوازی)'),
        ('misc', 'Miscellaneous (متفرق)'),
    ]

    date = models.DateField(default=timezone.now)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_to = models.CharField(max_length=200, blank=True)
    payment_method = models.CharField(
        max_length=15, choices=PaymentVoucher.PAYMENT_METHOD_CHOICES, default='cash'
    )
    description = models.TextField(blank=True)
    receipt_image = models.ImageField(upload_to='expenses/', blank=True, null=True)

    is_recurring = models.BooleanField('Recurring — بار بار', default=False)
    recurrence = models.CharField(max_length=10, choices=[
        ('monthly', 'Monthly — ماہانہ'),
        ('weekly', 'Weekly — ہفتہ وار'),
    ], default='monthly', blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'expenses'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.get_category_display()} — ₨{self.amount}"


class BankAccount(models.Model):
    """Bank accounts — can be factory's own or a party's."""
    OWNER_CHOICES = [
        ('own', 'Our Account (ہمارا اکاؤنٹ)'),
        ('party', 'Party Account (پارٹی کا اکاؤنٹ)'),
    ]
    BANK_CHOICES = [
        ('hbl', 'HBL — Habib Bank'),
        ('mcb', 'MCB — Muslim Commercial Bank'),
        ('ubl', 'UBL — United Bank'),
        ('abl', 'Allied Bank — ABL'),
        ('nbp', 'National Bank — NBP'),
        ('meezan', 'Meezan Bank'),
        ('standard', 'Standard Chartered'),
        ('faysal', 'Faysal Bank'),
        ('bop', 'Bank of Punjab'),
        ('bok', 'Bank of Khyber'),
        ('askari', 'Askari Bank'),
        ('soneri', 'Soneri Bank'),
        ('habib_metro', 'Habib Metropolitan'),
        ('summit', 'Summit Bank'),
        ('js', 'JS Bank'),
        ('other', 'Other'),
    ]
    owner_type = models.CharField('Account Owner — مالک', max_length=5, choices=OWNER_CHOICES, default='own')
    party = models.ForeignKey('parties.Party', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='bank_accounts', help_text='Link to party if this is their account')
    bank_code = models.CharField(max_length=15, choices=BANK_CHOICES, default="other", blank=True)
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=30)
    account_type = models.CharField(max_length=10, choices=[('current','Current'),('savings','Savings')], default='current')
    branch = models.CharField(max_length=200, blank=True)
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bank_accounts'

    def __str__(self):
        label = f"{self.bank_name} — {self.account_number}"
        if self.owner_type == 'party' and self.party:
            label += f" ({self.party.name})"
        return label


class Cheque(models.Model):
    """Cheque tracking — issued and received."""
    DIRECTION_CHOICES = [
        ('issued', 'Issued (جاری کیا)'),
        ('received', 'Received (وصول کیا)'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending (زیر التوا)'),
        ('deposited', 'Deposited (جمع)'),
        ('cleared', 'Cleared (کلیئر)'),
        ('bounced', 'Bounced (واپس)'),
        ('cancelled', 'Cancelled (منسوخ)'),
    ]
    cheque_number = models.CharField(max_length=30)
    bank_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    date_on_cheque = models.DateField()
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    party = models.ForeignKey('parties.Party', on_delete=models.PROTECT, related_name='cheques')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    deposit_date = models.DateField(null=True, blank=True)
    clearance_date = models.DateField(null=True, blank=True)
    bounce_date = models.DateField(null=True, blank=True)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='cheques')
    payment_voucher = models.ForeignKey(PaymentVoucher, on_delete=models.SET_NULL, null=True, blank=True)
    receipt_voucher = models.ForeignKey(ReceiptVoucher, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cheques'
        ordering = ['-date_on_cheque']

    def __str__(self):
        return f"Chq#{self.cheque_number} — ₨{self.amount} — {self.get_status_display()}"


class BankReconciliation(models.Model):
    """Bank reconciliation — match system records with bank statement."""
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='reconciliations')
    date = models.DateField(default=timezone.now)
    statement_balance = models.DecimalField('Bank Statement Balance', max_digits=15, decimal_places=2, default=0)
    system_balance = models.DecimalField('System Balance', max_digits=15, decimal_places=2, default=0)
    difference = models.DecimalField('Difference', max_digits=15, decimal_places=2, default=0)
    is_reconciled = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bank_reconciliations'
        ordering = ['-date']

    def save(self, *args, **kwargs):
        self.difference = self.statement_balance - self.system_balance
        self.is_reconciled = (self.difference == 0)
        super().save(*args, **kwargs)


class BankReconciliationItem(models.Model):
    """Individual transaction matched/unmatched during reconciliation."""
    reconciliation = models.ForeignKey(BankReconciliation, on_delete=models.CASCADE, related_name='items')
    date = models.DateField()
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    is_credit = models.BooleanField(default=False)
    is_matched = models.BooleanField(default=False)
    payment_voucher = models.ForeignKey(PaymentVoucher, on_delete=models.SET_NULL, null=True, blank=True)
    receipt_voucher = models.ForeignKey(ReceiptVoucher, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = 'bank_reconciliation_items'


class CrossPartyAdjustment(models.Model):
    """
    Cross-Party Adjustment — کراس پارٹی ایڈجسٹمنٹ
    
    Simple concept: Party A pays Party B directly on our behalf.
    No cash/bank moves through us. Both party balances adjust.
    
    Balance effect (same as Receipt from A + Payment to B):
      - paying_party balance -= amount  (they paid, so they owe us less / we owe them more)
      - receiving_party balance += amount  (they received, so we owe them less / they owe us more)
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('final', 'Final'),
        ('void', 'Void'),
    ]

    voucher_number = models.CharField(max_length=30, unique=True, editable=False)
    date = models.DateField(default=timezone.now)
    # Keep direction field for DB compatibility but ignore it in logic
    direction = models.CharField(max_length=25, default='debtor_pays_creditor', blank=True)

    # Party who PAYS (the one giving money — their account is debited in our books)
    from_party = models.ForeignKey(
        'parties.Party', on_delete=models.PROTECT, related_name='adjustments_from',
        verbose_name='Who Pays — کون ادا کرے گا',
        help_text='This party pays directly'
    )
    # Party who RECEIVES payment (the one getting money — their account is credited in our books)
    to_party = models.ForeignKey(
        'parties.Party', on_delete=models.PROTECT, related_name='adjustments_to',
        verbose_name='Who Gets Paid — کسے ادائیگی ہوگی',
        help_text='This party receives payment directly'
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    narration = models.TextField('Description — تفصیل', blank=True)

    # Linked receipt and payment (auto-created on finalize)
    receipt = models.ForeignKey(
        'finance.ReceiptVoucher', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cross_adj_receipt',
    )
    payment = models.ForeignKey(
        'finance.PaymentVoucher', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cross_adj_payment',
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cross_party_adjustments'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.voucher_number} — ₨{self.amount} ({self.from_party.name} → {self.to_party.name})"

    def save(self, *args, **kwargs):
        if not self.voucher_number:
            self.voucher_number = self._generate_number()
        super().save(*args, **kwargs)

    def finalize(self, we_owe_them=True, method='cash'):
        """
        Finalize cross-party adjustment.
        
        from_party PAYS to_party directly.
        
        Creates:
          1. Receipt from from_party — they paid (with the actual payment method)
          2. Payment to to_party — they got paid (with the actual payment method)
        
        If we_owe_them=True: Payment adjusts to_party balance (settling debt)
        If we_owe_them=False: Payment is created but to_party balance is NOT changed
        """
        self.status = 'final'

        adj_note = f'Cross-Party Adjustment {self.voucher_number}: {self.from_party.name} paid {self.to_party.name} directly'
        user_narration = f'{adj_note}. {self.narration}'.strip() if self.narration else adj_note

        # 1. Create Receipt from from_party (they paid us)
        rcv = ReceiptVoucher(
            date=self.date,
            party=self.from_party,
            amount=self.amount,
            payment_method=method,
            narration=user_narration,
            created_by=self.created_by,
        )
        rcv.save()
        rcv.finalize()  # This does: from_party.balance -= amount + auto-journal
        self.receipt = rcv

        # 2. Create Payment to to_party (we paid them)
        pmt = PaymentVoucher(
            date=self.date,
            party=self.to_party,
            amount=self.amount,
            payment_method=method,
            narration=user_narration,
            created_by=self.created_by,
        )
        pmt.save()

        if we_owe_them:
            # Adjust to_party balance — normal payment finalize
            # If we owe them (negative balance): debt gets reduced
            # If we don't owe them (zero/positive): advance payment, they now owe us
            pmt.finalize()  # to_party.balance += amount + journal + bank
        else:
            # NOT settling any debt — just record payment, no balance change for to_party
            pmt.status = 'final'
            pmt.save()
            # Handle bank balance for non-adjustment methods
            if pmt.bank_account and pmt.payment_method in ('bank', 'cheque', 'online'):
                pmt.bank_account.current_balance -= pmt.amount
                pmt.bank_account.save(update_fields=['current_balance'])
            try:
                from apps.accounting.auto_journal import journal_for_payment
                journal_for_payment(pmt)
            except Exception:
                pass

        self.payment = pmt
        self.save()

    def void(self):
        """Reverse the adjustment by voiding the linked receipt and payment."""
        if self.status != 'final':
            return

        # Void the receipt (reverses from_party balance + journal)
        if self.receipt and self.receipt.status == 'final':
            self.receipt.party.current_balance += self.receipt.amount
            self.receipt.party.save(update_fields=['current_balance'])
            # Reverse journal
            try:
                from apps.accounting.models import JournalEntry
                je = JournalEntry.objects.filter(receipt=self.receipt).first()
                if je and je.is_posted:
                    for line in je.lines.all():
                        line.account.current_balance -= (line.debit - line.credit)
                        line.account.save(update_fields=['current_balance'])
                    je.is_posted = False
                    je.save(update_fields=['is_posted'])
            except Exception:
                pass
            self.receipt.status = 'void'
            self.receipt.save()

        # Void the payment (reverses to_party balance + journal)
        if self.payment and self.payment.status == 'final':
            # Only reverse balance if it was actually adjusted by finalize
            # (finalize only adjusts when we_owe_them=True AND balance was negative)
            # We detect this: if Payment was finalized via pmt.finalize() (not manually),
            # the balance was adjusted. Check by seeing if reversing would make sense.
            self.payment.party.current_balance -= self.payment.amount
            self.payment.party.save(update_fields=['current_balance'])
            # Reverse bank if applicable
            if self.payment.bank_account and self.payment.payment_method in ('bank', 'cheque', 'online'):
                self.payment.bank_account.current_balance += self.payment.amount
                self.payment.bank_account.save(update_fields=['current_balance'])
            try:
                from apps.accounting.models import JournalEntry
                je = JournalEntry.objects.filter(payment=self.payment).first()
                if je and je.is_posted:
                    for line in je.lines.all():
                        line.account.current_balance -= (line.debit - line.credit)
                        line.account.save(update_fields=['current_balance'])
                    je.is_posted = False
                    je.save(update_fields=['is_posted'])
            except Exception:
                pass
            self.payment.status = 'void'
            self.payment.save()

        self.status = 'void'
        self.save()

    @classmethod
    def _generate_number(cls):
        today = timezone.now()
        pfx = f"ADJ-{today.strftime('%y%m')}"
        last = cls.objects.filter(voucher_number__startswith=pfx).order_by('-voucher_number').first()
        if last:
            try:
                seq = int(last.voucher_number.split('-')[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{pfx}-{seq:04d}"
