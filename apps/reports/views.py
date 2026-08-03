"""
Reports Module — Purchase, Sales, Financial, Stock, Ginning reports.
All reports support date range filtering and export.
"""
import json as _json
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, Count
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.http import HttpResponse
import csv

from apps.purchases.models import Purchase, PurchaseItem
from apps.sales.models import Sale, SaleItem
from apps.finance.models import PaymentVoucher, ReceiptVoucher, Expense
from apps.parties.models import Party
from apps.products.models import Product, Category
from apps.inventory.models import StockMovement


def _dates(request):
    """Parse date range from request. Returns (start, end, context_dict).
    context_dict has filter_from/filter_to for the date_filter template."""
    today = timezone.now().date()
    start = request.GET.get('from')
    end = request.GET.get('to')
    try:
        start = date.fromisoformat(start) if start else today.replace(day=1)
    except (ValueError, TypeError):
        start = today.replace(day=1)
    try:
        end = date.fromisoformat(end) if end else today
    except (ValueError, TypeError):
        end = today
    return start, end, {'filter_from': start, 'filter_to': end}


@login_required
def reports_index(request):
    return render(request, 'reports/index.html')


# ═══════════════════════════════════════════════════════════════
# PURCHASE REPORTS
# ═══════════════════════════════════════════════════════════════

@login_required
def purchase_register(request):
    start, end, ctx = _dates(request)
    purchases = Purchase.objects.filter(
        date__range=[start, end], status='final'
    ).select_related('supplier', 'broker').order_by('date')

    # Extra filters (like cost calculator)
    supplier_id = request.GET.get('supplier')
    if supplier_id:
        purchases = purchases.filter(supplier_id=supplier_id)
    category_id = request.GET.get('category')
    if category_id:
        purchases = purchases.filter(items__product__category_id=category_id).distinct()
    product_id = request.GET.get('product')
    if product_id:
        purchases = purchases.filter(items__product_id=product_id).distinct()

    total = purchases.aggregate(t=Sum('grand_total'))['t'] or 0
    count = purchases.count()
    purchases_json = []
    for p in purchases:
        items_desc = ', '.join(
            f"{i.product.name} {i.quantity}{i.unit.abbreviation}"
            for i in p.items.select_related('product','unit').all()[:3]
        )
        purchases_json.append({
            'id': p.pk, 'date': p.date.strftime('%d/%m/%Y'), 'number': p.purchase_number,
            'supplier': p.supplier.name, 'items': items_desc or '—',
            'total': float(p.grand_total),
            'paid': float(p.amount_paid), 'balance': float(p.balance_due),
        })
    from apps.products.models import Category
    ctx.update({
        'purchases': purchases, 'total': total, 'count': count,
        'purchases_json': _json.dumps(purchases_json),
        'suppliers': Party.objects.filter(party_type__in=['supplier','both'], is_active=True).order_by('name'),
        'categories': Category.objects.filter(is_active=True).order_by('name'),
        'products_list': Product.objects.filter(status='active').order_by('name'),
        'selected_supplier': supplier_id or '',
        'selected_category': category_id or '',
        'selected_product': product_id or '',
    })
    return render(request, 'reports/purchase_register.html', ctx)


@login_required
def purchase_by_supplier(request):
    start, end, ctx = _dates(request)
    data = Purchase.objects.filter(
        date__range=[start, end], status='final'
    ).values('supplier__name', 'supplier__code').annotate(
        total=Sum('grand_total'), count=Count('id')
    ).order_by('-total')
    grand = sum(d['total'] for d in data)
    ctx.update({'data': data, 'grand': grand})
    return render(request, 'reports/purchase_by_supplier.html', ctx)


@login_required
def purchase_by_product(request):
    start, end, ctx = _dates(request)
    data = PurchaseItem.objects.filter(
        purchase__date__range=[start, end], purchase__status='final'
    ).values('product__name', 'product__code').annotate(
        total_qty=Sum('quantity'), total_amount=Sum('net_amount')
    ).order_by('-total_amount')
    ctx.update({'data': data})
    return render(request, 'reports/purchase_by_product.html', ctx)


