"""
System Settings Models - Company info, system configuration
"""
from django.db import models
from django.core.cache import cache


class CompanySettings(models.Model):
    """
    Singleton model for company/factory settings.
    Only one record should exist.
    """
    # Company Information
    company_name = models.CharField(max_length=255, default='Cotton Factory')
    company_name_urdu = models.CharField(max_length=255, blank=True)
    logo = models.ImageField(upload_to='company/', blank=True, null=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Pakistan')
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)

    # Tax Information
    ntn_number = models.CharField('NTN Number', max_length=50, blank=True)
    sales_tax_number = models.CharField('Sales Tax Registration Number', max_length=50, blank=True)

    # Financial Settings
    MONTH_CHOICES = [(i, m) for i, m in enumerate(
        ['', 'January', 'February', 'March', 'April', 'May', 'June',
         'July', 'August', 'September', 'October', 'November', 'December'],
    ) if i > 0]

    financial_year_start = models.IntegerField(
        choices=MONTH_CHOICES, default=7,
        help_text='Month when financial year starts (July for Pakistan)'
    )
    currency = models.CharField(max_length=10, default='PKR')
    currency_symbol = models.CharField(max_length=5, default='₨')

    # Tax Rates
    sales_tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=17.00,
        help_text='Default Sales Tax percentage'
    )
    wht_rate_filer = models.DecimalField(
        'WHT Rate (Filer)', max_digits=5, decimal_places=2, default=4.00
    )
    wht_rate_non_filer = models.DecimalField(
        'WHT Rate (Non-Filer)', max_digits=5, decimal_places=2, default=8.00
    )

    # System Settings
    default_weight_unit = models.CharField(
        max_length=20, default='MAUND',
        choices=[('MAUND', 'Maund (من)'), ('KG', 'Kilogram'), ('TON', 'Ton')]
    )
    maund_to_kg = models.DecimalField(
        max_digits=10, decimal_places=2, default=40.00,
        help_text='1 Maund = ? Kg (default 40)'
    )
    negative_stock_allowed = models.BooleanField(
        default=False,
        help_text='Allow selling more than available stock?'
    )
    invoice_prefix = models.CharField(max_length=10, default='INV')
    purchase_prefix = models.CharField(max_length=10, default='PUR')
    payment_prefix = models.CharField(max_length=10, default='PAY')
    receipt_prefix = models.CharField(max_length=10, default='RCV')
    date_format = models.CharField(
        max_length=20, default='DD/MM/YYYY',
        choices=[
            ('DD/MM/YYYY', 'DD/MM/YYYY'),
            ('MM/DD/YYYY', 'MM/DD/YYYY'),
            ('YYYY-MM-DD', 'YYYY-MM-DD'),
        ]
    )

    # Session & Security
    session_timeout_minutes = models.IntegerField(default=30)
    low_stock_alert_enabled = models.BooleanField(default=True)

    # Email & Backup Settings
    backup_enabled = models.BooleanField('Enable Auto Backup — خودکار بیک اپ', default=False)
    backup_email = models.EmailField('Primary Email — بنیادی ای میل', blank=True,
        help_text='Gmail address for sending backups')
    backup_email_password = models.CharField('Gmail App Password — ایپ پاسورڈ', max_length=500, blank=True,
        help_text='Gmail App Password (not your regular Gmail password)')
    backup_email_secondary = models.EmailField('Secondary Email — ثانوی ای میل', blank=True,
        help_text='Additional email to receive backup copies')
    report_enabled = models.BooleanField('Enable Daily Reports — روزانہ رپورٹ', default=False)
    last_backup_email_at = models.DateTimeField(null=True, blank=True)
    last_report_email_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'company_settings'
        verbose_name = 'Company Settings'
        verbose_name_plural = 'Company Settings'

    def __str__(self):
        return self.company_name

    @staticmethod
    def _cipher():
        """Get Fernet cipher for email password encryption."""
        try:
            from cryptography.fernet import Fernet
            import base64, hashlib
            from django.conf import settings as s
            key_src = getattr(s, 'DATABASE_ENCRYPTION_KEY', 'cotton-factory')
            key = base64.urlsafe_b64encode(hashlib.sha256(key_src.encode()).digest())
            return Fernet(key)
        except Exception:
            return None

    def set_email_password(self, plain_password):
        """Encrypt and store the email app password."""
        if not plain_password:
            self.backup_email_password = ''
            return
        cipher = self._cipher()
        if cipher:
            self.backup_email_password = 'enc:' + cipher.encrypt(plain_password.encode()).decode()
        else:
            self.backup_email_password = plain_password

    def get_email_password(self):
        """Decrypt and return the email app password."""
        pw = self.backup_email_password
        if not pw:
            return ''
        if pw.startswith('enc:'):
            cipher = self._cipher()
            if cipher:
                try:
                    return cipher.decrypt(pw[4:].encode()).decode()
                except Exception:
                    pass  # Decryption failed — key changed or data corrupt
            # Decryption failed — clear the corrupted password
            # User will need to re-enter it in Settings
            import logging
            logging.getLogger('settings').warning(
                'Email password decryption failed — please re-enter in Settings'
            )
            return ''
        return pw  # Legacy plain text — still works

    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton)
        self.pk = 1
        super().save(*args, **kwargs)
        # Clear cache when settings change
        cache.delete('company_settings')

    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance."""
        cached = cache.get('company_settings')
        if cached:
            return cached
        settings, _ = cls.objects.get_or_create(pk=1)
        cache.set('company_settings', settings, 3600)  # Cache for 1 hour
        return settings


class FinancialYear(models.Model):
    """Track financial years and their status."""
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
    ]

    name = models.CharField(max_length=50)  # e.g., "2024-2025"
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')
    is_current = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='closed_years'
    )

    class Meta:
        db_table = 'financial_years'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        # Ensure only one year is current
        if self.is_current:
            FinancialYear.objects.exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)
