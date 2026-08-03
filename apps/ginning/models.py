"""
Ginning / Processing Module — Raw cotton → Lint + Seed + Waste.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class GinningLot(models.Model):
    """A batch/lot of raw cotton being processed."""
    STATUS_CHOICES = [
        ('pending', 'Pending (زیر عمل)'),
        ('processing', 'Processing (جاری)'),
        ('completed', 'Completed (مکمل)'),
    ]
    lot_number = models.CharField(max_length=30, unique=True)
    date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pending')

    # Input
    input_product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='ginning_inputs',
                                       help_text='Raw Cotton / Phutti')
    input_quantity = models.DecimalField('Input Qty (Maund)', max_digits=12, decimal_places=3, default=0)
    input_unit = models.ForeignKey('products.UnitOfMeasurement', on_delete=models.PROTECT, related_name='+')
    source_purchase = models.ForeignKey('purchases.Purchase', on_delete=models.SET_NULL, null=True, blank=True)

    # Output — filled after processing
    lint_product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='ginning_lint_output', help_text='Cotton Lint / Rooi')
    lint_quantity = models.DecimalField('Lint Qty', max_digits=12, decimal_places=3, default=0)

    seed_product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='ginning_seed_output', help_text='Cotton Seed / Binola')
    seed_quantity = models.DecimalField('Seed Qty', max_digits=12, decimal_places=3, default=0)

    waste_product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='ginning_waste_output', help_text='Waste / Jhaar')
    waste_quantity = models.DecimalField('Waste Qty', max_digits=12, decimal_places=3, default=0)

    # GOT = (Lint / Input) × 100
    got_percentage = models.DecimalField('GOT %', max_digits=5, decimal_places=2, default=0,
                                          help_text='Ginning Outturn — auto-calculated')

    # Cost tracking
    electricity_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    labour_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    maintenance_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_per_bale = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Machine info
    machine_number = models.CharField(max_length=20, blank=True)
    supervisor = models.ForeignKey('labour.Worker', on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'ginning_lots'
        ordering = ['-date']

    def __str__(self):
        return f"Lot {self.lot_number} — {self.input_quantity} → GOT {self.got_percentage}%"

    def calculate_got(self):
        if self.input_quantity > 0:
            self.got_percentage = (self.lint_quantity / self.input_quantity) * 100
        self.total_cost = self.electricity_cost + self.labour_cost + self.maintenance_cost + self.other_cost

    def complete(self):
        """Mark lot as completed — update stock."""
        self.calculate_got()
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
        # Reduce raw cotton stock
        if self.input_product:
            self.input_product.current_stock -= self.input_quantity
            self.input_product.save(update_fields=['current_stock'])
        # Increase output stocks
        for prod_field, qty_field in [('lint_product','lint_quantity'),
                                       ('seed_product','seed_quantity'),
                                       ('waste_product','waste_quantity')]:
            product = getattr(self, prod_field)
            qty = getattr(self, qty_field)
            if product and qty > 0:
                product.current_stock += qty
                product.save(update_fields=['current_stock'])

    @classmethod
    def generate_number(cls):
        today = timezone.now()
        prefix = f"LOT-{today.strftime('%y%m')}"
        last = cls.objects.filter(lot_number__startswith=prefix).order_by('-lot_number').first()
        seq = 1
        if last:
            try: seq = int(last.lot_number.split('-')[-1]) + 1
            except (ValueError, IndexError): pass
        return f"{prefix}-{seq:04d}"


class Bale(models.Model):
    """Individual cotton bale produced from ginning."""
    STATUS_CHOICES = [
        ('in_stock', 'In Stock (موجود)'),
        ('sold', 'Sold (فروخت)'),
        ('reserved', 'Reserved (محفوظ)'),
    ]
    GRADE_CHOICES = [
        ('A', 'Grade A'),
        ('B', 'Grade B'),
        ('C', 'Grade C'),
        ('D', 'Grade D'),
    ]
    bale_number = models.CharField(max_length=30, unique=True)
    ginning_lot = models.ForeignKey(GinningLot, on_delete=models.CASCADE, related_name='bales')
    weight = models.DecimalField('Weight (KG)', max_digits=10, decimal_places=2, default=0)
    grade = models.CharField(max_length=1, choices=GRADE_CHOICES, default='B')

    # Quality
    staple_length = models.DecimalField('Staple Length (mm)', max_digits=5, decimal_places=2, default=0)
    micronaire = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    strength = models.DecimalField('Strength (g/tex)', max_digits=5, decimal_places=2, default=0)
    trash_content = models.DecimalField('Trash %', max_digits=5, decimal_places=2, default=0)

    storage_location = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='in_stock')
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True, related_name='bales')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bales'
        ordering = ['-bale_number']

    def __str__(self):
        return f"Bale #{self.bale_number} — {self.weight}kg ({self.get_grade_display()})"