# ═══════════════════════════════════════════════════════════════
# SALES REPORTS
# ═══════════════════════════════════════════════════════════════

@login_required
def sales_register(request):
    start, end, ctx = _dates(request)
    sales = Sale.objects.filter(
        date__range=[start, end], status='final'
    ).select_related('customer', 'broker').order_by('date')

    customer_id = request.GET.get('customer')
    if customer_id:
        sales = sales.filter(customer_id=customer_id)
    category_id = request.GET.get('category')
    if category_id:
        sales = sales.filter(items__product__category_id=category_id).distinct()
    product_id = request.GET.get('product')
    if product_id:
        sales = sales.filter(items__product_id=product_id).distinct()

    total = sales.aggregate(t=Sum('grand_total'))['t'] or 0
    count = sales.count()
    sales_json = []
    for s in sales:
        items_desc = ', '.join(
            f"{i.product.name} {i.quantity}{i.unit.abbreviation}"
            for i in s.items.select_related('product','unit').all()[:3]
        )
        sales_json.append({
            'id': s.pk, 'date': s.date.strftime('%d/%m/%Y'), 'number': s.invoice_number,
            'customer': s.customer.name, 'items': items_desc or '—',
            'total': float(s.grand_total),
            'received': float(s.amount_received), 'balance': float(s.balance_due),
        })
    from apps.products.models import Category
    ctx.update({
        'sales': sales, 'total': total, 'count': count,
        'sales_json': _json.dumps(sales_json),
        'customers': Party.objects.filter(party_type__in=['customer','both'], is_active=True).order_by('name'),
        'categories': Category.objects.filter(is_active=True).order_by('name'),
        'products_list': Product.objects.filter(status='active').order_by('name'),
        'selected_customer': customer_id or '',
        'selected_category': category_id or '',
        'selected_product': product_id or '',
    })
    return render(request, 'reports/sales_register.html', ctx)


@login_required
def sales_by_customer(request):
    start, end, ctx = _dates(request)
    data = Sale.objects.filter(
        date__range=[start, end], status='final'
    ).values('customer__name', 'customer__code').annotate(
        total=Sum('grand_total'), count=Count('id')
    ).order_by('-total')
    grand = sum(d['total'] for d in data)
    ctx.update({'data': data, 'grand': grand})
    return render(request, 'reports/sales_by_customer.html', ctx)


@login_required
def sales_by_product(request):
    start, end, ctx = _dates(request)
    data = SaleItem.objects.filter(
        sale__date__range=[start, end], sale__status='final'
    ).values('product__name', 'product__code').annotate(
        total_qty=Sum('quantity'), total_amount=Sum('net_amount')
    ).order_by('-total_amount')
    ctx.update({'data': data})
    return render(request, 'reports/sales_by_product.html', ctx)


# ═══════════════════════════════════════════════════════════════
# FINANCIAL REPORTS
# ═══════════════════════════════════════════════════════════════

@login_required
def day_book(request):
    """All transactions of a day."""
    day_str = request.GET.get('date')
    try:
        day = date.fromisoformat(day_str) if day_str else timezone.now().date()
    except (ValueError, TypeError):
        day = timezone.now().date()

    purchases = Purchase.objects.filter(date=day, status='final').select_related('supplier')
    sales = Sale.objects.filter(date=day, status='final').select_related('customer')
    payments = PaymentVoucher.objects.filter(date=day, status='final').select_related('party')
    receipts = ReceiptVoucher.objects.filter(date=day, status='final').select_related('party')
    expenses = Expense.objects.filter(date=day)

    from django.db.models import Sum
    total_purchases = purchases.aggregate(t=Sum('grand_total'))['t'] or 0
    total_sales = sales.aggregate(t=Sum('grand_total'))['t'] or 0
    total_payments = payments.aggregate(t=Sum('amount'))['t'] or 0
    total_receipts = receipts.aggregate(t=Sum('amount'))['t'] or 0
    total_expenses = expenses.aggregate(t=Sum('amount'))['t'] or 0

    return render(request, 'reports/day_book.html', {
        'day': day, 'purchases': purchases, 'sales': sales,
        'payments': payments, 'receipts': receipts, 'expenses': expenses,
        'total_purchases': total_purchases, 'total_sales': total_sales,
        'total_payments': total_payments, 'total_receipts': total_receipts,
        'total_expenses': total_expenses,
        'filter_from': day, 'filter_to': day,
    })


