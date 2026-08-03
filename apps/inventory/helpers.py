"""
Inventory helper functions — stock processing.
"""
from .models import StockMovement
from apps.products.models import Product


def process_purchase_stock(purchase):
    """Create stock movements for a finalized purchase."""
    for item in purchase.items.all():
        product = item.product
        product.current_stock += item.quantity
        product.save(update_fields=['current_stock'])

        StockMovement.objects.create(
            date=purchase.date,
            product=product,
            movement_type='purchase',
            quantity=item.quantity,
            unit=item.unit,
            rate=item.rate,
            balance_after=product.current_stock,
            purchase=purchase,
            created_by=purchase.created_by,
        )


def process_sale_stock(sale):
    """Create stock movements for a finalized sale."""
    for item in sale.items.all():
        product = item.product
        product.current_stock -= item.quantity
        product.save(update_fields=['current_stock'])

        StockMovement.objects.create(
            date=sale.date,
            product=product,
            movement_type='sale',
            quantity=-item.quantity,
            unit=item.unit,
            rate=item.rate,
            balance_after=product.current_stock,
            sale=sale,
            created_by=sale.created_by,
        )
