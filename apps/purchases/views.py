"""
Purchase Views — Smart auto-save, instant field updates via HTMX.
"""
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.db.models import Q

from apps.authentication.models import AuditLog
from apps.parties.models import Party
from apps.products.models import Product, UnitOfMeasurement
from .models import Purchase, PurchaseItem


@login_required
def purchase_list(request):
    from django.core.paginator import Paginator
    from datetime import date, timedelta
    
    purchases = Purchase.objects.select_related('supplier', 'broker').all()
    search = request.GET.get('search', '')
    if search:
        purchases = purchases.filter(
            Q(purchase_number__icontains=search) |
            Q(supplier__name__icontains=search) |
            Q(bill_number__icontains=search)
        )
    status = request.GET.get('status')
    if status:
        purchases = purchases.filter(status=status)
    
    # Date filter
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    if date_from and date_to:
        purchases = purchases.filter(date__range=[date_from, date_to])
    
    # Pagination
    paginator = Paginator(purchases, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    today = date.today()
    context = {
        'purchases': page_obj, 'page_obj': page_obj,
        'search': search, 'selected_status': status,
        'filter_from': date_from or today.replace(day=1),
        'filter_to': date_to or today,
        'show_status': True,
    }
    if request.htmx:
        return render(request, 'purchases/partials/purchase_table.html', context)
    return render(request, 'purchases/purchase_list.html', context)


@login_required
def purchase_create(request):
    """Create a new draft purchase and redirect to the smart editor."""
    # Auto-cleanup: delete empty drafts older than 24 hours
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(hours=24)
    empty_old = Purchase.objects.filter(status='draft', created_at__lt=cutoff)
    for p in empty_old:
        if not p.items.exists():
            p.items.all().delete()
            p.delete()

    purchase = Purchase(
        supplier_id=Party.objects.filter(party_type__in=['supplier', 'both'], is_active=True).first().pk if Party.objects.filter(party_type__in=['supplier', 'both'], is_active=True).exists() else None,
        created_by=request.user,
        status='draft',
    )
    if purchase.supplier_id:
        purchase.save()
        return redirect('purchases:purchase_edit', pk=purchase.pk)
    else:
        messages.error(request, 'Please add at least one supplier first!')
        return redirect('parties:party_create')


@login_required
def purchase_edit(request, pk):
    """Smart purchase editor with instant-save fields."""
    purchase = get_object_or_404(Purchase, pk=pk)
    if purchase.status == 'void':
        messages.error(request, 'Voided purchases cannot be edited. — منسوخ شدہ خریداری میں ترمیم نہیں ہو سکتی۔')
        return redirect('purchases:purchase_detail', pk=pk)
    suppliers = Party.objects.filter(party_type__in=['supplier', 'both'], is_active=True)
    brokers = Party.objects.filter(party_type='broker', is_active=True)
    transporters = Party.objects.filter(party_type='transporter', is_active=True)
    from apps.products.models import Category
    categories = Category.objects.filter(is_active=True).order_by('sort_order', 'name')
    products = Product.objects.filter(status='active').select_related('category', 'unit')
    units = UnitOfMeasurement.objects.filter(is_active=True)

    # Build products JSON for Alpine.js category filter
    import json
    products_json = json.dumps([
        {'id': p.pk, 'name': p.name, 'category_id': p.category_id,
         'category': p.category.name, 'unit': p.unit.abbreviation}
        for p in products
    ])

    # Load items — fix any corrupted decimal values via ORM
    try:
        items = list(purchase.items.select_related('product', 'unit').all())
    except Exception:
        # Corrupted decimal data — fix using ORM
        from decimal import Decimal, InvalidOperation
        for item in purchase.items.all():
            changed = False
            for field in ['quantity', 'rate', 'net_weight', 'gross_weight', 'tare_weight',
                          'amount', 'net_amount', 'discount']:
                try:
                    val = getattr(item, field)
                    if val is not None:
                        Decimal(str(val))  # Test if valid
                except (InvalidOperation, ValueError, TypeError):
                    setattr(item, field, Decimal('0'))
                    changed = True
            if changed:
                item.save()
        items = list(purchase.items.select_related('product', 'unit').all())
        messages.warning(request, 'Some item values were auto-corrected — کچھ اقدار خود بخود درست کی گئیں')

    context = {
        'purchase': purchase,
        'items': items,
        'suppliers': suppliers,
        'brokers': brokers,
        'transporters': transporters,
        'categories': categories,
        'products': products,
        'products_json': products_json,
        'units': units,
    }
    return render(request, 'purchases/purchase_edit.html', context)


@login_required
@require_POST
def purchase_save_field(request, pk):
    """HTMX instant-save: save a single field on the purchase."""
    purchase = get_object_or_404(Purchase, pk=pk)
    is_edit_of_final = purchase.status == 'final'

    field = request.POST.get('field')
    value = request.POST.get('value', '')

    ALLOWED_FIELDS = {
        'date', 'supplier', 'broker', 'bill_number', 'purchase_type',
        'vehicle_number', 'transporter', 'bilty_number', 'gate_entry_number',
        'bardana_charges', 'commission_pct', 'commission_amount',
        'hamali_charges', 'tulai_charges',
        'mandi_fee', 'freight_charges', 'other_charges',
        'sales_tax_pct', 'sales_tax_amount',
        'wht_pct', 'wht_amount',
        'total_discount', 'payment_terms', 'amount_paid', 'notes',
    }

    if field not in ALLOWED_FIELDS:
        return HttpResponse('Invalid field', status=400)

    try:
        # Handle FK fields
        if field in ('supplier', 'broker', 'transporter'):
            field = f'{field}_id'
            value = int(value) if value else None
        # Handle decimal fields — reject negative values
        elif field in ('bardana_charges', 'commission_pct', 'commission_amount',
                       'hamali_charges', 'tulai_charges', 'mandi_fee',
                       'freight_charges', 'other_charges',
                       'sales_tax_pct', 'sales_tax_amount',
                       'wht_pct', 'wht_amount',
                       'total_discount', 'amount_paid'):
            value = Decimal(value) if value else Decimal('0')
            if value < 0:
                from django.http import HttpResponse as HR
                return HR('Amount cannot be negative — رقم منفی نہیں ہو سکتی', status=400)

        setattr(purchase, field, value)

        # Auto-calculate amounts from percentages
        if field == 'commission_pct' and purchase.subtotal > 0:
            purchase.commission_amount = (purchase.subtotal * value / Decimal('100')).quantize(Decimal('0.01'))
        elif field == 'sales_tax_pct' and purchase.subtotal > 0:
            purchase.sales_tax_amount = (purchase.subtotal * value / Decimal('100')).quantize(Decimal('0.01'))
        elif field == 'wht_pct' and purchase.subtotal > 0:
            purchase.wht_amount = (purchase.subtotal * value / Decimal('100')).quantize(Decimal('0.01'))

        purchase.save()

        # Log change if editing a finalized purchase
        if is_edit_of_final:
            AuditLog.log(user=request.user, action='UPDATE', model_name='Purchase',
                         object_id=purchase.pk, object_repr=str(purchase), request=request,
                         description=f'Finalized purchase edited: {purchase.purchase_number}, field={field}, new_value={value}')

        # Return updated totals
        return render(request, 'purchases/partials/purchase_totals.html', {
            'purchase': purchase,
        })
    except (ValueError, InvalidOperation) as e:
        return HttpResponse(str(e), status=400)


@login_required
@require_POST
def purchase_add_item(request, pk):
    """Add a line item to purchase."""
    purchase = get_object_or_404(Purchase, pk=pk)

    product_id = request.POST.get('product')
    if not product_id:
        return HttpResponse('Select a product', status=400)

    product = get_object_or_404(Product, pk=product_id)
    item = PurchaseItem.objects.create(
        purchase=purchase,
        product=product,
        unit=product.unit,
        rate=product.default_purchase_price,
        rate_basis=product.unit.abbreviation,  # default rate per product's unit
        sort_order=purchase.items.count(),
    )

    items = purchase.items.select_related('product', 'unit').all()
    purchase.refresh_from_db()
    return render(request, 'purchases/partials/purchase_items_and_totals.html', {
        'purchase': purchase,
        'items': items,
        'units': UnitOfMeasurement.objects.filter(is_active=True),
    })


@login_required
@require_POST
def purchase_save_item_field(request, pk, item_pk):
    """Instant-save a single field on a purchase item."""
    purchase = get_object_or_404(Purchase, pk=pk)
    item = get_object_or_404(PurchaseItem, pk=item_pk, purchase=purchase)
    is_edit_of_final = purchase.status == 'final'

    field = request.POST.get('field')
    value = request.POST.get('value', '')

    ALLOWED_ITEM_FIELDS = {
        'bags_count', 'quantity', 'rate',
        'gross_weight', 'tare_weight',
        'moisture_pct', 'trash_pct', 'staple_length', 'discount',
    }

    if field == 'unit':
        item.unit_id = int(value) if value else item.unit_id
    elif field == 'rate_basis':
        old_basis = item.rate_basis or ''
        new_basis = value.strip() if value else ''
        # Auto-convert rate when switching basis
        if item.rate and item.rate > 0 and old_basis != new_basis:
            net_kg = item.net_weight or Decimal('0')
            if net_kg > 0:
                # Step 1: Calculate total amount from OLD basis
                if old_basis == 'total':
                    total_amt = item.rate
                else:
                    # old_basis is a unit abbreviation
                    try:
                        old_unit = UnitOfMeasurement.objects.get(abbreviation=old_basis)
                        old_conv = old_unit.conversion_to_base or Decimal('1')
                        old_qty = net_kg / old_conv  # No intermediate rounding
                        total_amt = (old_qty * item.rate).quantize(Decimal('0.01'))
                    except (UnitOfMeasurement.DoesNotExist, Exception):
                        total_amt = ((item.quantity or Decimal('0')) * item.rate).quantize(Decimal('0.01'))

                # Step 2: Convert total amount to NEW basis rate
                if new_basis == 'total':
                    item.rate = total_amt.quantize(Decimal('0.01'))
                else:
                    try:
                        new_unit = UnitOfMeasurement.objects.get(abbreviation=new_basis)
                        new_conv = new_unit.conversion_to_base or Decimal('1')
                        new_qty = net_kg / new_conv  # No intermediate rounding
                        if new_qty > 0:
                            item.rate = (total_amt / new_qty).quantize(Decimal('0.01'))
                    except (UnitOfMeasurement.DoesNotExist, Exception):
                        pass
        item.rate_basis = new_basis
    elif field in ALLOWED_ITEM_FIELDS:
        try:
            setattr(item, field, Decimal(value) if value else Decimal('0'))
        except InvalidOperation:
            return HttpResponse('Invalid number', status=400)
    else:
        return HttpResponse('Invalid field', status=400)

    item.save()  # model.save() auto-calculates: net_weight, amount=qty×rate
    if is_edit_of_final:
        AuditLog.log(user=request.user, action='UPDATE', model_name='PurchaseItem',
                     object_id=item.pk, object_repr=str(item), request=request,
                     description=f'Finalized purchase item edited: {purchase.purchase_number}, field={field}, value={value}')
    purchase.refresh_from_db()

    items = purchase.items.select_related('product', 'unit').all()
    return render(request, 'purchases/partials/purchase_items_and_totals.html', {
        'purchase': purchase,
        'items': items,
        'units': UnitOfMeasurement.objects.filter(is_active=True),
    })


@login_required
@require_POST
def purchase_delete_item(request, pk, item_pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    item = get_object_or_404(PurchaseItem, pk=item_pk, purchase=purchase)
    if purchase.status == 'final':
        AuditLog.log(user=request.user, action='DELETE', model_name='PurchaseItem',
                     object_id=item.pk, object_repr=str(item), request=request,
                     description=f'Item removed from finalized purchase {purchase.purchase_number}: {item.product.name}')
    item.delete()
    purchase.save()  # Recalculates
    purchase.refresh_from_db()
    items = purchase.items.select_related('product', 'unit').all()
    return render(request, 'purchases/partials/purchase_items_and_totals.html', {
        'purchase': purchase,
        'items': items,
        'units': UnitOfMeasurement.objects.filter(is_active=True),
    })


@login_required
@require_POST
def purchase_finalize(request, pk):
    """Finalize the purchase — updates stock and supplier balance."""
    purchase = get_object_or_404(Purchase, pk=pk)
    if purchase.status != 'draft':
        messages.error(request, 'This purchase is already finalized.')
        return redirect('purchases:purchase_list')

    if not purchase.items.exists():
        messages.error(request, 'Add at least one item before finalizing.')
        return redirect('purchases:purchase_edit', pk=pk)

    purchase.finalize()
    AuditLog.log(
        user=request.user, action='CREATE', model_name='Purchase',
        object_id=purchase.pk, object_repr=str(purchase), request=request,
        description=f'Purchase finalized: {purchase.purchase_number}'
    )
    messages.success(request, f'Purchase {purchase.purchase_number} finalized! Stock updated.')
    return redirect('purchases:purchase_list')


@login_required
@require_POST
def purchase_delete(request, pk):
    """Void a purchase — draft is deleted, finalized is voided with full reversal."""
    purchase = get_object_or_404(Purchase, pk=pk)
    reason = request.POST.get('reason', '').strip()

    if purchase.status == 'draft':
        num = purchase.purchase_number
        purchase.items.all().delete()
        purchase.delete()
        AuditLog.log(user=request.user, action='DELETE', model_name='Purchase',
                     object_id=pk, object_repr=num, request=request,
                     description=f'Draft purchase deleted: {num}')
        messages.success(request, 'Draft purchase deleted.')
    elif purchase.status == 'final':
        # Reverse stock
        for item in purchase.items.all():
            item.product.current_stock -= item.quantity
            item.product.save(update_fields=['current_stock'])

        # Reverse supplier balance (use grand_total, not balance_due)
        purchase.supplier.current_balance += purchase.grand_total
        purchase.supplier.save(update_fields=['current_balance'])

        # Reverse journal entry
        from apps.accounting.models import JournalEntry
        je = JournalEntry.objects.filter(purchase=purchase).first()
        if je and je.is_posted:
            for line in je.lines.all():
                line.account.current_balance -= (line.debit - line.credit)
                line.account.save(update_fields=['current_balance'])
            je.is_posted = False
            je.save(update_fields=['is_posted'])

        purchase.status = 'void'
        purchase.save()
        AuditLog.log(user=request.user, action='DELETE', model_name='Purchase',
                     object_id=pk, object_repr=str(purchase), request=request,
                     description=f'Purchase VOIDED: {purchase.purchase_number}. '
                                 f'Reason: {reason or "Not specified"}. '
                                 f'Stock reversed, balance reversed, journal reversed.')
        messages.success(request,
            f'Purchase {purchase.purchase_number} voided — stock, balance, and journal reversed. '
            f'Create a new purchase with correct details.')
    else:
        messages.error(request, 'Cannot void this purchase.')
    return redirect('purchases:purchase_list')


# ─── PURCHASE RETURNS ────────────────────────────
@login_required
def purchase_return_list(request):
    from .models import PurchaseReturn
    returns = PurchaseReturn.objects.select_related('purchase', 'supplier').all()
    return render(request, 'purchases/return_list.html', {'returns': returns})


@login_required
def purchase_return_create(request, purchase_pk=None):
    from .models import PurchaseReturn, PurchaseReturnItem
    if request.method == 'POST':
        purchase_id = request.POST.get('purchase')
        purchase = get_object_or_404(Purchase, pk=purchase_id)
        pr = PurchaseReturn(purchase=purchase, supplier=purchase.supplier, 
                            reason=request.POST.get('reason', ''), created_by=request.user)
        pr.save()
        # Add return items
        total = Decimal('0')
        for item in purchase.items.all():
            qty = request.POST.get(f'return_qty_{item.pk}', '0')
            qty = Decimal(qty) if qty else Decimal('0')
            if qty > 0:
                PurchaseReturnItem.objects.create(
                    purchase_return=pr, product=item.product,
                    quantity=qty, rate=item.rate
                )
                total += qty * item.rate
                # Reverse stock
                item.product.current_stock -= qty
                item.product.save(update_fields=['current_stock'])
        pr.total_amount = total
        pr.status = 'final'
        pr.save()
        # Adjust supplier balance
        purchase.supplier.current_balance += total
        purchase.supplier.save(update_fields=['current_balance'])
        messages.success(request, f'Purchase return {pr.return_number} created — ₨{total:,.0f}')
        return redirect('purchases:return_list')
    
    purchase = get_object_or_404(Purchase, pk=purchase_pk, status='final') if purchase_pk else None
    purchases = Purchase.objects.filter(status='final').select_related('supplier')
    return render(request, 'purchases/return_form.html', {
        'purchase': purchase, 'purchases': purchases,
        'items': purchase.items.select_related('product').all() if purchase else [],
        'title': 'Purchase Return — واپسی'
    })


@login_required
def purchase_detail(request, pk):
    purchase = get_object_or_404(Purchase.objects.select_related('supplier', 'broker', 'transporter'), pk=pk)
    items = purchase.items.select_related('product', 'unit').all()
    # Duplicate detection: same supplier, same amount, same day
    dup_warning = None
    if purchase.status == 'final' and purchase.grand_total:
        dupes = Purchase.objects.filter(
            supplier=purchase.supplier, grand_total=purchase.grand_total,
            date=purchase.date, status='final'
        ).exclude(pk=purchase.pk)
        if dupes.exists():
            dup_nums = ', '.join(d.purchase_number for d in dupes[:3])
            dup_warning = (f'Similar purchase(s) found on same date, same supplier, same amount: {dup_nums}. '
                          f'اسی تاریخ، سپلائر اور رقم کی خریداری پہلے سے موجود ہے۔')
    return render(request, 'purchases/purchase_detail.html', {
        'purchase': purchase, 'items': items, 'duplicate_warning': dup_warning,
    })


@login_required
@require_POST
def purchase_cleanup_drafts(request):
    """Delete all empty draft purchases."""
    count = 0
    for p in Purchase.objects.filter(status='draft'):
        if not p.items.exists():
            p.delete()
            count += 1
    if count:
        AuditLog.log(user=request.user, action='DELETE', model_name='Purchase',
                     description=f'Cleaned up {count} empty draft purchases')
        messages.success(request, f'Deleted {count} empty drafts — {count} خالی مسودے حذف ہو گئے')
    else:
        messages.info(request, 'No empty drafts to clean up')
    return redirect('purchases:purchase_list')
