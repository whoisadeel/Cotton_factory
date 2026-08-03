"""
Product & Category Models for Cotton Factory
"""
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Category(models.Model):
    """Product categories with predefined cotton factory categories."""
    name = models.CharField(max_length=100)
    name_urdu = models.CharField(max_length=100, blank=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='subcategories'
    )
    is_default = models.BooleanField(
        default=False,
        help_text='System default categories cannot be deleted'
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        if self.is_default:
            raise PermissionError("Default categories cannot be deleted.")
        super().delete(*args, **kwargs)


class UnitOfMeasurement(models.Model):
    """Units of measurement with conversion support."""
    name = models.CharField(max_length=50)
    name_urdu = models.CharField(max_length=50, blank=True)
    abbreviation = models.CharField(max_length=10, unique=True)
    is_base_unit = models.BooleanField(
        default=False,
        help_text='Base unit for weight (KG is the base weight unit)'
    )
    conversion_to_base = models.DecimalField(
        max_digits=15, decimal_places=6, default=1,
        help_text='How many base units in 1 of this unit (e.g., 1 Maund = 40 KG)'
    )
    unit_type = models.CharField(
        max_length=20,
        choices=[
            ('weight', 'Weight'),
            ('quantity', 'Quantity/Count'),
            ('volume', 'Volume'),
            ('length', 'Length'),
        ],
        default='weight'
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'units_of_measurement'
        ordering = ['sort_order', 'name']

    def __str__(self):
        conv = float(self.conversion_to_base) if self.conversion_to_base else 1
        ur = self.name_urdu or self.abbreviation
        if conv != 1:
            # Show practical conversion: "Maund (من) — 1 = 40 KG"
            conv_str = f"{conv:g}" if conv == int(conv) else f"{conv:.3f}".rstrip('0').rstrip('.')
            return f"{self.name} ({ur}) — 1 = {conv_str} KG"
        return f"{self.name} ({ur})"

    def convert_to(self, value, target_unit):
        """Convert a value from this unit to a target unit."""
        if self.unit_type != target_unit.unit_type:
            raise ValueError(f"Cannot convert between {self.unit_type} and {target_unit.unit_type}")
        # Convert to base first, then to target
        base_value = Decimal(str(value)) * self.conversion_to_base
        return base_value / target_unit.conversion_to_base


class Product(models.Model):
    """Product master for all items in the cotton factory."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    SOURCE_CHOICES = [
        ('purchased', 'Purchased (خریداری)'),
        ('produced', 'Produced (پیداوار)'),
        ('both', 'Both (دونوں)'),
    ]

    name = models.CharField(max_length=200)
    name_urdu = models.CharField(max_length=200, blank=True)
    code = models.CharField(max_length=30, unique=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='products'
    )
    unit = models.ForeignKey(
        UnitOfMeasurement, on_delete=models.PROTECT, related_name='products'
    )
    source = models.CharField(
        'Product Source — ذریعہ', max_length=10, choices=SOURCE_CHOICES, default='purchased',
        help_text='Purchased = you buy it. Produced = your factory makes it (e.g. from ginning). Both = either way.'
    )
    default_purchase_price = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal('0'))]
    )
    default_sale_price = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal('0'))]
    )
    minimum_stock = models.DecimalField(
        max_digits=15, decimal_places=3, default=0,
        help_text='Minimum stock level for alerts'
    )
    current_stock = models.DecimalField(
        max_digits=15, decimal_places=3, default=0,
        help_text='Current stock quantity (auto-updated by transactions)'
    )
    hsn_code = models.CharField('HSN/Product Code', max_length=20, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    # Cotton-specific quality defaults
    default_moisture_pct = models.DecimalField(
        'Default Moisture %', max_digits=5, decimal_places=2, default=0, blank=True
    )
    default_trash_pct = models.DecimalField(
        'Default Trash/Impurity %', max_digits=5, decimal_places=2, default=0, blank=True
    )
    # Acceptable moisture loss for stock reconciliation
    acceptable_loss_pct = models.DecimalField(
        'Acceptable Loss %', max_digits=5, decimal_places=2, default=0,
        help_text='Acceptable weight loss percentage for moisture/natural loss'
    )

    is_system = models.BooleanField(
        default=False,
        help_text='System products cannot be deleted'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'products'
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def is_low_stock(self):
        """Check if current stock is below minimum level.
        Produced items with 0 stock are not flagged — they get stock from ginning."""
        if self.source == 'produced' and self.minimum_stock == 0:
            return False
        return self.current_stock < self.minimum_stock

    @property
    def allows_negative_stock(self):
        """Produced items can go negative — stock comes from production, not purchases."""
        return self.source in ('produced', 'both')

    @property
    def stock_value(self):
        """Calculate current stock value based on last purchase price or default."""
        return self.current_stock * self.default_purchase_price

    @property
    def last_purchase_rate(self):
        """Get the last purchase rate for this product."""
        from apps.purchases.models import PurchaseItem
        last = PurchaseItem.objects.filter(
            product=self, purchase__status='final', rate__gt=0
        ).order_by('-purchase__date').first()
        if last:
            return {'rate': last.rate, 'unit': last.unit.abbreviation, 'date': last.purchase.date}
        return None

    def get_stock_in_unit(self, target_unit):
        """Get current stock converted to a different unit."""
        return self.unit.convert_to(self.current_stock, target_unit)

    @classmethod
    def generate_code(cls, category_code):
        """Auto-generate product code based on category."""
        last = cls.objects.filter(
            code__startswith=category_code
        ).order_by('-code').first()
        if last:
            try:
                num = int(last.code.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        return f"{category_code}-{num:04d}"
