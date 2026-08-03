"""
Party Management Models - Suppliers, Customers, Brokers, etc.
"""
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Party(models.Model):
    """
    Master record for all business contacts.
    A party can be supplier, customer, broker, or any combination.
    """
    TYPE_CHOICES = [
        ('supplier', 'Supplier'),
        ('customer', 'Customer'),
        ('both', 'Both (Supplier & Customer)'),
        ('broker', 'Broker / Commission Agent'),
        ('transporter', 'Transporter'),
        ('employee', 'Employee'),
        ('other', 'Other'),
    ]

    BALANCE_TYPE_CHOICES = [
        ('debit', 'Debit (They owe us)'),
        ('credit', 'Credit (We owe them)'),
    ]

    PROVINCE_CHOICES = [
        ('punjab', 'Punjab'),
        ('sindh', 'Sindh'),
        ('kpk', 'Khyber Pakhtunkhwa'),
        ('balochistan', 'Balochistan'),
        ('islamabad', 'Islamabad Capital Territory'),
        ('ajk', 'Azad Jammu & Kashmir'),
        ('gilgit', 'Gilgit-Baltistan'),
    ]

    # Basic Information
    name = models.CharField(max_length=200)
    name_urdu = models.CharField(max_length=200, blank=True)
    code = models.CharField(max_length=30, unique=True)
    party_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default='supplier')
    company_name = models.CharField(max_length=200, blank=True)

    # Identity Documents
    cnic = models.CharField('CNIC Number', max_length=15, blank=True,
                            help_text='Format: XXXXX-XXXXXXX-X')
    ntn_number = models.CharField('NTN Number', max_length=20, blank=True)
    sales_tax_number = models.CharField('Sales Tax Registration', max_length=30, blank=True)
    is_filer = models.BooleanField('Tax Filer?', default=False,
                                   help_text='Whether this party is a tax filer (affects WHT rate)')

    # Contact Information
    phone_primary = models.CharField('Primary Phone', max_length=20, blank=True)
    phone_secondary = models.CharField('Secondary Phone', max_length=20, blank=True)
    whatsapp = models.CharField('WhatsApp Number', max_length=20, blank=True)
    email = models.EmailField(blank=True)

    # Address
    street_address = models.TextField('Street Address', blank=True)
    city = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=20, choices=PROVINCE_CHOICES, blank=True)
    country = models.CharField(max_length=100, default='Pakistan')

    # Financial
    opening_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal('0'))]
    )
    opening_balance_type = models.CharField(
        max_length=6, choices=BALANCE_TYPE_CHOICES, default='debit'
    )
    opening_balance_date = models.DateField(null=True, blank=True)
    current_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text='Positive = They owe us (Debit), Negative = We owe them (Credit)'
    )
    credit_limit = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text='Maximum credit allowed (0 = no limit)'
    )
    credit_days = models.IntegerField(
        default=0, help_text='Payment terms in days (0 = cash)'
    )

    # Broker-specific
    commission_rate = models.DecimalField(
        'Commission Rate %', max_digits=5, decimal_places=2, default=0,
        help_text='Default commission percentage for broker'
    )

    # Bank Details
    bank_name = models.CharField(max_length=100, blank=True)
    account_title = models.CharField(max_length=200, blank=True)
    account_number = models.CharField(max_length=30, blank=True)
    iban = models.CharField('IBAN', max_length=34, blank=True)
    bank_branch = models.CharField('Branch', max_length=200, blank=True)

    # Status
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'parties'
        verbose_name_plural = 'Parties'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_party_type_display()})"

    @property
    def balance_display(self):
        """Human-readable balance."""
        if self.current_balance > 0:
            return f"₨ {self.current_balance:,.2f} Dr"
        elif self.current_balance < 0:
            return f"₨ {abs(self.current_balance):,.2f} Cr"
        return "₨ 0.00"

    @property
    def is_over_credit_limit(self):
        """Check if party has exceeded credit limit."""
        if self.credit_limit <= 0:
            return False
        # For suppliers: negative balance means we owe them
        if self.party_type in ('supplier', 'both'):
            return abs(self.current_balance) > self.credit_limit if self.current_balance < 0 else False
        # For customers: positive balance means they owe us
        return self.current_balance > self.credit_limit

    @classmethod
    def generate_code(cls, party_type):
        """Auto-generate party code based on type."""
        prefix_map = {
            'supplier': 'SUP',
            'customer': 'CUS',
            'both': 'PTY',
            'broker': 'BRK',
            'transporter': 'TRN',
            'employee': 'EMP',
            'other': 'OTH',
        }
        prefix = prefix_map.get(party_type, 'PTY')
        last = cls.objects.filter(
            code__startswith=prefix
        ).order_by('-code').first()
        if last:
            try:
                num = int(last.code.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        return f"{prefix}-{num:04d}"

    def save(self, *args, **kwargs):
        # Set initial balance on creation
        if not self.pk:
            if self.opening_balance_type == 'debit':
                self.current_balance = self.opening_balance
            else:
                self.current_balance = -self.opening_balance
        super().save(*args, **kwargs)
