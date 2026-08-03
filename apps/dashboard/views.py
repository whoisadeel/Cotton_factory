"""
Dashboard — Summary cards, Charts, Recent Activity, Today's Feed.
"""
import calendar
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, Q
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone

from apps.products.models import Product
from apps.parties.models import Party


@login_required
def dashboard_view(request):
    today = timezone.now().date()

    # ── Imports (all at top to avoid scoping issues) ──
    from apps.purchases.models import Purchase
    from apps.sales.models import Sale
    from apps.finance.models import (
        Expense, PaymentVoucher, ReceiptVoucher, Cheque
    )

    # ── Auto-mark overdue purchases and sales ──
    Purchase.objects.filter(
        status='final', due_date__lt=today,
        payment_status__in=['unpaid', 'partial']
    ).update(payment_status='overdue')
    Sale.objects.filter(
        status='final', due_date__lt=today,
        payment_status__in=['unpaid', 'partial']
    ).update(payment_status='overdue')

    # ── Summary cards ──
    today_purchases = Purchase.objects.filter(
        date=today, status='final'
    ).aggregate(t=Sum('grand_total'))['t'] or 0

    today_sales = Sale.objects.filter(
        date=today, status='final'
    ).aggregate(t=Sum('grand_total'))['t'] or 0

    today_expenses = Expense.objects.filter(
        date=today
    ).aggregate(t=Sum('amount'))['t'] or 0

    today_payments = PaymentVoucher.objects.filter(
        date=today, status='final'
    ).aggregate(t=Sum('amount'))['t'] or 0

    today_receipts = ReceiptVoucher.objects.filter(
        date=today, status='final'
    ).aggregate(t=Sum('amount'))['t'] or 0

    # ── Payables & Receivables ──
    # Balance convention (enforced in all models):
    #   Positive balance = Dr = They owe us (receivable for us)
    #   Negative balance = Cr = We owe them (payable for us)
    #
    # Purchase.finalize:  supplier.current_balance -= amount  → negative (we owe them)
    # Payment.finalize:   party.current_balance += amount     → toward 0 (debt reduced)
    # Sale.finalize:      customer.current_balance += amount  → positive (they owe us)
    # Receipt.finalize:   party.current_balance -= amount     → toward 0 (receivable reduced)
    #
    # Payables = all parties where balance < 0 (we owe them)
    # Receivables = all parties where balance > 0 (they owe us)

    # What WE owe (negative balance = Cr = payable)
    total_payables = abs(
        Party.objects.filter(
            is_active=True, current_balance__lt=0
        ).aggregate(t=Sum('current_balance'))['t'] or Decimal('0')
    )

    # What THEY owe us (positive balance = Dr = receivable)
    total_receivables = (
        Party.objects.filter(
            is_active=True, current_balance__gt=0
        ).aggregate(t=Sum('current_balance'))['t'] or Decimal('0')
    )

    total_products = Product.objects.filter(status='active').count()
    products_with_stock = Product.objects.filter(status='active', current_stock__gt=0)
    stock_value = sum(p.stock_value for p in products_with_stock)

    low_stock_items = Product.objects.filter(
        status='active', minimum_stock__gt=0, current_stock__lt=F('minimum_stock'),
    ).select_related('unit')[:5] if total_products else []

    supplier_count = Party.objects.filter(party_type__in=['supplier', 'both'], is_active=True).count()
    customer_count = Party.objects.filter(party_type__in=['customer', 'both'], is_active=True).count()

    # ── Today's activity feed ──
    todays_activity = []
    for p in Purchase.objects.filter(date=today, status='final').select_related('supplier')[:5]:
        todays_activity.append({
            'type': 'purchase', 'icon': '📥', 'color': '#f97316',
            'text': f'Purchase from {p.supplier.name}',
            'amount': p.grand_total, 'ref': p.purchase_number, 'time': p.created_at,
        })
    for s in Sale.objects.filter(date=today, status='final').select_related('customer')[:5]:
        todays_activity.append({
            'type': 'sale', 'icon': '📤', 'color': '#3b82f6',
            'text': f'Sale to {s.customer.name}',
            'amount': s.grand_total, 'ref': s.invoice_number, 'time': s.created_at,
        })
    for v in PaymentVoucher.objects.filter(date=today, status='final').select_related('party')[:5]:
        todays_activity.append({
            'type': 'payment', 'icon': '💸', 'color': '#dc2626',
            'text': f'Payment to {v.party.name}',
            'amount': v.amount, 'ref': v.voucher_number, 'time': v.created_at,
        })
    for v in ReceiptVoucher.objects.filter(date=today, status='final').select_related('party')[:5]:
        todays_activity.append({
            'type': 'receipt', 'icon': '💰', 'color': '#059669',
            'text': f'Receipt from {v.party.name}',
            'amount': v.amount, 'ref': v.voucher_number, 'time': v.created_at,
        })
    for e in Expense.objects.filter(date=today)[:5]:
        todays_activity.append({
            'type': 'expense', 'icon': '🧾', 'color': '#9333ea',
            'text': f'{e.get_category_display()} — {e.paid_to or ""}',
            'amount': e.amount, 'ref': e.category, 'time': e.created_at,
        })
    todays_activity.sort(key=lambda x: x.get('time') or timezone.now(), reverse=True)

    # ── Chart data: Purchases vs Sales (last 6 months) — optimized ──
    chart_months = []
    chart_purchases = []
    chart_sales = []
    chart_expenses = []

    # Build month ranges
    month_ranges = []
    for i in range(5, -1, -1):
        d = today - timedelta(days=i * 30)
        ms = d.replace(day=1)
        me = d.replace(day=calendar.monthrange(d.year, d.month)[1])
        chart_months.append(calendar.month_abbr[d.month])
        month_ranges.append((ms, me))

    # 3 bulk queries covering all 6 months
    six_months_ago = month_ranges[0][0]
    from django.db.models.functions import TruncMonth
    pur_by_month = dict(
        Purchase.objects.filter(date__gte=six_months_ago, status='final')
        .annotate(m=TruncMonth('date'))
        .values('m').annotate(total=Sum('grand_total'))
        .values_list('m', 'total')
    )
    sal_by_month = dict(
        Sale.objects.filter(date__gte=six_months_ago, status='final')
        .annotate(m=TruncMonth('date'))
        .values('m').annotate(total=Sum('grand_total'))
        .values_list('m', 'total')
    )
    exp_by_month = dict(
        Expense.objects.filter(date__gte=six_months_ago)
        .annotate(m=TruncMonth('date'))
        .values('m').annotate(total=Sum('amount'))
        .values_list('m', 'total')
    )
    for ms, me in month_ranges:
        chart_purchases.append(float(pur_by_month.get(ms, 0) or 0))
        chart_sales.append(float(sal_by_month.get(ms, 0) or 0))
        chart_expenses.append(float(exp_by_month.get(ms, 0) or 0))

    # ── Expense breakdown doughnut (this month) ──
    expense_labels = []
    expense_data = []
    for item in (Expense.objects.filter(date__gte=today.replace(day=1))
                 .values('category')
                 .annotate(total=Sum('amount'))
                 .order_by('-total')[:8]):
        expense_labels.append(item['category'].replace('_', ' ').title())
        expense_data.append(float(item['total']))

    # ── Cash flow line chart (last 30 days) — optimized with 3 bulk queries ──
    cash_flow_dates = []
    cash_flow_in = []
    cash_flow_out = []

    cf_start = today - timedelta(days=29)

    # Bulk query: receipts by date (money in)
    receipt_by_day = dict(
        ReceiptVoucher.objects.filter(date__gte=cf_start, status='final')
        .values('date').annotate(total=Sum('amount'))
        .values_list('date', 'total')
    )
    # Bulk query: payments by date (money out)
    payment_by_day = dict(
        PaymentVoucher.objects.filter(date__gte=cf_start, status='final')
        .values('date').annotate(total=Sum('amount'))
        .values_list('date', 'total')
    )
    # Bulk query: expenses by date
    expense_by_day = dict(
        Expense.objects.filter(date__gte=cf_start)
        .values('date').annotate(total=Sum('amount'))
        .values_list('date', 'total')
    )

    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        cash_flow_dates.append(d.strftime('%d/%m'))
        cash_flow_in.append(float(receipt_by_day.get(d, 0) or 0))
        cash_flow_out.append(
            float(payment_by_day.get(d, 0) or 0) +
            float(expense_by_day.get(d, 0) or 0)
        )

    # ── Notifications ──
    notifications = []

    # Cheques maturing soon
    next_week = today + timedelta(days=7)
    maturing = Cheque.objects.filter(
        status__in=['pending', 'deposited'],
        date_on_cheque__lte=next_week,
        date_on_cheque__gte=today,
    ).select_related('party')
    for ch in maturing[:5]:
        days_left = (ch.date_on_cheque - today).days
        notifications.append({
            'icon': '📝', 'color': '#d97706',
            'text': f'Cheque {ch.cheque_number} (₨{ch.amount:,.0f}) — {ch.party.name}',
            'detail': f'Matures {"today" if days_left == 0 else "tomorrow" if days_left == 1 else f"in {days_left} days"}',
        })

    # Overdue receivables — customers with positive balance (they owe us)
    overdue = Party.objects.filter(
        party_type__in=['customer', 'both'], is_active=True,
        credit_days__gt=0, current_balance__gt=0,
    ).order_by('-current_balance')[:5]
    for p in overdue:
        notifications.append({
            'icon': '⏰', 'color': '#dc2626',
            'text': f'{p.name} owes ₨{p.current_balance:,.0f}',
            'detail': f'Credit limit: {p.credit_days} days',
        })

    # ── Smart Insights ──
    from .insights import generate_insights
    insights = generate_insights()

    # Key product stock for cotton factory
    key_products = Product.objects.filter(
        status='active', category__code__in=['PHUTTI', 'ROOI', 'BINOLA', 'JHAAR']
    ).select_related('category', 'unit')[:6]
    key_stock = []
    for p in key_products:
        conv = float(p.unit.conversion_to_base or 1)
        kg = float(p.current_stock) * conv
        key_stock.append({
            'name': p.name, 'stock': p.current_stock,
            'unit': p.unit.abbreviation, 'kg': round(kg, 0),
            'maund': round(kg / 40, 1), 'source': p.source,
        })

    # Cash in hand from accounting
    from apps.accounting.models import Account
    cash_account = Account.objects.filter(code='1001').first()
    cash_in_hand = cash_account.current_balance if cash_account else Decimal('0')

    # Backup reminder
    import os
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backups')
    last_backup = None
    backup_warning = False
    if os.path.exists(backup_dir):
        backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.sqlite3')], reverse=True)
        if backups:
            last_backup = backups[0]
        else:
            backup_warning = True
    else:
        backup_warning = True

    return render(request, 'dashboard/index.html', {
        'today': today,
        'today_purchases': today_purchases,
        'today_sales': today_sales,
        'today_expenses': today_expenses,
        'today_payments': today_payments,
        'today_receipts': today_receipts,
        'today_net': today_receipts - today_payments,
        'total_payables': total_payables,
        'total_receivables': total_receivables,
        'stock_value': stock_value,
        'total_products': total_products,
        'supplier_count': supplier_count,
        'customer_count': customer_count,
        'low_stock_items': low_stock_items,
        'todays_activity': todays_activity,
        'insights': insights,
        'chart_months': json.dumps(chart_months),
        'chart_purchases': json.dumps(chart_purchases),
        'chart_sales': json.dumps(chart_sales),
        'chart_expenses': json.dumps(chart_expenses),
        'expense_labels': json.dumps(expense_labels),
        'expense_data': json.dumps(expense_data),
        'cash_flow_dates': json.dumps(cash_flow_dates),
        'cash_flow_in': json.dumps(cash_flow_in),
        'cash_flow_out': json.dumps(cash_flow_out),
        'notifications': notifications,
        'key_stock': key_stock,
        'cash_in_hand': cash_in_hand,
        'backup_warning': backup_warning,
        'last_backup': last_backup,
    })