@login_required
def cash_book(request):
    start, end, ctx = _dates(request)
    # Summaries
    payments_cash = PaymentVoucher.objects.filter(
        date__range=[start, end], status='final', payment_method='cash'
    ).aggregate(t=Sum('amount'))['t'] or 0
    receipts_cash = ReceiptVoucher.objects.filter(
        date__range=[start, end], status='final', payment_method='cash'
    ).aggregate(t=Sum('amount'))['t'] or 0
    expenses_cash = Expense.objects.filter(
        date__range=[start, end], payment_method='cash'
    ).aggregate(t=Sum('amount'))['t'] or 0

    # Transaction details
    cash_payments = PaymentVoucher.objects.filter(
        date__range=[start, end], status='final', payment_method='cash'
    ).select_related('party').order_by('date', 'created_at')
    cash_receipts = ReceiptVoucher.objects.filter(
        date__range=[start, end], status='final', payment_method='cash'
    ).select_related('party').order_by('date', 'created_at')
    cash_expenses = Expense.objects.filter(
        date__range=[start, end], payment_method='cash'
    ).order_by('date', 'created_at')

    ctx.update({
        'receipts_cash': receipts_cash,
        'payments_cash': payments_cash,
        'expenses_cash': expenses_cash,
        'net_cash': receipts_cash - payments_cash - expenses_cash,
        'cash_payments': cash_payments,
        'cash_receipts': cash_receipts,
        'cash_expenses': cash_expenses,
    })
    return render(request, 'reports/cash_book.html', ctx)


@login_required
def bank_book(request):
    start, end, ctx = _dates(request)
    from apps.finance.models import BankAccount
    bank_accounts = BankAccount.objects.filter(owner_type='own', is_active=True)
    bank_payments = PaymentVoucher.objects.filter(
        date__range=[start, end], status='final', payment_method__in=['bank', 'cheque', 'online']
    ).aggregate(t=Sum('amount'))['t'] or 0
    bank_receipts = ReceiptVoucher.objects.filter(
        date__range=[start, end], status='final', payment_method__in=['bank', 'cheque', 'online']
    ).aggregate(t=Sum('amount'))['t'] or 0

    # Transaction details
    bank_pay_list = PaymentVoucher.objects.filter(
        date__range=[start, end], status='final', payment_method__in=['bank', 'cheque', 'online']
    ).select_related('party', 'bank_account').order_by('date', 'created_at')
    bank_rcv_list = ReceiptVoucher.objects.filter(
        date__range=[start, end], status='final', payment_method__in=['bank', 'cheque', 'online']
    ).select_related('party', 'bank_account').order_by('date', 'created_at')

    ctx.update({
        'bank_accounts': bank_accounts, 'bank_payments': bank_payments,
        'bank_receipts': bank_receipts,
        'bank_pay_list': bank_pay_list, 'bank_rcv_list': bank_rcv_list,
        'net_bank': bank_receipts - bank_payments,
    })
    return render(request, 'reports/bank_book.html', ctx)


@login_required
def outstanding_payables(request):
    parties = Party.objects.filter(
        current_balance__lt=0, is_active=True
    ).order_by('current_balance')
    total = parties.aggregate(t=Sum('current_balance'))['t'] or 0
    return render(request, 'reports/outstanding_payables.html', {
        'parties': parties, 'total': abs(total)
    })


