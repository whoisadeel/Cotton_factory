"""
Sales Management Models — Full cotton trade sales workflow.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class Sale(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft (مسودہ)'),
        ('final', 'Final (حتمی)'),
        ('returned', 'Returned (واپس)'),
        ('void', 'Void (منسوخ)'),
    ]
    SALE_TYPE_CHOICES = [
        ('direct', 'Direct Sale (براہ راست)'),
        ('broker', 'Through Broker (دلال کے ذریعے)'),
        ('export', 'Export (برآمد)'),
    ]
    PAYMENT_TERMS_CHOICES = [
        ('cash', 'Cash (نقد)'),
        ('credit', 'Credit (ادھار)'),
        ('partial', 'Partial Payment (جزوی ادائیگی)'),
    ]

    invoice_number = models.CharField(max_length=30, unique=True, editable=False)
    date = models.DateField(default=timezone.now)

    customer = models.ForeignKey(
        'parties.Party', on_delete=models.PROTECT,
        related_name='sales', limit_choices_to={'party_type__in': ['customer', 'both'], 'is_active': True}
    )
    broker = models.ForeignKey(
        'parties.Party', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='brokered_sales', limit_choices_to={'party_type': 'broker', 'is_active': True}
    )
    sale_type = models.CharField(max_length=10, choices=SALE_TYPE_CHOICES, default='direct')

    # Transport
    vehicle_number = models.CharField(max_length=30, blank=True)
    transporter = models.ForeignKey(
        'parties.Party', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transported_sales', limit_choices_to={'party_type': 'transporter', 'is_active': True}
    )
    bilty_number = models.CharField(max_length=30, blank=True)
    destination = models.CharField(max_length=100, blank=True)

    # Amounts
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    bardana_charges = models.DecimalField('Bardana', max_digits=12, decimal_places=2, default=0)
    commission_pct = models.DecimalField('Commission %', max_digits=5, decimal_places=2, default=0)
    commission_amount = models.DecimalField('Commission', max_digits=12, decimal_places=2, default=0)
    sales_tax_pct = models.DecimalField('Sales Tax %', max_digits=5, decimal_places=2, default=0)
    wht_pct = models.DecimalField('WHT %', max_digits=5, decimal_places=2, default=0)
    hamali_charges = models.DecimalField('Loading/Unloading', max_digits=12, decimal_places=2, default=0)
    tulai_charges = models.DecimalField('Weighing', max_digits=12, decimal_places=2, default=0)
    freight_charges = models.DecimalField('Freight', max_digits=12, decimal_places=2, default=0)
    other_charges = models.DecimalField('Other', max_digits=12, decimal_places=2, default=0)
    sales_tax_amount = models.DecimalField('Sales Tax', max_digits=12, decimal_places=2, default=0)
    wht_amount = models.DecimalField('WHT', max_digits=12, decimal_places=2, default=0)
    total_discount = models.DecimalField('Discount', max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    payment_terms = models.CharField(max_length=10, choices=PAYMENT_TERMS_CHOICES, default='credit')
    amount_received = models.DecimalField('Received Now', max_digits=15, decimal_places=2, default=0)
    balance_due = models.DecimalField('Remaining', max_digits=15, decimal_places=2, default=0)
    due_date = models.DateField('Payment Due Date — آخری تاریخ', null=True, blank=True)
    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid — غیر ادا'),
        ('partial', 'Partially Paid — جزوی ادائیگی'),
        ('paid', 'Fully Paid — مکمل ادائیگی'),
        ('overdue', 'Overdue — میعاد گزر گئی'),
    ]
    payment_status = models.CharField(
        'Payment Status — ادائیگی کی حالت',
        max_length=15, choices=PAYMENT_STATUS_CHOICES, default='unpaid',
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='sales_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sales'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.invoice_number} — {self.customer.name}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self._generate_number()
        if self.pk:
            self.recalculate()
        super().save(*args, **kwargs)

    def recalculate(self):
        if not self.pk:
            return
        from decimal import Decimal
        TWO = Decimal('0.01')
        items = self.items.all()
        self.subtotal = sum(i.net_amount for i in items)

        # Auto-calculate percentage-based charges
        if self.commission_pct and self.commission_pct > 0 and self.subtotal > 0:
            self.commission_amount = (self.subtotal * self.commission_pct / Decimal('100')).quantize(TWO)
        if self.sales_tax_pct and self.sales_tax_pct > 0 and self.subtotal > 0:
            self.sales_tax_amount = (self.subtotal * self.sales_tax_pct / Decimal('100')).quantize(TWO)
        if self.wht_pct and self.wht_pct > 0 and self.subtotal > 0:
            self.wht_amount = (self.subtotal * self.wht_pct / Decimal('100')).quantize(TWO)

        charges = (
            self.bardana_charges + self.commission_amount +
            self.hamali_charges + self.tulai_charges +
            self.freight_charges + self.other_charges +
            self.sales_tax_amount + self.wht_amount
        )
        self.grand_total = self.subtotal + charges - self.total_discount
        self.balance_due = self.grand_total - self.amount_received

    def finalize(self):
        from apps.inventory.helpers import process_sale_stock
        self.status = 'final'
        self.finalized_at = timezone.now()

        # Auto-set due date from customer credit days
        if not self.due_date and self.customer.credit_days > 0:
            self.due_date = self.date + timezone.timedelta(days=self.customer.credit_days)

        # Auto-set payment status
        self.update_payment_status()
        self.save()
        process_sale_stock(self)
        customer = self.customer
        customer.current_balance += self.grand_total
        customer.save(update_fields=['current_balance'])

        # Auto-create journal entry
        try:
            from apps.accounting.auto_journal import journal_for_sale
            journal_for_sale(self)
        except Exception:
            pass

    def update_payment_status(self):
        """Update payment_status based on amounts and due date."""
        if self.balance_due <= 0:
            self.payment_status = 'paid'
        elif self.amount_received > 0:
            self.payment_status = 'partial'
        elif self.due_date and self.due_date < timezone.now().date():
            self.payment_status = 'overdue'
        else:
            self.payment_status = 'unpaid'

    @classmethod
    def _generate_number(cls):
        today = timezone.now()
        prefix = f"INV-{today.strftime('%y%m')}"
        last = cls.objects.filter(invoice_number__startswith=prefix).order_by('-invoice_number').first()
        if last:
            try:
                seq = int(last.invoice_number.split('-')[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{prefix}-{seq:04d}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='sale_items')

    bags_count = models.DecimalField('Bags/Items (بوری)', max_digits=10, decimal_places=0, default=0)
    quantity = models.DecimalField('Net Weight (خالص وزن)', max_digits=12, decimal_places=3, default=0)
    unit = models.ForeignKey('products.UnitOfMeasurement', on_delete=models.PROTECT)
    rate = models.DecimalField('Rate (نرخ)', max_digits=12, decimal_places=2, default=0)
    # Legacy
    weight_mode = models.CharField(max_length=12, default='direct', blank=True)
    weight_per_bag = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    rate_basis = models.CharField(max_length=10, default='per_unit', blank=True)

    gross_weight = models.DecimalField('Gross Wt (KG)', max_digits=12, decimal_places=3, default=0)
    tare_weight = models.DecimalField('Tare Wt (KG)', max_digits=12, decimal_places=3, default=0)
    net_weight = models.DecimalField('Net Wt (KG)', max_digits=12, decimal_places=3, default=0)

    moisture_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    trash_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'sale_items'
        ordering = ['sort_order']

    def save(self, *args, **kwargs):
        from decimal import Decimal
        THREE = Decimal('0.001')
        TWO = Decimal('0.01')
        if self.gross_weight and self.gross_weight > 0:
            tare = self.tare_weight or Decimal('0')
            self.net_weight = (self.gross_weight - tare).quantize(THREE)
            if self.unit_id:
                try:
                    conv = self.unit.conversion_to_base or Decimal('1')
                    self.quantity = (self.net_weight / conv).quantize(THREE) if conv else self.net_weight
                except Exception:
                    self.quantity = self.net_weight
        else:
            if self.quantity and self.quantity > 0 and self.unit_id:
                try:
                    conv = self.unit.conversion_to_base or Decimal('1')
                    self.net_weight = (self.quantity * conv).quantize(THREE)
                except Exception:
                    self.net_weight = self.quantity

        rate = self.rate or Decimal('0')
        net_kg = self.net_weight or Decimal('0')
        basis = self.rate_basis or ''

        if basis == 'total':
            self.amount = rate
        elif basis and net_kg > 0:
            from apps.products.models import UnitOfMeasurement
            try:
                rate_unit = UnitOfMeasurement.objects.get(abbreviation=basis)
                rate_conv = rate_unit.conversion_to_base or Decimal('1')
                # Don't round intermediate qty — only round the final amount
                qty_in_rate_unit = net_kg / rate_conv
                self.amount = (qty_in_rate_unit * rate).quantize(TWO)
            except (UnitOfMeasurement.DoesNotExist, Exception):
                self.amount = ((self.quantity or Decimal('0')) * rate).quantize(TWO)
        else:
            self.amount = ((self.quantity or Decimal('0')) * rate).quantize(TWO)

        self.net_amount = self.amount - (self.discount or Decimal('0'))
        super().save(*args, **kwargs)
        if self.sale_id:
            sale = self.sale
            sale.recalculate()
            Sale.objects.filter(pk=sale.pk).update(
                subtotal=sale.subtotal,
                commission_amount=sale.commission_amount,
                sales_tax_amount=sale.sales_tax_amount,
                wht_amount=sale.wht_amount,
                grand_total=sale.grand_total,
                balance_due=sale.balance_due,
            )


class SaleReturn(models.Model):
    """Return items from customer."""
    return_number = models.CharField(max_length=30, unique=True)
    date = models.DateField(default=timezone.now)
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name='returns')
    customer = models.ForeignKey('parties.Party', on_delete=models.PROTECT, related_name='sale_returns')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=[('draft','Draft'),('final','Final')], default='draft')
    created_by = models.ForeignKey('authentication.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sale_returns'
        ordering = ['-date']

    def __str__(self):
        return f"{self.return_number} — ₨{self.total_amount}"

    def save(self, *args, **kwargs):
        if not self.return_number:
            from django.utils import timezone as tz
            today = tz.now()
            prefix = f"SR-{today.strftime('%y%m')}"
            last = SaleReturn.objects.filter(return_number__startswith=prefix).order_by('-return_number').first()
            seq = int(last.return_number.split('-')[-1]) + 1 if last else 1
            self.return_number = f"{prefix}-{seq:04d}"
        super().save(*args, **kwargs)


class SaleReturnItem(models.Model):
    sale_return = models.ForeignKey(SaleReturn, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        db_table = 'sale_return_items'

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.rate
        super().save(*args, **kwargs)
