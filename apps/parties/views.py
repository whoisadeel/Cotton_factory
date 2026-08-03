"""
Party Management Views
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from apps.authentication.models import AuditLog
from .models import Party
from .forms import PartyForm


@login_required
def party_list(request):
    """List all parties with search and filter."""
    parties = Party.objects.all()

    search = request.GET.get('search', '')
    if search:
        parties = parties.filter(
            Q(name__icontains=search) |
            Q(name_urdu__icontains=search) |
            Q(code__icontains=search) |
            Q(phone_primary__icontains=search) |
            Q(city__icontains=search) |
            Q(cnic__icontains=search)
        )

    party_type = request.GET.get('type')
    if party_type:
        parties = parties.filter(party_type=party_type)

    status_filter = request.GET.get('status')
    if status_filter == 'active':
        parties = parties.filter(is_active=True)
    elif status_filter == 'inactive':
        parties = parties.filter(is_active=False)

    context = {
        'parties': parties,
        'search': search,
        'selected_type': party_type,
        'selected_status': status_filter,
        'type_choices': Party.TYPE_CHOICES,
    }

    if request.htmx:
        return render(request, 'parties/partials/party_table.html', context)

    from django.core.paginator import Paginator
    paginator = Paginator(parties, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    context['parties'] = page_obj
    context['page_obj'] = page_obj
    return render(request, 'parties/party_list.html', context)


@login_required
def party_create(request):
    """Create a new party."""
    if request.method == 'POST':
        form = PartyForm(request.POST)
        if form.is_valid():
            party = form.save()
            AuditLog.log(
                user=request.user, action='CREATE',
                model_name='Party', object_id=party.pk,
                object_repr=str(party), request=request,
                description=f'Party created: {party.name}'
            )
            messages.success(request, f'Party "{party.name}" created successfully.')
            if request.htmx:
                return HttpResponse(status=204, headers={'HX-Redirect': '/parties/'})
            return redirect('parties:party_list')
    else:
        initial_type = request.GET.get('type', 'supplier')
        form = PartyForm(initial={'party_type': initial_type})

    template = 'parties/partials/party_form.html' if request.htmx else 'parties/party_form.html'
    return render(request, template, {'form': form, 'title': 'Add New Party'})


@login_required
def party_edit(request, pk):
    """Edit an existing party."""
    party = get_object_or_404(Party, pk=pk)
    if request.method == 'POST':
        form = PartyForm(request.POST, instance=party)
        if form.is_valid():
            party = form.save()
            AuditLog.log(
                user=request.user, action='UPDATE',
                model_name='Party', object_id=party.pk,
                object_repr=str(party), request=request,
                changes=form.changed_data,
                description=f'Party updated: {party.name}'
            )
            messages.success(request, f'Party "{party.name}" updated successfully.')
            if request.htmx:
                return HttpResponse(status=204, headers={'HX-Redirect': '/parties/'})
            return redirect('parties:party_list')
    else:
        form = PartyForm(instance=party)

    template = 'parties/partials/party_form.html' if request.htmx else 'parties/party_form.html'
    return render(request, template, {'form': form, 'party': party, 'title': f'Edit: {party.name}'})


@login_required
def party_detail(request, pk):
    """View party details with inline ledger, stats, bank accounts, adjustments."""
    party = get_object_or_404(Party, pk=pk)
    
    from django.db.models import Sum, Count, Max
    from django.utils import timezone
    today = timezone.now().date()
    fy_start = today.replace(month=7, day=1) if today.month >= 7 else today.replace(year=today.year - 1, month=7, day=1)

    # Build recent transactions
    transactions = []
    stats = {}
    try:
        from apps.purchases.models import Purchase
        purchases = Purchase.objects.filter(supplier=party, status='final')
        for p in purchases.order_by('-date')[:10]:
            transactions.append({'date': p.date, 'type': 'Purchase', 'ref': p.purchase_number, 'debit': 0, 'credit': p.grand_total, 'url': f'/purchases/{p.pk}/'})
        p_stats = purchases.filter(date__gte=fy_start).aggregate(
            total=Sum('grand_total'), count=Count('pk'), last_date=Max('date'))
        stats['purchases_total'] = p_stats['total'] or 0
        stats['purchases_count'] = p_stats['count'] or 0
        stats['last_purchase'] = p_stats['last_date']

        from apps.sales.models import Sale
        sales = Sale.objects.filter(customer=party, status='final')
        for s in sales.order_by('-date')[:10]:
            transactions.append({'date': s.date, 'type': 'Sale', 'ref': s.invoice_number, 'debit': s.grand_total, 'credit': 0, 'url': f'/sales/{s.pk}/'})
        s_stats = sales.filter(date__gte=fy_start).aggregate(
            total=Sum('grand_total'), count=Count('pk'), last_date=Max('date'))
        stats['sales_total'] = s_stats['total'] or 0
        stats['sales_count'] = s_stats['count'] or 0
        stats['last_sale'] = s_stats['last_date']

        from apps.finance.models import PaymentVoucher, ReceiptVoucher, CrossPartyAdjustment, BankAccount
        payments = PaymentVoucher.objects.filter(party=party, status='final')
        for v in payments.order_by('-date')[:10]:
            transactions.append({'date': v.date, 'type': 'Payment', 'ref': v.voucher_number, 'debit': v.amount, 'credit': 0, 'url': f'/finance/payments/{v.pk}/'})
        pay_stats = payments.filter(date__gte=fy_start).aggregate(total=Sum('amount'), last_date=Max('date'))
        stats['payments_total'] = pay_stats['total'] or 0
        stats['last_payment'] = pay_stats['last_date']

        receipts = ReceiptVoucher.objects.filter(party=party, status='final')
        for v in receipts.order_by('-date')[:10]:
            transactions.append({'date': v.date, 'type': 'Receipt', 'ref': v.voucher_number, 'debit': 0, 'credit': v.amount, 'url': f'/finance/receipts/{v.pk}/'})
        rcv_stats = receipts.filter(date__gte=fy_start).aggregate(total=Sum('amount'), last_date=Max('date'))
        stats['receipts_total'] = rcv_stats['total'] or 0
        stats['last_receipt'] = rcv_stats['last_date']

        # Cross-party adjustments
        adjustments = CrossPartyAdjustment.objects.filter(
            status='final'
        ).filter(
            Q(from_party=party) | Q(to_party=party)
        ).select_related('from_party', 'to_party').order_by('-date')[:5]
        stats['adjustments'] = adjustments

        # Linked bank accounts
        bank_accounts = BankAccount.objects.filter(party=party, is_active=True)
        stats['bank_accounts'] = bank_accounts

    except Exception:
        pass
    transactions.sort(key=lambda x: x["date"], reverse=True)
    
    return render(request, "parties/party_detail.html", {
        "party": party, "transactions": transactions[:15], "stats": stats,
    })


@login_required
@require_POST
def party_delete(request, pk):
    """Deactivate a party (soft delete). POST only."""
    party = get_object_or_404(Party, pk=pk)
    party.is_active = False
    party.save()
    AuditLog.log(
        user=request.user, action='DELETE',
        model_name='Party', object_id=party.pk,
        object_repr=str(party), request=request,
        description=f'Party deactivated: {party.name}'
    )
    messages.success(request, f'Party "{party.name}" has been deactivated.')
    if request.htmx:
        return HttpResponse(status=204, headers={'HX-Trigger': 'partyChanged'})
    return redirect('parties:party_list')


@login_required
def party_search_api(request):
    """API endpoint for party search (used in dropdowns)."""
    q = request.GET.get('q', '')
    party_type = request.GET.get('type', '')
    parties = Party.objects.filter(is_active=True)

    if q:
        parties = parties.filter(
            Q(name__icontains=q) | Q(code__icontains=q)
        )
    if party_type:
        if party_type == 'supplier':
            parties = parties.filter(party_type__in=['supplier', 'both'])
        elif party_type == 'customer':
            parties = parties.filter(party_type__in=['customer', 'both'])
        else:
            parties = parties.filter(party_type=party_type)

    parties = parties[:20]
    data = [{'id': p.pk, 'name': p.name, 'code': p.code,
             'type': p.get_party_type_display(), 'balance': str(p.current_balance)}
            for p in parties]
    return JsonResponse(data, safe=False)


@login_required
def party_bank_info_api(request, pk):
    """Return party's bank details as JSON — used by payment/receipt forms."""
    party = get_object_or_404(Party, pk=pk)
    return JsonResponse({
        'bank_name': party.bank_name or '',
        'account_title': party.account_title or '',
        'account_number': party.account_number or '',
        'iban': party.iban or '',
        'bank_branch': party.bank_branch or '',
        'name': party.name,
        'phone': party.phone_primary or '',
        'city': party.city or '',
    })


@login_required
@require_POST
def party_quick_add_api(request):
    """Quick-add a party from within purchase/sale forms — returns JSON."""
    name = request.POST.get('name', '').strip()
    party_type = request.POST.get('party_type', 'supplier')
    phone = request.POST.get('phone', '').strip()
    city = request.POST.get('city', '').strip()

    if not name:
        return JsonResponse({'error': 'Name is required — نام ضروری ہے'}, status=400)

    code = Party.generate_code(party_type)
    party = Party.objects.create(
        name=name, code=code, party_type=party_type,
        phone_primary=phone, city=city, country='Pakistan',
    )
    AuditLog.log(
        user=request.user, action='CREATE', model_name='Party',
        object_id=party.pk, object_repr=str(party), request=request,
        description=f'Quick-add: {party.name} ({party.get_party_type_display()})',
    )
    return JsonResponse({
        'id': party.pk, 'name': party.name, 'code': party.code,
        'type': party.get_party_type_display(), 'city': party.city,
    })