@login_required
def outstanding_receivables(request):
    parties = Party.objects.filter(
        current_balance__gt=0, is_active=True
    ).order_by('-current_balance')
    total = parties.aggregate(t=Sum('current_balance'))['t'] or 0
    return render(request, 'reports/outstanding_receivables.html', {
        'parties': parties, 'total': total
    })


@login_required
def profit_loss(request):
    start, end, ctx = _dates(request)
    sales_total = Sale.objects.filter(date__range=[start, end], status='final').aggregate(t=Sum('grand_total'))['t'] or 0
    purchase_total = Purchase.objects.filter(date__range=[start, end], status='final').aggregate(t=Sum('grand_total'))['t'] or 0
    expenses_total = Expense.objects.filter(date__range=[start, end]).aggregate(t=Sum('amount'))['t'] or 0
    gross_profit = sales_total - purchase_total
    net_profit = gross_profit - expenses_total

    expense_breakdown = Expense.objects.filter(
        date__range=[start, end]
    ).values('category').annotate(total=Sum('amount')).order_by('-total')

    ctx.update({
        'sales_total': sales_total, 'purchase_total': purchase_total,
        'expenses_total': expenses_total, 'gross_profit': gross_profit,
        'net_profit': net_profit, 'expense_breakdown': expense_breakdown,
    })
    return render(request, 'reports/profit_loss.html', ctx)


@login_required
def trial_balance(request):
    from apps.accounting.models import Account
    accounts = Account.objects.filter(current_balance__gt=0) | Account.objects.filter(current_balance__lt=0)
    accounts = accounts.select_related('group').order_by('code')
    total_debit = sum(a.current_balance for a in accounts if a.current_balance > 0)
    total_credit = sum(abs(a.current_balance) for a in accounts if a.current_balance < 0)
    return render(request, 'reports/trial_balance.html', {
        'accounts': accounts, 'total_debit': total_debit, 'total_credit': total_credit
    })


@login_required
def stock_report(request):
    products = Product.objects.filter(status='active').select_related('category', 'unit')

    stock_data = []
    total_value = Decimal('0')
    for p in products:
        conv = float(p.unit.conversion_to_base or 1)
        stock_kg = float(p.current_stock) * conv
        stock_maund = stock_kg / 40.0
        value = p.stock_value
        if p.current_stock > 0:
            total_value += value
        stock_data.append({
            'product': p, 'current_stock': p.current_stock, 'unit': p.unit,
            'stock_kg': round(stock_kg, 2), 'stock_maund': round(stock_maund, 2),
            'value': value, 'is_low': p.is_low_stock,
            'purchase_price': p.default_purchase_price,
        })

    category_id = request.GET.get('category')
    if category_id:
        stock_data = [s for s in stock_data if str(s['product'].category_id) == category_id]

    show_zero = request.GET.get('show_zero', '')
    if not show_zero:
        stock_data = [s for s in stock_data if s['current_stock'] > 0 or s['is_low']]

    categories = Category.objects.filter(is_active=True)
    return render(request, 'reports/stock_report.html', {
        'stock_data': stock_data, 'total_value': total_value,
        'categories': categories, 'selected_category': category_id,
        'show_zero': show_zero,
    })


