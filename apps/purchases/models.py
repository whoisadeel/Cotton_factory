"""
Purchase Management Models — Full cotton trade purchase workflow.
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal


class Purchase(models.Model):
    """
    Purchase entry (header). Supports draft auto-save and finalization.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft (مسودہ)'),
        ('final', 'Final (حتمی)'),
        ('returned', 'Returned (واپس)'),
        ('void', 'Void (منسوخ)'),
    ]
    PURCHASE_TYPE_CHOICES = [
        ('direct', 'Direct Purchase (براہ راست)'),
        ('broker', 'Through Broker (دلال کے ذریعے)'),
        ('import', 'Import (درآمد)'),
    ]
    PAYMENT_TERMS_CHOICES = [
        ('cash', 'Cash (نقد)'),
        ('credit', 'Credit (ادھار)'),
        ('partial', 'Partial Payment (جزوی ادائیگی)'),
    ]

    # Auto-generated
    purchase_number = models.CharField(max_length=30, unique=True, editable=False)
    date = models.DateField(default=timezone.now)

    # Supplier & Broker
    supplier = models.ForeignKey(
        'parties.Party', on_delete=models.PROTECT,
        related_name='purchases', limit_choices_to={'party_type__in': ['supplier', 'both'], 'is_active': True}
    )
    broker = models.ForeignKey(
        'parties.Party', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='brokered_purchases', limit_choices_to={'party_type': 'broker', 'is_active': True}
    )
    bill_number = models.CharField('Supplier Invoice #', max_length=50, blank=True)
    purchase_type = models.CharField(max_length=10, choices=PURCHASE_TYPE_CHOICES, default='direct')

    # Transport
    vehicle_number = models.CharField(max_length=30, blank=True)
    transporter = models.ForeignKey(
        'parties.Party', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transported_purchases', limit_choices_to={'party_type': 'transporter', 'is_active': True}
    )
    bilty_number = models.CharField('Bilty / Receipt #', max_length=30, blank=True)
    gate_entry_number = models.CharField(max_length=20, blank=True)

    # Amounts (auto-calculated from items + charges)
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    bardana_charges = models.DecimalField('Bardana (بردانہ)', max_digits=12, decimal_places=2, default=0)
    commission_pct = models.DecimalField('Commission %', max_digits=5, decimal_places=2, default=0)
    commission_amount = models.DecimalField('Commission (کمیشن)', max_digits=12, decimal_places=2, default=0)
    sales_tax_pct = models.DecimalField('Sales Tax %', max_digits=5, decimal_places=2, default=0)
    wht_pct = models.DecimalField('WHT %', max_digits=5, decimal_places=2, default=0)
    hamali_charges = models.DecimalField('Loading/Unloading (حمالی)', max_digits=12, decimal_places=2, default=0)
    tulai_charges = models.DecimalField('Weighing (تلائی)', max_digits=12, decimal_places=2, default=0)
    mandi_fee = models.DecimalField('Market Fee (منڈی فیس)', max_digits=12, decimal_places=2, default=0)
    freight_charges = models.DecimalField('Freight (بھاڑا)', max_digits=12, decimal_places=2, default=0)
    other_charges = models.DecimalField('Other Charges (دیگر)', max_digits=12, decimal_places=2, default=0)
    sales_tax_amount = models.DecimalField('Sales Tax', max_digits=12, decimal_places=2, default=0)
    wht_amount = models.DecimalField('WHT', max_digits=12, decimal_places=2, default=0)
    total_discount = models.DecimalField('Discount (رعایت)', max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField('Grand Total (کل رقم)', max_digits=15, decimal_places=2, default=0)

    # Payment
    payment_terms = models.CharField(max_length=10, choices=PAYMENT_TERMS_CHOICES, default='credit')
    amount_paid = models.DecimalField('Paid Now (ادائیگی)', max_digits=15, decimal_places=2, default=0)
    balance_due = models.DecimalField('Remaining (بقایا)', max_digits=15, decimal_places=2, default=0)
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

    # Status
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)

    # Audit
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='purchases_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'purchases'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.purchase_number} — {self.supplier.name}"

    def save(self, *args, **kwargs):
        if not self.purchase_number:
            self.purchase_number = self._generate_number()
        if self.pk:
            self.recalculate()
        super().save(*args, **kwargs)

    def recalculate(self):
        """Recalculate totals from line items and charges."""
        if not self.pk:
            return
        TWO = Decimal('0.01')
        items = self.items.all()
        self.subtotal = sum(i.net_amount for i in items)

        # Auto-calculate percentage-based charges from current subtotal
        if self.commission_pct and self.commission_pct > 0 and self.subtotal > 0:
            self.commission_amount = (self.subtotal * self.commission_pct / Decimal('100')).quantize(TWO)
        if self.sales_tax_pct and self.sales_tax_pct > 0 and self.subtotal > 0:
            self.sales_tax_amount = (self.subtotal * self.sales_tax_pct / Decimal('100')).quantize(TWO)
        if self.wht_pct and self.wht_pct > 0 and self.subtotal > 0:
            self.wht_amount = (self.subtotal * self.wht_pct / Decimal('100')).quantize(TWO)

        charges = (
            self.bardana_charges + self.commission_amount +
            self.hamali_charges + self.tulai_charges +
            self.mandi_fee + self.freight_charges +
            self.other_charges + self.sales_tax_amount +
            self.wht_amount
        )
        self.grand_total = self.subtotal + charges - self.total_discount
        self.balance_due = self.grand_total - self.amount_paid

    def finalize(self):
        """Mark purchase as final — updates stock and supplier balance."""
        from apps.inventory.helpers import process_purchase_stock

        self.status = 'final'
        self.finalized_at = timezone.now()

        # Auto-set due date from supplier credit days
        if not self.due_date and self.supplier.credit_days > 0:
            self.due_date = self.date + timezone.timedelta(days=self.supplier.credit_days)

        # Auto-set payment status
        self.update_payment_status()
        self.save()

        # Update stock
        process_purchase_stock(self)

        # Update supplier balance (we owe them more)
        supplier = self.supplier
        supplier.current_balance -= self.grand_total
        supplier.save(update_fields=['current_balance'])

        # Auto-create journal entry
        try:
            from apps.accounting.auto_journal import journal_for_purchase
            journal_for_purchase(self)
        except Exception:
            pass  # Don't block finalization if accounting fails

    def update_payment_status(self):
        """Update payment_status based on amounts and due date."""
        if self.balance_due <= 0:
            self.payment_status = 'paid'
        elif self.amount_paid > 0:
            self.payment_status = 'partial'
        elif self.due_date and self.due_date < timezone.now().date():
            self.payment_status = 'overdue'
        else:
            self.payment_status = 'unpaid'

    @classmethod
    def _generate_number(cls):
        today = timezone.now()
        prefix = f"PUR-{today.strftime('%y%m')}"
        last = cls.objects.filter(purchase_number__startswith=prefix).order_by('-purchase_number').first()
        if last:
            try:
                seq = int(last.purchase_number.split('-')[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{prefix}-{seq:04d}"


class PurchaseItem(models.Model):
    """Individual line item in a purchase."""
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='purchase_items')

    # Bags count — optional, informational (e.g. "20 bags came")
    bags_count = models.DecimalField('Bags/Items (بوری)', max_digits=10, decimal_places=0, default=0)

    # Core: Weight + Unit + Rate → Amount
    quantity = models.DecimalField('Net Weight (خالص وزن)', max_digits=12, decimal_places=3, default=0)
    unit = models.ForeignKey('products.UnitOfMeasurement', on_delete=models.PROTECT)
    rate = models.DecimalField('Rate (نرخ)', max_digits=12, decimal_places=2, default=0)

    # Weighbridge (optional expandable — fills net_weight/quantity when used)
    gross_weight = models.DecimalField('Gross Wt KG', max_digits=12, decimal_places=3, default=0)
    tare_weight = models.DecimalField('Tare Wt KG', max_digits=12, decimal_places=3, default=0)

    # Auto-calculated: weight in KG (for conversions/reports)
    net_weight = models.DecimalField('Net Wt KG', max_digits=12, decimal_places=3, default=0)

    # Legacy fields kept for migration compatibility
    weight_mode = models.CharField(max_length=12, default='direct', blank=True)
    weight_per_bag = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    rate_basis = models.CharField(max_length=10, default='per_unit', blank=True)

    # Cotton quality (optional)
    moisture_pct = models.DecimalField('Moisture %', max_digits=5, decimal_places=2, default=0)
    trash_pct = models.DecimalField('Trash %', max_digits=5, decimal_places=2, default=0)
    staple_length = models.DecimalField('Staple Length (mm)', max_digits=5, decimal_places=2, default=0, blank=True)

    # Calculated
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'purchase_items'
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"

    def save(self, *args, **kwargs):
        THREE = Decimal('0.001')
        # ── If weighbridge data filled → override quantity from net KG ──
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

        # ── Amount calculation based on rate_basis ──
        # rate_basis = unit abbreviation (KG, MND, BALE, etc.) or 'total'
        TWO = Decimal('0.01')
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

        # Recalculate purchase totals
        if self.purchase_id:
            purchase = self.purchase
            purchase.recalculate()
            Purchase.objects.filter(pk=purchase.pk).update(
                subtotal=purchase.subtotal,
                commission_amount=purchase.commission_amount,
                sales_tax_amount=purchase.sales_tax_amount,
                wht_amount=purchase.wht_amount,
                grand_total=purchase.grand_total,
                balance_due=purchase.balance_due,
            )


class PurchaseReturn(models.Model):
    """Return items to supplier from a purchase."""
    return_number = models.CharField(max_length=30, unique=True)
    date = models.DateField(default=timezone.now)
    purchase = models.ForeignKey(Purchase, on_delete=models.PROTECT, related_name='returns')
    supplier = models.ForeignKey('parties.Party', on_delete=models.PROTECT, related_name='purchase_returns')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=[('draft','Draft'),('final','Final')], default='draft')
    created_by = models.ForeignKey('authentication.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'purchase_returns'
        ordering = ['-date']

    def __str__(self):
        return f"{self.return_number} — ₨{self.total_amount}"

    def save(self, *args, **kwargs):
        if not self.return_number:
            from django.utils import timezone as tz
            today = tz.now()
            prefix = f"PR-{today.strftime('%y%m')}"
            last = PurchaseReturn.objects.filter(return_number__startswith=prefix).order_by('-return_number').first()
            seq = int(last.return_number.split('-')[-1]) + 1 if last else 1
            self.return_number = f"{prefix}-{seq:04d}"
        super().save(*args, **kwargs)


class PurchaseReturnItem(models.Model):
    purchase_return = models.ForeignKey(PurchaseReturn, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        db_table = 'purchase_return_items'

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.rate
        super().save(*args, **kwargs)
