from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from apps.products.models import Product
from .models import StockMovement


@login_required
def stock_overview(request):
    products = Product.objects.filter(status='active').select_related('category', 'unit')
    return render(request, 'inventory/stock_overview.html', {'products': products})


@login_required
def stock_movements(request):
    movements = StockMovement.objects.select_related('product', 'unit').all()[:100]
    return render(request, 'inventory/stock_movements.html', {'movements': movements})


# ─── STOCK ADJUSTMENT ─────────────────
@login_required
def stock_adjustment(request):
    from apps.products.models import Product, UnitOfMeasurement
    if request.method == 'POST':
        product_id = request.POST.get('product')
        if not product_id:
            messages.error(request, 'Please select a product — پروڈکٹ منتخب کریں')
            products = Product.objects.filter(status='active').select_related('unit')
            return render(request, 'inventory/stock_adjustment.html', {'products': products})
        product = get_object_or_404(Product, pk=product_id)
        adj_type = request.POST.get('adj_type', 'adjustment_in')
        qty = Decimal(request.POST.get('quantity') or '0')
        reason = request.POST.get('reason', '')
        if qty > 0:
            if adj_type == 'adjustment_in':
                product.current_stock += qty
            else:
                product.current_stock -= qty
            product.save(update_fields=['current_stock'])
            StockMovement.objects.create(
                product=product, movement_type=adj_type,
                quantity=qty if adj_type == 'adjustment_in' else -qty,
                unit=product.unit, balance_after=product.current_stock,
                notes=reason, created_by=request.user,
            )
            from apps.authentication.models import AuditLog
            AuditLog.log(user=request.user, action='UPDATE', model_name='Product',
                         object_id=product.pk, object_repr=str(product), request=request,
                         description=f'Stock adjustment: {product.name} '
                                     f'{"+" if adj_type == "adjustment_in" else "-"}{qty} {product.unit.abbreviation}. '
                                     f'Reason: {reason or "Not specified"}. '
                                     f'New stock: {product.current_stock}')
            messages.success(request, f'Stock adjusted: {product.name} {"+" if adj_type == "adjustment_in" else "-"}{qty}')
            return redirect('inventory:stock_overview')
    
    products = Product.objects.filter(status='active').select_related('unit')
    return render(request, 'inventory/stock_adjustment.html', {
        'products': products, 'title': 'Stock Adjustment — اسٹاک ایڈجسٹمنٹ',
        'back_url': '/inventory/', 'submit_label': 'Adjust', 'submit_label_ur': 'ایڈجسٹ'
    })
