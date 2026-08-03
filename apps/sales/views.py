"""
Sales Views — Smart auto-save, instant field updates via HTMX.
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
from .models import Sale, SaleItem


@login_required
def sale_list(request):
    from django.core.paginator import Paginator
    from datetime import date
    sales = Sale.objects.select_related('customer', 'broker').all()
    search = request.GET.get('search', '')
    if search:
        sales = sales.filter(Q(invoice_number__icontains=search)|Q(customer__name__icontains=search))
    status = request.GET.get('status')
    if status:
        sales = sales.filter(status=status)
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    if date_from and date_to:
        sales = sales.filter(date__range=[date_from, date_to])
    paginator = Paginator(sales, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    today = date.today()
    context = {'sales': page_obj, 'page_obj': page_obj, 'search': search, 'selected_status': status,
               'filter_from': date_from or today.replace(day=1), 'filter_to': date_to or today, 'show_status': True}
    if request.htmx:
        return render(request, 'sales/partials/sale_table.html', context)
    return render(request, 'sales/sale_list.html', context)


@login_required
def sale_create(request):
    # Auto-cleanup: delete empty drafts older than 24 hours
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(hours=24)
    for s in Sale.objects.filter(status='draft', created_at__lt=cutoff):
        if not s.items.exists():
            s.items.all().delete()
            s.delete()

    customer = Party.objects.filter(party_type__in=['customer', 'both'], is_active=True).first()
    if not customer:
        messages.error(request, 'Please add at least one customer first!')
        return redirect('parties:party_create')
    sale = Sale(customer=customer, created_by=request.user, status='draft')
    sale.save()
    return redirect('sales:sale_edit', pk=sale.pk)


@login_required
def sale_edit(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    if sale.status == 'void':
        messages.error(request, 'Voided sales cannot be edited. — منسوخ شدہ فروخت میں ترمیم نہیں ہو سکتی۔')
        return redirect('sales:sale_detail', pk=pk)
    from apps.products.models import Category
    categories = Category.objects.filter(is_active=True).order_by('sort_order', 'name')
    products = Product.objects.filter(status='active').select_related('category', 'unit')
    import json
    products_json = json.dumps([
        {'id': p.pk, 'name': p.name, 'category_id': p.category_id,
         'category': p.category.name, 'unit': p.unit.abbreviation}
        for p in products
    ])
    try:
        items = list(sale.items.select_related('product', 'unit').all())
    except Exception:
        # Corrupted decimal data — fix using ORM
        from decimal import Decimal, InvalidOperation
        for item in sale.items.all():
            changed = False
            for field in ['quantity', 'rate', 'net_weight', 'gross_weight', 'tare_weight',
                          'amount', 'net_amount', 'discount']:
                try:
                    val = getattr(item, field)
                    if val is not None:
                        Decimal(str(val))
                except (InvalidOperation, ValueError, TypeError):
                    setattr(item, field, Decimal('0'))
                    changed = True
            if changed:
                item.save()
        items = list(sale.items.select_related('product', 'unit').all())

    context = {
        'sale': sale,
        'items': items,
        'customers': Party.objects.filter(party_type__in=['customer', 'both'], is_active=True),
        'brokers': Party.objects.filter(party_type='broker', is_active=True),
        'transporters': Party.objects.filter(party_type='transporter', is_active=True),
        'categories': categories,
        'products': products,
        'products_json': products_json,
        'units': UnitOfMeasurement.objects.filter(is_active=True),
    }
    return render(request, 'sales/sale_edit.html', context)


@login_required
@require_POST
def sale_save_field(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    is_edit_of_final = sale.status == 'final'
    field = request.POST.get('field')
    value = request.POST.get('value', '')
    ALLOWED = {
        'date', 'customer', 'broker', 'sale_type',
        'vehicle_number', 'transporter', 'bilty_number', 'destination',
        'bardana_charges', 'commission_pct', 'commission_amount',
        'hamali_charges', 'tulai_charges',
        'freight_charges', 'other_charges',
        'sales_tax_pct', 'sales_tax_amount',
        'wht_pct', 'wht_amount',
        'total_discount', 'payment_terms', 'amount_received', 'notes',
    }
    if field not in ALLOWED:
        return HttpResponse('Invalid field', status=400)
    try:
        if field in ('customer', 'broker', 'transporter'):
            setattr(sale, f'{field}_id', int(value) if value else None)
        elif field in ('bardana_charges', 'commission_pct', 'commission_amount',
                       'hamali_charges', 'tulai_charges',
                       'freight_charges', 'other_charges',
                       'sales_tax_pct', 'sales_tax_amount',
                       'wht_pct', 'wht_amount',
                       'total_discount', 'amount_received'):
            dec_val = Decimal(value) if value else Decimal('0')
            if dec_val < 0:
                return HttpResponse('Amount cannot be negative — رقم منفی نہیں ہو سکتی', status=400)
            setattr(sale, field, dec_val)
            # Auto-calculate amounts from percentages
            if field == 'commission_pct' and sale.subtotal > 0:
                sale.commission_amount = (sale.subtotal * dec_val / Decimal('100')).quantize(Decimal('0.01'))
            elif field == 'sales_tax_pct' and sale.subtotal > 0:
                sale.sales_tax_amount = (sale.subtotal * dec_val / Decimal('100')).quantize(Decimal('0.01'))
            elif field == 'wht_pct' and sale.subtotal > 0:
                sale.wht_amount = (sale.subtotal * dec_val / Decimal('100')).quantize(Decimal('0.01'))
        else:
            setattr(sale, field, value)
        sale.save()
        if is_edit_of_final:
            AuditLog.log(user=request.user, action='UPDATE', model_name='Sale',
                         object_id=sale.pk, object_repr=str(sale), request=request,
                         description=f'Finalized sale edited: {sale.invoice_number}, field={field}, value={value}')
        return render(request, 'sales/partials/sale_totals.html', {'sale': sale})
    except (ValueError, InvalidOperation) as e:
        return HttpResponse(str(e), status=400)


@login_required
@require_POST
def sale_add_item(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    product_id = request.POST.get('product')
    if not product_id:
        return HttpResponse('Select a product', status=400)
    product = get_object_or_404(Product, pk=product_id)
    SaleItem.objects.create(
        sale=sale, product=product, unit=product.unit,
        rate=product.default_sale_price, rate_basis=product.unit.abbreviation,
        sort_order=sale.items.count(),
    )
    sale.refresh_from_db()
    return render(request, 'sales/partials/sale_items_and_totals.html', {
        'sale': sale,
        'items': sale.items.select_related('product', 'unit').all(),
        'units': UnitOfMeasurement.objects.filter(is_active=True),
    })


@login_required
@require_POST
def sale_save_item_field(request, pk, item_pk):
    sale = get_object_or_404(Sale, pk=pk)
    item = get_object_or_404(SaleItem, pk=item_pk, sale=sale)
    is_edit_of_final = sale.status == 'final'
    field = request.POST.get('field')
    value = request.POST.get('value', '')
    ALLOWED = {'bags_count', 'quantity', 'rate', 'gross_weight', 'tare_weight', 'moisture_pct', 'trash_pct', 'discount'}
    if field == 'unit':
        item.unit_id = int(value) if value else item.unit_id
    elif field == 'rate_basis':
        old_basis = item.rate_basis or ''
        new_basis = value.strip() if value else ''
        if item.rate and item.rate > 0 and old_basis != new_basis:
            net_kg = item.net_weight or Decimal('0')
            if net_kg > 0:
                if old_basis == 'total':
                    total_amt = item.rate
                else:
                    try:
                        old_unit = UnitOfMeasurement.objects.get(abbreviation=old_basis)
                        old_qty = net_kg / (old_unit.conversion_to_base or Decimal('1'))  # No intermediate rounding
                        total_amt = (old_qty * item.rate).quantize(Decimal('0.01'))
                    except (UnitOfMeasurement.DoesNotExist, Exception):
                        total_amt = ((item.quantity or Decimal('0')) * item.rate).quantize(Decimal('0.01'))
                if new_basis == 'total':
                    item.rate = total_amt.quantize(Decimal('0.01'))
                else:
                    try:
                        new_unit = UnitOfMeasurement.objects.get(abbreviation=new_basis)
                        new_qty = net_kg / (new_unit.conversion_to_base or Decimal('1'))  # No intermediate rounding
                        if new_qty > 0:
                            item.rate = (total_amt / new_qty).quantize(Decimal('0.01'))
                    except (UnitOfMeasurement.DoesNotExist, Exception):
                        pass
        item.rate_basis = new_basis
    elif field in ALLOWED:
        try:
            setattr(item, field, Decimal(value) if value else Decimal('0'))
        except InvalidOperation:
            return HttpResponse('Invalid number', status=400)
    else:
        return HttpResponse('Invalid field', status=400)
    item.save()
    if is_edit_of_final:
        AuditLog.log(user=request.user, action='UPDATE', model_name='SaleItem',
                     object_id=item.pk, object_repr=str(item), request=request,
                     description=f'Finalized sale item edited: {sale.invoice_number}, field={field}, value={value}')
    sale.refresh_from_db()
    return render(request, 'sales/partials/sale_items_and_totals.html', {
        'sale': sale,
        'items': sale.items.select_related('product', 'unit').all(),
        'units': UnitOfMeasurement.objects.filter(is_active=True),
    })


@login_required
@require_POST
def sale_delete_item(request, pk, item_pk):
    sale = get_object_or_404(Sale, pk=pk)
    item = get_object_or_404(SaleItem, pk=item_pk, sale=sale)
    if sale.status == 'final':
        AuditLog.log(user=request.user, action='DELETE', model_name='SaleItem',
                     object_id=item.pk, object_repr=str(item), request=request,
                     description=f'Item removed from finalized sale {sale.invoice_number}: {item.product.name}')
    item.delete()
    sale.save()
    sale.refresh_from_db()
    return render(request, 'sales/partials/sale_items_and_totals.html', {
        'sale': sale,
        'items': sale.items.select_related('product', 'unit').all(),
        'units': UnitOfMeasurement.objects.filter(is_active=True),
    })


@login_required
@require_POST
def sale_finalize(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    if sale.status != 'draft':
        messages.error(request, 'Already finalized.')
        return redirect('sales:sale_list')
    if not sale.items.exists():
        messages.error(request, 'Add at least one item.')
        return redirect('sales:sale_edit', pk=pk)
    # Check stock availability (skip for produced items — they can go negative)
    for item in sale.items.select_related('product').all():
        product = item.product
        if not product.allows_negative_stock and item.quantity > product.current_stock:
            messages.error(request,
                f'Not enough stock for {product.name}: '
                f'need {item.quantity}, have {product.current_stock} — '
                f'{product.name} کا اسٹاک کافی نہیں')
            return redirect('sales:sale_edit', pk=pk)
    sale.finalize()
    AuditLog.log(
        user=request.user, action='CREATE', model_name='Sale',
        object_id=sale.pk, object_repr=str(sale), request=request,
        description=f'Sale finalized: {sale.invoice_number}'
    )
    messages.success(request, f'Sale {sale.invoice_number} finalized! Stock updated.')
    return redirect('sales:sale_list')


@login_required
@require_POST
def sale_delete(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    reason = request.POST.get('reason', '').strip()

    if sale.status == 'draft':
        sale.items.all().delete()
        sale.delete()
        AuditLog.log(user=request.user, action='DELETE', model_name='Sale',
                     object_id=pk, description='Draft sale deleted')
        messages.success(request, 'Draft sale deleted.')
    elif sale.status == 'final':
        # Reverse stock
        for item in sale.items.all():
            item.product.current_stock += item.quantity
            item.product.save(update_fields=['current_stock'])

        # Reverse customer balance (use grand_total, not balance_due)
        sale.customer.current_balance -= sale.grand_total
        sale.customer.save(update_fields=['current_balance'])

        # Reverse journal
        from apps.accounting.models import JournalEntry
        je = JournalEntry.objects.filter(sale=sale).first()
        if je and je.is_posted:
            for line in je.lines.all():
                line.account.current_balance -= (line.debit - line.credit)
                line.account.save(update_fields=['current_balance'])
            je.is_posted = False
            je.save(update_fields=['is_posted'])

        sale.status = 'void'
        sale.save()
        AuditLog.log(user=request.user, action='DELETE', model_name='Sale',
                     object_id=pk, object_repr=str(sale), request=request,
                     description=f'Sale VOIDED: {sale.invoice_number}. '
                                 f'Reason: {reason or "Not specified"}. '
                                 f'Stock reversed, balance reversed, journal reversed.')
        messages.success(request,
            f'Sale {sale.invoice_number} voided — stock, balance, and journal reversed.')
    else:
        messages.error(request, 'Cannot void this sale.')
    return redirect('sales:sale_list')


# ─── SALE RETURNS ────────────────────────────
@login_required
def sale_return_list(request):
    from .models import SaleReturn
    returns = SaleReturn.objects.select_related('sale', 'customer').all()
    return render(request, 'sales/return_list.html', {'returns': returns})


@login_required
def sale_return_create(request, sale_pk=None):
    from .models import SaleReturn, SaleReturnItem
    if request.method == 'POST':
        sale_id = request.POST.get('sale')
        sale = get_object_or_404(Sale, pk=sale_id)
        sr = SaleReturn(sale=sale, customer=sale.customer,
                        reason=request.POST.get('reason', ''), created_by=request.user)
        sr.save()
        total = Decimal('0')
        for item in sale.items.all():
            qty = request.POST.get(f'return_qty_{item.pk}', '0')
            qty = Decimal(qty) if qty else Decimal('0')
            if qty > 0:
                SaleReturnItem.objects.create(sale_return=sr, product=item.product, quantity=qty, rate=item.rate)
                total += qty * item.rate
                item.product.current_stock += qty
                item.product.save(update_fields=['current_stock'])
        sr.total_amount = total
        sr.status = 'final'
        sr.save()
        sale.customer.current_balance -= total
        sale.customer.save(update_fields=['current_balance'])
        messages.success(request, f'Sale return {sr.return_number} created — ₨{total:,.0f}')
        return redirect('sales:return_list')
    
    sale = get_object_or_404(Sale, pk=sale_pk, status='final') if sale_pk else None
    sales_list = Sale.objects.filter(status='final').select_related('customer')
    return render(request, 'sales/return_form.html', {
        'sale': sale, 'sales': sales_list,
        'items': sale.items.select_related('product').all() if sale else [],
        'title': 'Sale Return — واپسی'
    })


@login_required
def sale_detail(request, pk):
    sale = get_object_or_404(Sale.objects.select_related('customer', 'broker'), pk=pk)
    items = sale.items.select_related('product', 'unit').all()
    dup_warning = None
    if sale.status == 'final' and sale.grand_total:
        dupes = Sale.objects.filter(
            customer=sale.customer, grand_total=sale.grand_total,
            date=sale.date, status='final'
        ).exclude(pk=sale.pk)
        if dupes.exists():
            dup_nums = ', '.join(d.invoice_number for d in dupes[:3])
            dup_warning = (f'Similar sale(s) found on same date, same customer, same amount: {dup_nums}. '
                          f'اسی تاریخ، گاہک اور رقم کی فروخت پہلے سے موجود ہے۔')
    return render(request, 'sales/sale_detail.html', {
        'sale': sale, 'items': items, 'duplicate_warning': dup_warning,
    })


@login_required
@require_POST
def sale_cleanup_drafts(request):
    """Delete all empty draft sales."""
    count = 0
    for s in Sale.objects.filter(status='draft'):
        if not s.items.exists():
            s.delete()
            count += 1
    if count:
        from apps.authentication.models import AuditLog
        AuditLog.log(user=request.user, action='DELETE', model_name='Sale',
                     description=f'Cleaned up {count} empty draft sales')
        messages.success(request, f'Deleted {count} empty drafts — {count} خالی مسودے حذف ہو گئے')
    else:
        messages.info(request, 'No empty drafts to clean up')
    return redirect('sales:sale_list')
