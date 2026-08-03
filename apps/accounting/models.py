"""
Accounting — Chart of Accounts, Journal Entries, Double-Entry Ledger.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class AccountGroup(models.Model):
    """Top-level account groups: Assets, Liabilities, Income, Expenses, Capital."""
    GROUP_TYPES = [
        ('asset', 'Assets (اثاثے)'),
        ('liability', 'Liabilities (واجبات)'),
        ('income', 'Income (آمدنی)'),
        ('expense', 'Expenses (اخراجات)'),
        ('capital', 'Capital (سرمایہ)'),
    ]
    name = models.CharField(max_length=100)
    name_urdu = models.CharField(max_length=100, blank=True)
    group_type = models.CharField(max_length=10, choices=GROUP_TYPES)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    code = models.CharField(max_length=10, unique=True)
    is_system = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'account_groups'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} — {self.name}"


class Account(models.Model):
    """Individual ledger account."""
    name = models.CharField(max_length=200)
    name_urdu = models.CharField(max_length=200, blank=True)
    code = models.CharField(max_length=20, unique=True)
    group = models.ForeignKey(AccountGroup, on_delete=models.PROTECT, related_name='accounts')
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    # Link to party if this is a party sub-ledger
    party = models.OneToOneField('parties.Party', on_delete=models.SET_NULL, null=True, blank=True, related_name='account')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} — {self.name}"


class JournalEntry(models.Model):
    """Double-entry journal. Every transaction creates one."""
    ENTRY_TYPES = [
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('payment', 'Payment'),
        ('receipt', 'Receipt'),
        ('expense', 'Expense'),
        ('adjustment', 'Cross-Party Adjustment'),
        ('journal', 'Journal Voucher'),
        ('opening', 'Opening Balance'),
    ]
    entry_number = models.CharField(max_length=30, unique=True)
    date = models.DateField(default=timezone.now)
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPES, default='journal')
    narration = models.TextField(blank=True)
    # Source references
    purchase = models.ForeignKey('purchases.Purchase', on_delete=models.SET_NULL, null=True, blank=True)
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True)
    payment = models.ForeignKey('finance.PaymentVoucher', on_delete=models.SET_NULL, null=True, blank=True)
    receipt = models.ForeignKey('finance.ReceiptVoucher', on_delete=models.SET_NULL, null=True, blank=True)

    is_posted = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'journal_entries'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.entry_number} — {self.get_entry_type_display()}"

    @property
    def total_debit(self):
        return self.lines.filter(debit__gt=0).aggregate(t=models.Sum('debit'))['t'] or 0

    @property
    def total_credit(self):
        return self.lines.filter(credit__gt=0).aggregate(t=models.Sum('credit'))['t'] or 0

    @property
    def is_balanced(self):
        return self.total_debit == self.total_credit

    def post(self):
        """Post journal entry — update account balances."""
        if not self.is_balanced:
            raise ValueError("Journal entry is not balanced (debit ≠ credit)")
        for line in self.lines.all():
            acct = line.account
            acct.current_balance += line.debit - line.credit
            acct.save(update_fields=['current_balance'])
        self.is_posted = True
        self.save(update_fields=['is_posted'])

    @classmethod
    def generate_number(cls):
        today = timezone.now()
        prefix = f"JV-{today.strftime('%y%m')}"
        last = cls.objects.filter(entry_number__startswith=prefix).order_by('-entry_number').first()
        seq = 1
        if last:
            try: seq = int(last.entry_number.split('-')[-1]) + 1
            except (ValueError, IndexError): pass
        return f"{prefix}-{seq:04d}"


class JournalLine(models.Model):
    """Individual debit/credit line in a journal entry."""
    journal = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='journal_lines')
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    narration = models.CharField(max_length=255, blank=True)
    party = models.ForeignKey('parties.Party', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = 'journal_lines'

    def __str__(self):
        if self.debit > 0:
            return f"Dr {self.account.name} ₨{self.debit}"
        return f"Cr {self.account.name} ₨{self.credit}"