@login_required
def party_ledger(request, pk=None):
    party = None
    entries = []
    start, end, ctx = _dates(request)

    if pk:
        party = get_object_or_404(Party, pk=pk)
        ledger = []
        for p in Purchase.objects.filter(supplier=party, date__range=[start, end], status='final'):
            ledger.append({'date': p.date, 'type': 'Purchase', 'ref': p.purchase_number,
                           'debit': 0, 'credit': p.grand_total, 'desc': f'Purchase from {party.name}'})
        for s in Sale.objects.filter(customer=party, date__range=[start, end], status='final'):
            ledger.append({'date': s.date, 'type': 'Sale', 'ref': s.invoice_number,
                           'debit': s.grand_total, 'credit': 0, 'desc': f'Sale to {party.name}'})
        for v in PaymentVoucher.objects.filter(party=party, date__range=[start, end], status='final'):
            ledger.append({'date': v.date, 'type': 'Payment', 'ref': v.voucher_number,
                           'debit': v.amount, 'credit': 0, 'desc': v.narration or 'Payment'})
        for v in ReceiptVoucher.objects.filter(party=party, date__range=[start, end], status='final'):
            ledger.append({'date': v.date, 'type': 'Receipt', 'ref': v.voucher_number,
                           'debit': 0, 'credit': v.amount, 'desc': v.narration or 'Receipt'})

        # Expenses paid to this party
        for e in Expense.objects.filter(paid_to__iexact=party.name, date__range=[start, end]):
            ledger.append({'date': e.date, 'type': 'Expense', 'ref': e.get_category_display(),
                           'debit': e.amount, 'credit': 0, 'desc': e.description or e.get_category_display()})

        ledger.sort(key=lambda x: x['date'])

        # Add running balance
        ob = float(party.opening_balance or 0)
        if party.opening_balance_type == 'credit':
            ob = -ob
        balance = ob
        entries = [{'date': '—', 'type': 'Opening', 'ref': '', 'desc': 'Opening Balance',
                    'debit': ob if ob > 0 else 0, 'credit': abs(ob) if ob < 0 else 0, 'balance': balance}]
        for row in ledger:
            balance += float(row['debit']) - float(row['credit'])
            row['balance'] = balance
            entries.append(row)

        # Summary totals for the period
        total_debit = sum(float(e.get('debit', 0) or 0) for e in entries if e['type'] != 'Opening')
        total_credit = sum(float(e.get('credit', 0) or 0) for e in entries if e['type'] != 'Opening')
        total_purchases = sum(float(e.get('credit', 0) or 0) for e in entries if e['type'] == 'Purchase')
        total_sales = sum(float(e.get('debit', 0) or 0) for e in entries if e['type'] == 'Sale')
        total_paid = sum(float(e.get('debit', 0) or 0) for e in entries if e['type'] == 'Payment')
        total_received = sum(float(e.get('credit', 0) or 0) for e in entries if e['type'] == 'Receipt')

    all_parties = Party.objects.filter(is_active=True).order_by('name')
    ctx.update({
        'party': party, 'entries': entries, 'all_parties': all_parties,
        'total_debit': total_debit if pk else 0,
        'total_credit': total_credit if pk else 0,
        'total_purchases': total_purchases if pk else 0,
        'total_sales': total_sales if pk else 0,
        'total_paid': total_paid if pk else 0,
        'total_received': total_received if pk else 0,
    })
    return render(request, 'reports/party_ledger.html', ctx)


@login_required
def broker_commission_report(request):
    start, end, ctx = _dates(request)
    # Broker-linked commissions
    purchases = Purchase.objects.filter(
        date__range=[start, end], status='final', broker__isnull=False
    ).values('broker__name', 'broker__code').annotate(
        total=Sum('commission_amount'), count=Count('id')
    ).order_by('-total')
    sales = Sale.objects.filter(
        date__range=[start, end], status='final', broker__isnull=False
    ).values('broker__name', 'broker__code').annotate(
        total=Sum('commission_amount'), count=Count('id')
    ).order_by('-total')
    # ALL commissions (including without broker)
    total_purchase_commission = Purchase.objects.filter(
        date__range=[start, end], status='final', commission_amount__gt=0
    ).aggregate(t=Sum('commission_amount'))['t'] or 0
    total_sale_commission = Sale.objects.filter(
        date__range=[start, end], status='final', commission_amount__gt=0
    ).aggregate(t=Sum('commission_amount'))['t'] or 0
    # Commission entries without broker
    no_broker_purchases = Purchase.objects.filter(
        date__range=[start, end], status='final', commission_amount__gt=0, broker__isnull=True
    ).select_related('supplier').order_by('-date')
    no_broker_sales = Sale.objects.filter(
        date__range=[start, end], status='final', commission_amount__gt=0, broker__isnull=True
    ).select_related('customer').order_by('-date')

    ctx.update({
        'purchase_commissions': purchases, 'sale_commissions': sales,
        'total_purchase_commission': total_purchase_commission,
        'total_sale_commission': total_sale_commission,
        'no_broker_purchases': no_broker_purchases,
        'no_broker_sales': no_broker_sales,
    })
    return render(request, 'reports/broker_commission.html', ctx)


