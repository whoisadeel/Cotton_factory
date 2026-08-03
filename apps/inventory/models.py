"""
Inventory / Stock tracking models.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class StockMovement(models.Model):
    """Every stock change is recorded here — full traceability."""
    MOVEMENT_TYPES = [
        ('purchase', 'Purchase Inward (خریداری)'),
        ('sale', 'Sale Outward (فروخت)'),
        ('purchase_return', 'Purchase Return'),
        ('sale_return', 'Sale Return'),
        ('adjustment_in', 'Adjustment In'),
        ('adjustment_out', 'Adjustment Out'),
        ('processing_in', 'Processing Input'),
        ('processing_out', 'Processing Output'),
    ]

    date = models.DateField(default=timezone.now)
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.ForeignKey('products.UnitOfMeasurement', on_delete=models.PROTECT)
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_after = models.DecimalField(max_digits=15, decimal_places=3, default=0)

    # Reference to source
    purchase = models.ForeignKey('purchases.Purchase', on_delete=models.SET_NULL, null=True, blank=True)
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True)

    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'stock_movements'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.get_movement_type_display()} — {self.product.name} × {self.quantity}"
