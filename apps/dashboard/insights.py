"""
Smart Business Insights Engine — Analyzes real data to surface
useful patterns, warnings, and recommendations.
"""
from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum, Avg, Count, F, Q
from django.utils import timezone


def generate_insights():
    """Analyze all business data and return a list of insight cards."""
    from apps.purchases.models import Purchase
    from apps.sales.models import Sale
    from apps.finance.models import PaymentVoucher, ReceiptVoucher, Expense, Cheque
    from apps.parties.models import Party
    from apps.products.models import Product

    today = timezone.now().date()
    month_start = today.replace(day=1)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    last_month_end = month_start - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    insights = []

    # ── 1. PROFIT/LOSS TREND ──
    try:
        this_month_sales = Sale.objects.filter(
            date__gte=month_start, status='final'
        ).aggregate(t=Sum('grand_total'))['t'] or Decimal('0')
        this_month_purchases = Purchase.objects.filter(
            date__gte=month_start, status='final'
        ).aggregate(t=Sum('grand_total'))['t'] or Decimal('0')
        this_month_expenses = Expense.objects.filter(
            date__gte=month_start
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        gross_profit = this_month_sales - this_month_purchases
        net_profit = gross_profit - this_month_expenses

        if this_month_sales > 0 or this_month_purchases > 0:
            if net_profit > 0:
                margin = (net_profit / this_month_sales * 100) if this_month_sales else 0
                insights.append({
                    'type': 'success',
                    'icon': '📈',
                    'title': 'Profitable This Month — اس مہینے منافع',
                    'body': f'Net profit: ₨{net_profit:,.0f} (margin: {margin:.1f}%)',
                    'body_ur': f'خالص منافع: ₨{net_profit:,.0f}',
                    'detail': f'Sales ₨{this_month_sales:,.0f} − Purchases ₨{this_month_purchases:,.0f} − Expenses ₨{this_month_expenses:,.0f}',
                })
            elif net_profit < 0:
                insights.append({
                    'type': 'danger',
                    'icon': '📉',
                    'title': 'Loss This Month — اس مہینے نقصان',
                    'body': f'Net loss: ₨{abs(net_profit):,.0f}',
                    'body_ur': f'خالص نقصان: ₨{abs(net_profit):,.0f}',
                    'detail': f'Sales ₨{this_month_sales:,.0f} − Purchases ₨{this_month_purchases:,.0f} − Expenses ₨{this_month_expenses:,.0f}',
                })

        # Compare with last month
        last_month_sales = Sale.objects.filter(
            date__range=[last_month_start, last_month_end], status='final'
        ).aggregate(t=Sum('grand_total'))['t'] or Decimal('0')
        if last_month_sales > 0 and this_month_sales > 0:
            change = ((this_month_sales - last_month_sales) / last_month_sales) * 100
            if abs(change) > 10:
                direction = 'up' if change > 0 else 'down'
                insights.append({
                    'type': 'info' if change > 0 else 'warning',
                    'icon': '📊',
                    'title': f'Sales {direction} {abs(change):.0f}% vs last month',
                    'body': f'This month: ₨{this_month_sales:,.0f} vs Last: ₨{last_month_sales:,.0f}',
                    'body_ur': f'اس مہینے: ₨{this_month_sales:,.0f} بمقابلہ پچھلے مہینے: ₨{last_month_sales:,.0f}',
                })
    except Exception:
        pass

    # ── 2. OVERDUE RECEIVABLES ──
    # Convention: positive balance = Dr = they owe us
    try:
        overdue_customers = Party.objects.filter(
            party_type__in=['customer', 'both'], is_active=True,
            current_balance__gt=0,
        )
        total_receivable = overdue_customers.aggregate(
            t=Sum('current_balance'))['t'] or Decimal('0')
        overdue_count = overdue_customers.count()

        if total_receivable > 0:
            insights.append({
                'type': 'warning',
                'icon': '💰',
                'title': f'{overdue_count} customers owe you — {overdue_count} گاہک مقروض ہیں',
                'body': f'Total receivable: ₨{total_receivable:,.0f}',
                'body_ur': f'کل واجب الوصول: ₨{total_receivable:,.0f}',
                'detail': 'Follow up on outstanding payments',
            })
    except Exception:
        pass

    # ── 3. LARGE PAYABLES ──
    # Convention: negative balance = Cr = we owe them
    try:
        suppliers_owed = Party.objects.filter(
            party_type__in=['supplier', 'both'], is_active=True,
            current_balance__lt=0,
        )
        total_payable = abs(
            suppliers_owed.aggregate(t=Sum('current_balance'))['t'] or Decimal('0')
        )

        if total_payable > 0:
            insights.append({
                'type': 'info',
                'icon': '🏭',
                'title': 'Outstanding Payables — واجب الادا',
                'body': f'You owe suppliers: ₨{total_payable:,.0f}',
                'body_ur': f'سپلائرز کو واجب الادا: ₨{total_payable:,.0f}',
            })
    except Exception:
        pass

    # ── 4. LOW STOCK ALERTS ──
    try:
        low_stock = Product.objects.filter(
            status='active', minimum_stock__gt=0,
            current_stock__lt=F('minimum_stock')
        )
        if low_stock.exists():
            names = ', '.join(p.name for p in low_stock[:3])
            insights.append({
                'type': 'danger',
                'icon': '📦',
                'title': f'{low_stock.count()} products below minimum stock',
                'body': names,
                'body_ur': f'{low_stock.count()} مصنوعات کا اسٹاک کم ہے',
            })
    except Exception:
        pass

    # ── 5. EXPENSE TREND ──
    try:
        this_month_exp = Expense.objects.filter(
            date__gte=month_start
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        last_month_exp = Expense.objects.filter(
            date__range=[last_month_start, last_month_end]
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        if last_month_exp > 0 and this_month_exp > 0:
            change = ((this_month_exp - last_month_exp) / last_month_exp) * 100
            if change > 20:
                insights.append({
                    'type': 'warning',
                    'icon': '🧾',
                    'title': f'Expenses up {change:.0f}% — اخراجات {change:.0f}% بڑھ گئے',
                    'body': f'This month: ₨{this_month_exp:,.0f} vs Last: ₨{last_month_exp:,.0f}',
                    'body_ur': f'اس مہینے: ₨{this_month_exp:,.0f}',
                })

        # Top expense category
        top_cat = Expense.objects.filter(date__gte=month_start).values('category').annotate(
            total=Sum('amount')
        ).order_by('-total').first()
        if top_cat and top_cat['total'] > 0:
            cat_name = top_cat['category'].replace('_', ' ').title()
            pct = (top_cat['total'] / this_month_exp * 100) if this_month_exp else 0
            insights.append({
                'type': 'info',
                'icon': '💡',
                'title': f'Top expense: {cat_name} ({pct:.0f}%)',
                'body': f'₨{top_cat["total"]:,.0f} spent on {cat_name} this month',
                'body_ur': f'اس مہینے {cat_name} پر ₨{top_cat["total"]:,.0f} خرچ ہوئے',
            })
    except Exception:
        pass

    # ── 6. CHEQUES MATURING SOON ──
    try:
        next_week = today + timedelta(days=7)
        maturing = Cheque.objects.filter(
            status__in=['pending', 'deposited'],
            date_on_cheque__lte=next_week,
            date_on_cheque__gte=today,
        )
        if maturing.exists():
            total_chq = maturing.aggregate(t=Sum('amount'))['t'] or 0
            insights.append({
                'type': 'warning',
                'icon': '📝',
                'title': f'{maturing.count()} cheques maturing this week',
                'body': f'Total: ₨{float(total_chq):,.0f}',
                'body_ur': f'{maturing.count()} چیک اس ہفتے میچور ہو رہے ہیں',
            })
    except Exception:
        pass

    # ── 7. CASH FLOW PREDICTION ──
    try:
        last_7_in = ReceiptVoucher.objects.filter(
            date__gte=week_ago, status='final'
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        last_7_out = (
            (PaymentVoucher.objects.filter(date__gte=week_ago, status='final').aggregate(t=Sum('amount'))['t'] or Decimal('0')) +
            (Expense.objects.filter(date__gte=week_ago).aggregate(t=Sum('amount'))['t'] or Decimal('0'))
        )
        weekly_net = last_7_in - last_7_out
        if last_7_in > 0 or last_7_out > 0:
            projected_monthly = weekly_net * 4
            if weekly_net > 0:
                insights.append({
                    'type': 'success',
                    'icon': '💵',
                    'title': 'Positive cash flow — نقدی کا بہاؤ مثبت',
                    'body': f'Last 7 days: +₨{weekly_net:,.0f} net (In: ₨{last_7_in:,.0f}, Out: ₨{last_7_out:,.0f})',
                    'body_ur': f'پچھلے 7 دن: +₨{weekly_net:,.0f}',
                })
            elif weekly_net < 0:
                insights.append({
                    'type': 'danger',
                    'icon': '💸',
                    'title': 'Negative cash flow — نقدی کا بہاؤ منفی',
                    'body': f'Last 7 days: -₨{abs(weekly_net):,.0f} net (In: ₨{last_7_in:,.0f}, Out: ₨{last_7_out:,.0f})',
                    'body_ur': f'پچھلے 7 دن: -₨{abs(weekly_net):,.0f}',
                    'detail': 'You are spending more than receiving. Consider following up on receivables.',
                })
    except Exception:
        pass

    # ── 8. TOP SUPPLIER & CUSTOMER ──
    try:
        top_supplier = Purchase.objects.filter(
            date__gte=month_start, status='final'
        ).values('supplier__name').annotate(
            total=Sum('grand_total')
        ).order_by('-total').first()
        if top_supplier:
            insights.append({
                'type': 'info',
                'icon': '🏆',
                'title': f'Top supplier: {top_supplier["supplier__name"]}',
                'body': f'₨{top_supplier["total"]:,.0f} purchased this month',
                'body_ur': f'اس مہینے سب سے زیادہ خریداری',
            })

        top_customer = Sale.objects.filter(
            date__gte=month_start, status='final'
        ).values('customer__name').annotate(
            total=Sum('grand_total')
        ).order_by('-total').first()
        if top_customer:
            insights.append({
                'type': 'info',
                'icon': '⭐',
                'title': f'Top customer: {top_customer["customer__name"]}',
                'body': f'₨{top_customer["total"]:,.0f} sold this month',
                'body_ur': f'اس مہینے سب سے زیادہ فروخت',
            })
    except Exception:
        pass

    # ── 9. STOCK VALUE ──
    try:
        products = Product.objects.filter(status='active', current_stock__gt=0)
        total_stock_value = sum(p.stock_value for p in products)
        if total_stock_value > 0:
            insights.append({
                'type': 'info',
                'icon': '📊',
                'title': f'Stock value: ₨{total_stock_value:,.0f}',
                'body': f'{products.count()} products in stock',
                'body_ur': f'اسٹاک کی مالیت: ₨{total_stock_value:,.0f}',
            })
    except Exception:
        pass

    # ── 10. TOP CUSTOMER THIS MONTH ──
    try:
        from apps.sales.models import Sale
        top_customer = Sale.objects.filter(
            date__gte=month_start, status='final'
        ).values('customer__name').annotate(
            total=Sum('grand_total')
        ).order_by('-total').first()
        if top_customer and top_customer['total']:
            insights.append({
                'type': 'info', 'icon': '🏆',
                'title': f'Top Customer: {top_customer["customer__name"]}',
                'body': f'₨{top_customer["total"]:,.0f} in sales this month',
                'body_ur': f'اس مہینے سب سے زیادہ خریدنے والے',
            })
    except Exception:
        pass

    # ── 11. BIGGEST UNPAID PURCHASE ──
    try:
        from apps.purchases.models import Purchase
        biggest_unpaid = Purchase.objects.filter(
            status='final', balance_due__gt=0
        ).order_by('-balance_due').first()
        if biggest_unpaid and biggest_unpaid.balance_due > 0:
            insights.append({
                'type': 'warning', 'icon': '⚠️',
                'title': f'Biggest unpaid: ₨{biggest_unpaid.balance_due:,.0f}',
                'body': f'{biggest_unpaid.supplier.name} — {biggest_unpaid.purchase_number}',
                'body_ur': f'سب سے بڑی بقایا خریداری',
            })
    except Exception:
        pass

    # ── 12. CHEQUES PENDING DEPOSIT ──
    try:
        pending_cheques = Cheque.objects.filter(status='pending', direction='received').count()
        if pending_cheques > 0:
            total_pending = Cheque.objects.filter(
                status='pending', direction='received'
            ).aggregate(t=Sum('amount'))['t'] or 0
            insights.append({
                'type': 'warning', 'icon': '📝',
                'title': f'{pending_cheques} cheque(s) pending deposit',
                'body': f'Total: ₨{total_pending:,.0f} — deposit them soon',
                'body_ur': f'{pending_cheques} چیک جمع کرانے ہیں',
            })
    except Exception:
        pass

    # If no insights, add a welcome message
    if not insights:
        insights.append({
            'type': 'info',
            'icon': '👋',
            'title': 'Start adding data to see insights',
            'body': 'Create purchases, sales, and payments to unlock smart business insights.',
            'body_ur': 'خریداری، فروخت اور ادائیگی شامل کریں تاکہ ذہین بصیرت دیکھ سکیں',
        })

    return insights