@login_required
def ginning_report(request):
    start, end, ctx = _dates(request)
    from apps.ginning.models import GinningLot
    lots = GinningLot.objects.filter(date__range=[start, end]).order_by('date')
    total_input = lots.aggregate(t=Sum('input_quantity'))['t'] or 0
    total_lint = lots.aggregate(t=Sum('lint_quantity'))['t'] or 0
    total_seed = lots.aggregate(t=Sum('seed_quantity'))['t'] or 0
    avg_got = (total_lint / total_input * 100) if total_input > 0 else 0
    ctx.update({
        'lots': lots, 'total_input': total_input, 'total_lint': total_lint,
        'total_seed': total_seed, 'avg_got': avg_got,
    })
    return render(request, 'reports/ginning_report.html', ctx)


@login_required
def monthly_comparison(request):
    import calendar
    from datetime import date as dt_date
    year = int(request.GET.get('year', timezone.now().year))
    data = []
    for month in range(1, 13):
        from_d = dt_date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        to_d = dt_date(year, month, last_day)
        p_total = Purchase.objects.filter(date__range=[from_d, to_d], status='final').aggregate(t=Sum('grand_total'))['t'] or 0
        s_total = Sale.objects.filter(date__range=[from_d, to_d], status='final').aggregate(t=Sum('grand_total'))['t'] or 0
        e_total = Expense.objects.filter(date__range=[from_d, to_d]).aggregate(t=Sum('amount'))['t'] or 0
        data.append({
            'month': calendar.month_abbr[month], 'purchases': p_total,
            'sales': s_total, 'expenses': e_total, 'profit': s_total - p_total - e_total
        })
    return render(request, 'reports/monthly_comparison.html', {'data': data, 'year': year})


# ═══════════════════════════════════════════════════════════════
# AGING & OVERDUE REPORTS
# ═══════════════════════════════════════════════════════════════

@login_required
def aging_report(request):
    from django.utils import timezone as tz
    today = tz.now().date()

    def _build_aging(parties):
        buckets = {'current': [], '30': [], '60': [], '90': [], 'over90': []}
        for p in parties:
            bal = abs(p.current_balance)
            dates = []
            lp = Purchase.objects.filter(supplier=p, status='final').order_by('-date').first()
            ls = Sale.objects.filter(customer=p, status='final').order_by('-date').first()
            lpv = PaymentVoucher.objects.filter(party=p, status='final').order_by('-date').first()
            lrv = ReceiptVoucher.objects.filter(party=p, status='final').order_by('-date').first()
            dates = [x.date for x in [lp, ls, lpv, lrv] if x]
            last_date = max(dates) if dates else today
            age = (today - last_date).days
            entry = {'party': p, 'amount': bal, 'age_days': age, 'last_date': last_date}
            if age <= 30: buckets['current'].append(entry)
            elif age <= 60: buckets['30'].append(entry)
            elif age <= 90: buckets['60'].append(entry)
            else: buckets['over90'].append(entry)
        return buckets

    receivable_parties = Party.objects.filter(current_balance__gt=0, is_active=True).order_by('-current_balance')
    receivable_aging = _build_aging(receivable_parties)
    total_receivable = sum(p.current_balance for p in receivable_parties)
    payable_parties = Party.objects.filter(current_balance__lt=0, is_active=True).order_by('current_balance')
    payable_aging = _build_aging(payable_parties)
    total_payable = sum(abs(p.current_balance) for p in payable_parties)

    return render(request, 'reports/aging_report.html', {
        'receivable_aging': receivable_aging, 'payable_aging': payable_aging,
        'total_receivable': total_receivable, 'total_payable': total_payable, 'today': today,
    })