@login_required
def global_search(request):
    """Global search API — search across parties, products, purchases, sales."""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    results = []

    # Search parties
    for p in Party.objects.filter(
        Q(name__icontains=q) | Q(code__icontains=q) | Q(phone_primary__icontains=q),
        is_active=True
    )[:5]:
        results.append({
            'type': 'party', 'icon': '👤', 'title': p.name,
            'subtitle': f'{p.get_party_type_display()} — {p.code}',
            'url': f'/parties/{p.pk}/',
        })

    # Search products
    for p in Product.objects.filter(
        Q(name__icontains=q) | Q(code__icontains=q), status='active'
    )[:5]:
        results.append({
            'type': 'product', 'icon': '📦', 'title': p.name,
            'subtitle': f'{p.code} — Stock: {p.current_stock}',
            'url': f'/products/{p.pk}/edit/',
        })

    # Search purchases
    try:
        from apps.purchases.models import Purchase
        for p in Purchase.objects.filter(
            Q(purchase_number__icontains=q) | Q(supplier__name__icontains=q)
        ).select_related('supplier')[:5]:
            results.append({
                'type': 'purchase', 'icon': '🛒', 'title': p.purchase_number,
                'subtitle': f'{p.supplier.name} — ₨{p.grand_total:,.0f}',
                'url': f'/purchases/{p.pk}/edit/',
            })
    except Exception:
        pass

    # Search sales
    try:
        from apps.sales.models import Sale
        for s in Sale.objects.filter(
            Q(invoice_number__icontains=q) | Q(customer__name__icontains=q)
        ).select_related('customer')[:5]:
            results.append({
                'type': 'sale', 'icon': '📋', 'title': s.invoice_number,
                'subtitle': f'{s.customer.name} — ₨{s.grand_total:,.0f}',
                'url': f'/sales/{s.pk}/edit/',
            })
    except Exception:
        pass

    return JsonResponse({'results': results[:15]})
