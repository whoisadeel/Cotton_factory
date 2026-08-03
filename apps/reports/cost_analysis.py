"""
Purchase Cost Calculator — Select purchases, check/uncheck them,
see live cost per KG/Maund. All calculation happens client-side with Alpine.js.
"""
from datetime import date
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from apps.purchases.models import Purchase, PurchaseItem
from apps.products.models import Product, UnitOfMeasurement, Category
from apps.parties.models import Party


@login_required
def purchase_cost_analysis(request):
    today = timezone.now().date()

    # Parse filters
    product_id = request.GET.get('product')
    category_id = request.GET.get('category')
    from_date = request.GET.get('from')
    to_date = request.GET.get('to')
    supplier_id = request.GET.get('supplier')
    display_unit = request.GET.get('unit', 'MND')

    try:
        from_date = date.fromisoformat(from_date) if from_date else today.replace(day=1)
    except (ValueError, TypeError):
        from_date = today.replace(day=1)
    try:
        to_date = date.fromisoformat(to_date) if to_date else today
    except (ValueError, TypeError):
        to_date = today

    # Dropdowns
    products = Product.objects.filter(status='active').select_related('category', 'unit').order_by('name')
    categories = Category.objects.filter(is_active=True).order_by('name')
    suppliers = Party.objects.filter(party_type__in=['supplier', 'both'], is_active=True).order_by('name')
    units = UnitOfMeasurement.objects.filter(is_active=True, unit_type='weight').order_by('sort_order')

    # Get display unit conversion factor
    try:
        disp_unit_obj = UnitOfMeasurement.objects.get(abbreviation=display_unit)
    except UnitOfMeasurement.DoesNotExist:
        disp_unit_obj = UnitOfMeasurement.objects.filter(abbreviation='MND').first() or UnitOfMeasurement.objects.first()
    disp_conv = float(disp_unit_obj.conversion_to_base or 1)

    purchase_rows = []

    # Build query
    items_qs = PurchaseItem.objects.filter(
        purchase__status='final',
        purchase__date__range=[from_date, to_date],
    ).select_related('purchase', 'purchase__supplier', 'unit', 'product', 'product__category')

    if product_id:
        items_qs = items_qs.filter(product_id=product_id)
    elif category_id:
        items_qs = items_qs.filter(product__category_id=category_id)
    else:
        # Need at least one filter
        items_qs = items_qs.none()

    if supplier_id:
        items_qs = items_qs.filter(purchase__supplier_id=supplier_id)

    items_qs = items_qs.order_by('purchase__date')

    for item in items_qs:
        p = item.purchase
        unit_conv = float(item.unit.conversion_to_base or 1)
        weight_kg = float(item.quantity) * unit_conv
        if weight_kg <= 0:
            continue

        base_cost = float(item.net_amount)

        # Proportional share of purchase-level charges
        if float(p.subtotal) > 0:
            share_ratio = float(item.net_amount) / float(p.subtotal)
        else:
            share_ratio = 1.0

        extra = float(
            p.bardana_charges + p.commission_amount + p.hamali_charges +
            p.tulai_charges + p.mandi_fee + p.freight_charges +
            p.other_charges + p.sales_tax_amount + p.wht_amount -
            p.total_discount
        ) * share_ratio

        all_in = base_cost + extra
        weight_disp = weight_kg / disp_conv if disp_conv else weight_kg

        purchase_rows.append({
            'id': item.pk,
            'date': p.date.isoformat(),
            'date_display': p.date.strftime('%d/%m/%Y'),
            'purchase_number': p.purchase_number,
            'supplier': p.supplier.name,
            'product': item.product.name,
            'bags': int(item.bags_count) if item.bags_count else 0,
            'qty': float(item.quantity),
            'unit': item.unit.abbreviation,
            'rate': float(item.rate),
            'weight_kg': round(weight_kg, 2),
            'weight_disp': round(weight_disp, 3),
            'base_cost': round(base_cost, 2),
            'extra': round(extra, 2),
            'all_in': round(all_in, 2),
        })

    has_filter = bool(product_id or category_id)

    context = {
        'products': products,
        'categories': categories,
        'suppliers': suppliers,
        'units': units,
        'selected_product': product_id or '',
        'selected_category': category_id or '',
        'selected_supplier': supplier_id or '',
        'display_unit': display_unit,
        'disp_unit_name': disp_unit_obj.name,
        'disp_unit_abbr': disp_unit_obj.abbreviation,
        'disp_conv': disp_conv,
        'from_date': from_date,
        'to_date': to_date,
        'purchase_rows_json': __import__('json').dumps(purchase_rows),
        'has_filter': has_filter,
        'today': today,
    }
    return render(request, 'reports/purchase_cost_analysis.html', context)