@login_required
def overdue_invoices(request):
    from django.utils import timezone as tz
    today = tz.now().date()

    overdue_purchases = Purchase.objects.filter(
        status='final', due_date__lt=today, payment_status__in=['unpaid', 'partial', 'overdue']
    ).select_related('supplier').order_by('due_date')
    overdue_sales = Sale.objects.filter(
        status='final', due_date__lt=today, payment_status__in=['unpaid', 'partial', 'overdue']
    ).select_related('customer').order_by('due_date')

    for p in overdue_purchases:
        if p.payment_status != 'overdue':
            p.payment_status = 'overdue'
            p.save(update_fields=['payment_status'])
    for s in overdue_sales:
        if s.payment_status != 'overdue':
            s.payment_status = 'overdue'
            s.save(update_fields=['payment_status'])

    return render(request, 'reports/overdue_invoices.html', {
        'overdue_purchases': overdue_purchases, 'overdue_sales': overdue_sales, 'today': today,
    })


@login_required
def accounts_overview(request):
    """Complete financial overview — all parties, all balances, all transactions."""
    start, end, ctx = _dates(request)
    from django.db.models import Subquery, OuterRef, Value
    from django.db.models.functions import Coalesce

    # Use aggregated subqueries instead of per-party loop (fast even with 1000+ parties)
    purchase_totals = dict(Purchase.objects.filter(
        status='final', date__range=[start, end]
    ).values('supplier_id').annotate(t=Sum('grand_total')).values_list('supplier_id', 't'))

    sale_totals = dict(Sale.objects.filter(
        status='final', date__range=[start, end]
    ).values('customer_id').annotate(t=Sum('grand_total')).values_list('customer_id', 't'))

    payment_totals = dict(PaymentVoucher.objects.filter(
        status='final', date__range=[start, end]
    ).values('party_id').annotate(t=Sum('amount')).values_list('party_id', 't'))

    receipt_totals = dict(ReceiptVoucher.objects.filter(
        status='final', date__range=[start, end]
    ).values('party_id').annotate(t=Sum('amount')).values_list('party_id', 't'))

    all_parties = Party.objects.filter(is_active=True).order_by('name')
    parties_data = []
    for p in all_parties:
        total_purchases = purchase_totals.get(p.pk, 0) or 0
        total_sales = sale_totals.get(p.pk, 0) or 0
        total_paid = payment_totals.get(p.pk, 0) or 0
        total_received = receipt_totals.get(p.pk, 0) or 0

        if total_purchases or total_sales or total_paid or total_received or p.current_balance != 0:
            parties_data.append({
                'party': p,
                'purchases': total_purchases,
                'sales': total_sales,
                'paid': total_paid,
                'received': total_received,
                'balance': p.current_balance,
            })

    # Totals
    total_receivable = sum(d['balance'] for d in parties_data if d['balance'] > 0)
    total_payable = abs(sum(d['balance'] for d in parties_data if d['balance'] < 0))
    total_purchases = sum(d['purchases'] for d in parties_data)
    total_sales = sum(d['sales'] for d in parties_data)
    total_paid_out = sum(d['paid'] for d in parties_data)
    total_received_in = sum(d['received'] for d in parties_data)

    # Recent payments
    recent_payments = PaymentVoucher.objects.filter(
        status='final', date__range=[start, end]
    ).select_related('party').order_by('-date', '-created_at')[:20]

    # Recent receipts
    recent_receipts = ReceiptVoucher.objects.filter(
        status='final', date__range=[start, end]
    ).select_related('party').order_by('-date', '-created_at')[:20]

    ctx.update({
        'parties_data': parties_data,
        'total_receivable': total_receivable,
        'total_payable': total_payable,
        'total_purchases': total_purchases,
        'total_sales': total_sales,
        'total_paid_out': total_paid_out,
        'total_received_in': total_received_in,
        'recent_payments': recent_payments,
        'recent_receipts': recent_receipts,
    })
    return render(request, 'reports/accounts_overview.html', ctx)


@login_required
def expense_analysis(request):
    start, end, ctx = _dates(request)
    categories = Expense.objects.filter(
        date__range=[start, end]
    ).values('category').annotate(total=Sum('amount'), count=Count('id')).order_by('-total')
    total_expenses = sum(c['total'] for c in categories)
    for c in categories:
        c['label'] = c['category'].replace('_', ' ').title()
        c['pct'] = (c['total'] / total_expenses * 100) if total_expenses > 0 else 0
    daily = Expense.objects.filter(
        date__range=[start, end]
    ).values('date').annotate(total=Sum('amount')).order_by('date')
    ctx.update({'categories': categories, 'daily': daily, 'total_expenses': total_expenses})
    return render(request, 'reports/expense_analysis.html', ctx)


@login_required
def stock_reconciliation(request):
    products = Product.objects.filter(status='active').select_related('category', 'unit')
    discrepancies = []
    for p in products:
        movements = StockMovement.objects.filter(product=p)
        total_in = movements.filter(
            movement_type__in=['purchase', 'sale_return', 'adjustment_in', 'processing_out']
        ).aggregate(t=Sum('quantity'))['t'] or Decimal('0')
        total_out = movements.filter(
            movement_type__in=['sale', 'purchase_return', 'adjustment_out', 'processing_in']
        ).aggregate(t=Sum('quantity'))['t'] or Decimal('0')
        expected = total_in - total_out
        drift = p.current_stock - expected
        discrepancies.append({
            'product': p, 'current_stock': p.current_stock, 'expected_stock': expected,
            'total_in': total_in, 'total_out': total_out, 'drift': drift,
            'has_drift': drift != 0,
        })
    has_issues = any(d['has_drift'] for d in discrepancies)
    return render(request, 'reports/stock_reconciliation.html', {
        'discrepancies': discrepancies, 'has_issues': has_issues,
    })


# ═══════════════════════════════════════════════════════════════
# CSV EXPORT
# ═══════════════════════════════════════════════════════════════

@login_required
def export_csv(request, report_type):
    start, end, _ = _dates(request)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_{start}_{end}.csv"'
    writer = csv.writer(response)

    if report_type == 'purchases':
        writer.writerow(['Date', 'Purchase #', 'Supplier', 'Total', 'Paid', 'Balance'])
        for p in Purchase.objects.filter(date__range=[start, end], status='final').select_related('supplier'):
            writer.writerow([p.date, p.purchase_number, p.supplier.name, p.grand_total, p.amount_paid, p.balance_due])
    elif report_type == 'sales':
        writer.writerow(['Date', 'Invoice', 'Customer', 'Total', 'Received', 'Balance'])
        for s in Sale.objects.filter(date__range=[start, end], status='final').select_related('customer'):
            writer.writerow([s.date, s.invoice_number, s.customer.name, s.grand_total, s.amount_received, s.balance_due])
    elif report_type == 'stock':
        writer.writerow(['Code', 'Product', 'Category', 'Stock', 'Unit', 'KG', 'Maund', 'Value'])
        for p in Product.objects.filter(status='active').select_related('category', 'unit'):
            conv = float(p.unit.conversion_to_base or 1)
            kg = float(p.current_stock) * conv
            writer.writerow([p.code, p.name, p.category.name, p.current_stock, p.unit.abbreviation,
                              round(kg, 2), round(kg / 40, 2), p.stock_value])
    return response
