"""
Automated Backup & Report Email System
Sends daily CSV backup + morning agenda + evening summary via Gmail.
"""
import csv
import html as html_mod
import io
import logging
import zipfile
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum, Count, Q, F
from django.utils import timezone

logger = logging.getLogger('backup_email')

TWO = Decimal('0.01')


def _esc(value):
    """HTML-escape any user-provided text to prevent broken HTML / XSS."""
    if value is None:
        return ''
    return html_mod.escape(str(value))


def _get_settings():
    """Get company settings safely."""
    try:
        from apps.settings_app.models import CompanySettings
        return CompanySettings.get_settings()
    except Exception:
        return None


def _send_email(subject, html_body, attachments=None):
    """Send email via Gmail SMTP with app password."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    cs = _get_settings()
    password = cs.get_email_password() if cs else ''
    if not cs or not cs.backup_email or not password:
        logger.warning("Email not configured — skipping")
        return False

    sender = cs.backup_email
    recipients = [sender]
    if cs.backup_email_secondary:
        recipients.append(cs.backup_email_secondary)

    try:
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))

        if attachments:
            for filename, data in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(data)
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipients, msg.as_string())
        server.quit()

        logger.info(f"Email sent: {subject} → {recipients}")
        return True
    except Exception as e:
        logger.error(f"Email failed: {e}")
        return False


# ─── HTML Helpers ────────────────────────────────────────────────

def _fmt(amount):
    """Format PKR amount with commas."""
    if amount is None:
        return '₨ 0'
    return f'₨ {amount:,.0f}'


def _card(label, value, color='#374151', bg='#f9fafb'):
    """Render a summary card."""
    return f'''
    <td style="padding:12px 16px;background:{bg};border-radius:12px;text-align:center;width:25%;">
        <div style="font-size:11px;color:#6b7280;font-weight:600;">{label}</div>
        <div style="font-size:18px;font-weight:800;color:{color};margin-top:4px;">{value}</div>
    </td>'''


def _section_header(emoji, title, urdu='', count=None):
    """Render a section header."""
    badge = f' <span style="background:#fbbf24;color:#78350f;padding:2px 8px;border-radius:8px;font-size:12px;font-weight:700;">{count}</span>' if count else ''
    urdu_text = f' — {urdu}' if urdu else ''
    return f'''
    <tr><td colspan="10" style="padding:20px 0 8px 0;">
        <h3 style="margin:0;color:#1e293b;font-size:16px;">{emoji} {title}{urdu_text}{badge}</h3>
    </td></tr>'''


def _alert_row(text, amount, color='#dc2626', detail=''):
    """Red/orange alert row. `text` and `detail` are pre-escaped by caller."""
    detail_html = f'<br><span style="font-size:11px;color:#9ca3af;">{detail}</span>' if detail else ''
    return f'''
    <tr style="border-bottom:1px solid #f3f4f6;">
        <td style="padding:8px 12px;font-size:13px;">{text}{detail_html}</td>
        <td style="padding:8px 12px;text-align:right;font-weight:700;color:{color};font-size:14px;white-space:nowrap;">{_fmt(amount)}</td>
    </tr>'''


def _txn_row(date_str, party, narration, amount, color='#374151', method=''):
    """Transaction detail row. All text params must be pre-escaped by caller."""
    method_badge = f'<span style="background:#e5e7eb;padding:1px 6px;border-radius:4px;font-size:10px;margin-left:4px;">{method}</span>' if method else ''
    return f'''
    <tr style="border-bottom:1px solid #f3f4f6;">
        <td style="padding:6px 10px;font-size:12px;color:#6b7280;white-space:nowrap;">{date_str}</td>
        <td style="padding:6px 10px;font-size:13px;font-weight:600;">{party}{method_badge}</td>
        <td style="padding:6px 10px;font-size:12px;color:#6b7280;">{narration}</td>
        <td style="padding:6px 10px;text-align:right;font-weight:700;color:{color};font-size:13px;white-space:nowrap;">{_fmt(amount)}</td>
    </tr>'''


def _empty_row(text):
    """Empty state row."""
    return f'<tr><td colspan="10" style="padding:12px;text-align:center;color:#9ca3af;font-size:13px;">✓ {text}</td></tr>'


def _table_start():
    return '<table style="width:100%;border-collapse:collapse;margin:0 0 8px 0;">'


def _table_end():
    return '</table>'


# ─── Morning Report: Today's Agenda ─────────────────────────────

def send_morning_report():
    """
    ☀️ MORNING REPORT (7 AM) — "Today's Agenda"
    1. Yesterday's Quick Summary
    2. ⚠️ Cheques Due Today
    3. ⚠️ Payments Due Today (purchase credit days expiring)
    4. ⚠️ Overdue Receivables
    5. 📋 Pending Cheques (not yet deposited)
    6. 🔴 Low Stock Alerts
    """
    cs = _get_settings()
    if not cs or not cs.report_enabled:
        return

    try:
        from apps.purchases.models import Purchase
        from apps.sales.models import Sale
        from apps.finance.models import PaymentVoucher, ReceiptVoucher, Expense, Cheque
        from apps.parties.models import Party
        from apps.products.models import Product

        today = date.today()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        company = _esc(cs.company_name or 'Cotton Factory')

        # ── Section 1: Yesterday's Quick Summary ──
        y_purchases = Purchase.objects.filter(date=yesterday, status='final').aggregate(
            total=Sum('grand_total'), count=Count('id'))
        y_sales = Sale.objects.filter(date=yesterday, status='final').aggregate(
            total=Sum('grand_total'), count=Count('id'))
        y_received = ReceiptVoucher.objects.filter(date=yesterday, status='final').aggregate(
            total=Sum('amount'), count=Count('id'))
        y_paid = PaymentVoucher.objects.filter(date=yesterday, status='final').aggregate(
            total=Sum('amount'), count=Count('id'))
        y_expenses = Expense.objects.filter(date=yesterday).aggregate(
            total=Sum('amount'), count=Count('id'))

        y_purchase_total = y_purchases['total'] or 0
        y_sale_total = y_sales['total'] or 0
        y_received_total = y_received['total'] or 0
        y_paid_total = y_paid['total'] or 0
        y_expense_total = y_expenses['total'] or 0

        # ── Section 2: Cheques Due Today ──
        cheques_due_today = Cheque.objects.filter(
            date_on_cheque=today,
            status__in=['pending', 'deposited']
        ).select_related('party').order_by('amount')

        # Cheques due tomorrow (for heads-up)
        cheques_due_tomorrow = Cheque.objects.filter(
            date_on_cheque=tomorrow,
            status__in=['pending', 'deposited']
        ).select_related('party').order_by('amount')

        # ── Section 3: Payments Due Today ──
        # Purchases whose due_date is today and still have balance
        purchases_due_today = Purchase.objects.filter(
            due_date=today,
            status='final',
            balance_due__gt=0
        ).select_related('supplier').order_by('-balance_due')

        # ── Section 4: Overdue Receivables ──
        # Sales whose due_date has passed and still have balance
        overdue_sales = Sale.objects.filter(
            due_date__lt=today,
            status='final',
            balance_due__gt=0
        ).select_related('customer').order_by('-balance_due')[:10]

        # Overdue purchases (we need to pay)
        overdue_purchases = Purchase.objects.filter(
            due_date__lt=today,
            status='final',
            balance_due__gt=0
        ).select_related('supplier').order_by('-balance_due')[:10]

        # ── Section 5: Pending Cheques (not deposited yet) ──
        pending_cheques = Cheque.objects.filter(
            status='pending'
        ).select_related('party').order_by('date_on_cheque')

        # ── Section 6: Low Stock ──
        low_stock = Product.objects.filter(
            status='active',
            current_stock__lt=F('minimum_stock'),
            minimum_stock__gt=0
        ).order_by('current_stock')

        negative_stock = Product.objects.filter(
            status='active',
            current_stock__lt=0
        )

        # ── Build Email HTML ──
        alert_count = (
            cheques_due_today.count() +
            purchases_due_today.count() +
            overdue_sales.count() +
            overdue_purchases.count() +
            pending_cheques.count() +
            low_stock.count() +
            negative_stock.count()
        )

        html_parts = []
        html_parts.append(f'''
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:640px;margin:0 auto;background:#ffffff;">
            <div style="background:linear-gradient(135deg,#059669,#047857);padding:24px;border-radius:16px 16px 0 0;">
                <h1 style="margin:0;color:white;font-size:20px;">☀️ صبح کی رپورٹ — Morning Agenda</h1>
                <p style="margin:4px 0 0;color:#a7f3d0;font-size:13px;">{company} — {today.strftime("%A, %d %B %Y")}</p>
                {'<p style="margin:4px 0 0;color:#fbbf24;font-size:13px;font-weight:700;">⚠️ ' + str(alert_count) + ' items need your attention today</p>' if alert_count > 0 else '<p style="margin:4px 0 0;color:#a7f3d0;font-size:13px;">✅ No urgent items today — سب ٹھیک ہے</p>'}
            </div>
            <div style="padding:16px 20px;">
        ''')

        # ── Yesterday's Summary ──
        html_parts.append(f'''
            <h3 style="color:#6b7280;font-size:13px;margin:16px 0 8px;text-transform:uppercase;letter-spacing:1px;">📊 Yesterday's Summary — کل کا خلاصہ ({yesterday.strftime("%d %b")})</h3>
            <table style="width:100%;border-collapse:separate;border-spacing:6px;">
            <tr>
                {_card('Purchases خریداری', _fmt(y_purchase_total), '#ea580c', '#fff7ed')}
                {_card('Sales فروخت', _fmt(y_sale_total), '#059669', '#f0fdf4')}
                {_card('Received وصولی', _fmt(y_received_total), '#2563eb', '#eff6ff')}
                {_card('Paid Out ادائیگی', _fmt(y_paid_total), '#dc2626', '#fef2f2')}
            </tr></table>
        ''')
        if y_expense_total:
            html_parts.append(f'<p style="font-size:12px;color:#6b7280;margin:2px 0 0 4px;">Expenses: {_fmt(y_expense_total)} ({y_expenses["count"]})</p>')

        # ── Cheques Due Today ──
        html_parts.append(_table_start())
        html_parts.append(_section_header('🔔', 'Cheques Due Today', 'آج کے چیک', cheques_due_today.count() or None))
        if cheques_due_today.exists():
            for ch in cheques_due_today:
                direction = '← Received' if ch.direction == 'received' else '→ Issued'
                html_parts.append(_alert_row(
                    f'<strong>{_esc(ch.party.name)}</strong> — #{_esc(ch.cheque_number)}',
                    ch.amount,
                    '#dc2626' if ch.direction == 'issued' else '#059669',
                    f'{direction} • {_esc(ch.bank_name)} • Status: {ch.get_status_display()}'
                ))
        else:
            html_parts.append(_empty_row('No cheques due today'))
        html_parts.append(_table_end())

        # Cheques due tomorrow
        if cheques_due_tomorrow.exists():
            html_parts.append(_table_start())
            html_parts.append(_section_header('📅', 'Cheques Due Tomorrow', 'کل کے چیک', cheques_due_tomorrow.count()))
            for ch in cheques_due_tomorrow:
                direction = '← Received' if ch.direction == 'received' else '→ Issued'
                html_parts.append(_alert_row(
                    f'<strong>{_esc(ch.party.name)}</strong> — #{_esc(ch.cheque_number)}',
                    ch.amount,
                    '#d97706',
                    f'{direction} • {_esc(ch.bank_name)}'
                ))
            html_parts.append(_table_end())

        # ── Payments Due Today (Purchases) ──
        html_parts.append(_table_start())
        html_parts.append(_section_header('💰', 'Payments Due Today', 'آج کی واجب ادائیگیاں', purchases_due_today.count() or None))
        if purchases_due_today.exists():
            total_due = Decimal('0')
            for p in purchases_due_today:
                total_due += p.balance_due
                html_parts.append(_alert_row(
                    f'<strong>{_esc(p.supplier.name)}</strong>',
                    p.balance_due,
                    '#dc2626',
                    f'{_esc(p.purchase_number)} • Total: {_fmt(p.grand_total)}'
                ))
            html_parts.append(f'<tr><td style="padding:8px 12px;font-weight:700;font-size:13px;">TOTAL DUE TODAY</td>'
                            f'<td style="padding:8px 12px;text-align:right;font-weight:800;color:#dc2626;font-size:15px;">{_fmt(total_due)}</td></tr>')
        else:
            html_parts.append(_empty_row('No payments due today'))
        html_parts.append(_table_end())

        # ── Overdue Receivables (Sales) ──
        if overdue_sales.exists():
            html_parts.append(_table_start())
            total_overdue_recv = Sale.objects.filter(
                due_date__lt=today, status='final', balance_due__gt=0
            ).aggregate(t=Sum('balance_due'))['t'] or 0
            html_parts.append(_section_header('⚠️', 'Overdue Receivables', 'واجب الوصول بقایا', overdue_sales.count()))
            for s in overdue_sales:
                days = (today - s.due_date).days
                html_parts.append(_alert_row(
                    f'<strong>{_esc(s.customer.name)}</strong>',
                    s.balance_due,
                    '#ea580c',
                    f'{_esc(s.invoice_number)} • {days} days overdue'
                ))
            html_parts.append(f'<tr><td style="padding:8px 12px;font-weight:700;font-size:13px;">TOTAL OVERDUE RECEIVABLES</td>'
                            f'<td style="padding:8px 12px;text-align:right;font-weight:800;color:#ea580c;font-size:15px;">{_fmt(total_overdue_recv)}</td></tr>')
            html_parts.append(_table_end())

        # ── Overdue Payments (Purchases we haven't paid) ──
        if overdue_purchases.exists():
            html_parts.append(_table_start())
            total_overdue_pay = Purchase.objects.filter(
                due_date__lt=today, status='final', balance_due__gt=0
            ).aggregate(t=Sum('balance_due'))['t'] or 0
            html_parts.append(_section_header('🔴', 'Overdue Payments', 'واجب الادا بقایا', overdue_purchases.count()))
            for p in overdue_purchases:
                days = (today - p.due_date).days
                html_parts.append(_alert_row(
                    f'<strong>{_esc(p.supplier.name)}</strong>',
                    p.balance_due,
                    '#dc2626',
                    f'{_esc(p.purchase_number)} • {days} days overdue'
                ))
            html_parts.append(f'<tr><td style="padding:8px 12px;font-weight:700;font-size:13px;">TOTAL OVERDUE PAYMENTS</td>'
                            f'<td style="padding:8px 12px;text-align:right;font-weight:800;color:#dc2626;font-size:15px;">{_fmt(total_overdue_pay)}</td></tr>')
            html_parts.append(_table_end())

        # ── Pending Cheques (need to deposit) ──
        if pending_cheques.exists():
            html_parts.append(_table_start())
            html_parts.append(_section_header('📋', 'Pending Cheques — Not Deposited', 'جمع نہ کرائے گئے چیک', pending_cheques.count()))
            pending_total = Decimal('0')
            for ch in pending_cheques:
                pending_total += ch.amount
                days_since = (today - ch.date_on_cheque).days if ch.date_on_cheque <= today else 0
                age_text = f'{days_since} days old' if days_since > 0 else f'Due {ch.date_on_cheque.strftime("%d %b")}'
                html_parts.append(_alert_row(
                    f'<strong>{_esc(ch.party.name)}</strong> — #{_esc(ch.cheque_number)}',
                    ch.amount,
                    '#d97706',
                    f'{_esc(ch.bank_name)} • {age_text}'
                ))
            html_parts.append(f'<tr><td style="padding:8px 12px;font-weight:700;font-size:13px;">TOTAL PENDING</td>'
                            f'<td style="padding:8px 12px;text-align:right;font-weight:800;color:#d97706;font-size:15px;">{_fmt(pending_total)}</td></tr>')
            html_parts.append(_table_end())

        # ── Low Stock Alerts ──
        if low_stock.exists() or negative_stock.exists():
            html_parts.append(_table_start())
            html_parts.append(_section_header('📦', 'Low/Negative Stock', 'کم اسٹاک',
                                            low_stock.count() + negative_stock.count()))
            for p in negative_stock:
                unit_abbr = _esc(p.unit.abbreviation) if p.unit else 'KG'
                html_parts.append(f'''
                <tr style="border-bottom:1px solid #fecaca;background:#fef2f2;">
                    <td style="padding:8px 12px;font-size:13px;"><strong>{_esc(p.name)}</strong>
                        <br><span style="font-size:11px;color:#dc2626;">⛔ NEGATIVE STOCK</span></td>
                    <td style="padding:8px 12px;text-align:right;font-weight:700;color:#dc2626;font-size:14px;">{p.current_stock} {unit_abbr}</td>
                </tr>''')
            for p in low_stock:
                unit_abbr = _esc(p.unit.abbreviation) if p.unit else 'KG'
                html_parts.append(f'''
                <tr style="border-bottom:1px solid #f3f4f6;">
                    <td style="padding:8px 12px;font-size:13px;"><strong>{_esc(p.name)}</strong>
                        <br><span style="font-size:11px;color:#d97706;">Min: {p.minimum_stock}</span></td>
                    <td style="padding:8px 12px;text-align:right;font-weight:700;color:#d97706;font-size:14px;">{p.current_stock} {unit_abbr}</td>
                </tr>''')
            html_parts.append(_table_end())

        # ── Footer ──
        html_parts.append(f'''
            <hr style="border:1px solid #e5e7eb;margin:20px 0;">
            <p style="color:#9ca3af;font-size:11px;text-align:center;">
                {company} — Morning Agenda Report • Generated {timezone.now().strftime("%I:%M %p")} PKT
            </p>
            </div></div>
        ''')

        subject = f'☀️ {company} — Morning Agenda — {today.strftime("%d %b %Y")}'
        if alert_count > 0:
            subject += f' — ⚠️ {alert_count} alerts'

        html = ''.join(html_parts)
        success = _send_email(subject, html)
        if success:
            cs.last_report_email_at = timezone.now()
            cs.save(update_fields=['last_report_email_at'])
        return success

    except Exception as e:
        logger.error(f"Morning report failed: {e}", exc_info=True)
        return False


# ─── Evening Report: Today's Full Summary ────────────────────────

def send_evening_report():
    """
    🌙 EVENING REPORT (10 PM) — "Today's Full Summary"
    1. Today's P&L Summary
    2. 💰 Cash & Bank Position
    3. 📋 Today's Transactions (actual list)
    4. 📊 Top 5 Receivables & Top 5 Payables
    5. ⚠️ Tomorrow's Agenda
    6. Week-to-date vs last week comparison
    """
    cs = _get_settings()
    if not cs or not cs.report_enabled:
        return

    try:
        from apps.purchases.models import Purchase
        from apps.sales.models import Sale
        from apps.finance.models import PaymentVoucher, ReceiptVoucher, Expense, Cheque, BankAccount
        from apps.parties.models import Party

        today = date.today()
        tomorrow = today + timedelta(days=1)
        company = _esc(cs.company_name or 'Cotton Factory')

        # ── Section 1: Today's P&L ──
        t_purchases = Purchase.objects.filter(date=today, status='final')
        t_sales = Sale.objects.filter(date=today, status='final')
        t_payments = PaymentVoucher.objects.filter(date=today, status='final')
        t_receipts = ReceiptVoucher.objects.filter(date=today, status='final')
        t_expenses = Expense.objects.filter(date=today)

        total_purchases = t_purchases.aggregate(t=Sum('grand_total'))['t'] or Decimal('0')
        total_sales = t_sales.aggregate(t=Sum('grand_total'))['t'] or Decimal('0')
        total_payments = t_payments.aggregate(t=Sum('amount'))['t'] or Decimal('0')
        total_receipts = t_receipts.aggregate(t=Sum('amount'))['t'] or Decimal('0')
        total_expenses = t_expenses.aggregate(t=Sum('amount'))['t'] or Decimal('0')

        gross_profit = total_sales - total_purchases
        net_profit = gross_profit - total_expenses
        cash_flow = total_receipts - total_payments - total_expenses

        # ── Section 2: Cash & Bank Position ──
        bank_accounts = BankAccount.objects.filter(is_active=True).order_by('-current_balance')

        # Estimate cash position: sum of all cash receipts - cash payments - cash expenses for all time
        # (This is approximate — ideally tracked via a Cash Account in Chart of Accounts)
        total_bank_balance = bank_accounts.aggregate(t=Sum('current_balance'))['t'] or Decimal('0')

        total_receivable = Party.objects.filter(
            current_balance__gt=0, is_active=True
        ).aggregate(t=Sum('current_balance'))['t'] or Decimal('0')
        total_payable = abs(Party.objects.filter(
            current_balance__lt=0, is_active=True
        ).aggregate(t=Sum('current_balance'))['t'] or Decimal('0'))

        # ── Section 3: Today's Transactions ──
        # (we'll list the actual items)

        # ── Section 4: Top Receivables & Payables ──
        top_receivables = Party.objects.filter(
            current_balance__gt=0, is_active=True
        ).order_by('-current_balance')[:7]

        top_payables = Party.objects.filter(
            current_balance__lt=0, is_active=True
        ).order_by('current_balance')[:7]

        # ── Section 5: Tomorrow's Agenda ──
        cheques_tomorrow = Cheque.objects.filter(
            date_on_cheque=tomorrow,
            status__in=['pending', 'deposited']
        ).select_related('party')

        purchases_due_tomorrow = Purchase.objects.filter(
            due_date=tomorrow, status='final', balance_due__gt=0
        ).select_related('supplier')

        # ── Section 6: Week comparison ──
        # This week (Mon-today) vs last week (Mon-Sun)
        days_since_monday = today.weekday()  # 0=Monday
        this_week_start = today - timedelta(days=days_since_monday)
        last_week_start = this_week_start - timedelta(days=7)
        last_week_end = this_week_start - timedelta(days=1)

        tw_purchases = Purchase.objects.filter(date__gte=this_week_start, date__lte=today, status='final').aggregate(t=Sum('grand_total'))['t'] or 0
        tw_sales = Sale.objects.filter(date__gte=this_week_start, date__lte=today, status='final').aggregate(t=Sum('grand_total'))['t'] or 0
        tw_received = ReceiptVoucher.objects.filter(date__gte=this_week_start, date__lte=today, status='final').aggregate(t=Sum('amount'))['t'] or 0
        tw_paid = PaymentVoucher.objects.filter(date__gte=this_week_start, date__lte=today, status='final').aggregate(t=Sum('amount'))['t'] or 0

        lw_purchases = Purchase.objects.filter(date__gte=last_week_start, date__lte=last_week_end, status='final').aggregate(t=Sum('grand_total'))['t'] or 0
        lw_sales = Sale.objects.filter(date__gte=last_week_start, date__lte=last_week_end, status='final').aggregate(t=Sum('grand_total'))['t'] or 0
        lw_received = ReceiptVoucher.objects.filter(date__gte=last_week_start, date__lte=last_week_end, status='final').aggregate(t=Sum('amount'))['t'] or 0
        lw_paid = PaymentVoucher.objects.filter(date__gte=last_week_start, date__lte=last_week_end, status='final').aggregate(t=Sum('amount'))['t'] or 0

        # ── Receipt/Payment method breakdown ──
        method_in = {}
        for r in t_receipts.select_related('party'):
            m = r.get_payment_method_display()
            method_in[m] = method_in.get(m, Decimal('0')) + r.amount
        method_out = {}
        for p in t_payments.select_related('party'):
            m = p.get_payment_method_display()
            method_out[m] = method_out.get(m, Decimal('0')) + p.amount

        # ── Expense breakdown by category ──
        expense_by_cat = {}
        for e in t_expenses:
            cat = e.get_category_display()
            expense_by_cat[cat] = expense_by_cat.get(cat, Decimal('0')) + e.amount

        # ══════ Build HTML ══════
        html_parts = []
        html_parts.append(f'''
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:640px;margin:0 auto;background:#ffffff;">
            <div style="background:linear-gradient(135deg,#1e293b,#334155);padding:24px;border-radius:16px 16px 0 0;">
                <h1 style="margin:0;color:white;font-size:20px;">🌙 شام کی رپورٹ — Evening Summary</h1>
                <p style="margin:4px 0 0;color:#94a3b8;font-size:13px;">{company} — {today.strftime("%A, %d %B %Y")}</p>
            </div>
            <div style="padding:16px 20px;">
        ''')

        # ── P&L Summary Cards ──
        profit_color = '#059669' if net_profit >= 0 else '#dc2626'
        profit_bg = '#f0fdf4' if net_profit >= 0 else '#fef2f2'
        profit_label = 'Net Profit نفع' if net_profit >= 0 else 'Net Loss نقصان'
        cashflow_color = '#059669' if cash_flow >= 0 else '#dc2626'

        html_parts.append(f'''
            <h3 style="color:#6b7280;font-size:13px;margin:16px 0 8px;text-transform:uppercase;letter-spacing:1px;">📊 Today's P&L — آج کا نفع نقصان</h3>
            <table style="width:100%;border-collapse:separate;border-spacing:6px;">
            <tr>
                {_card('Sales فروخت', _fmt(total_sales), '#059669', '#f0fdf4')}
                {_card('Purchases خریداری', _fmt(total_purchases), '#ea580c', '#fff7ed')}
                {_card('Expenses اخراجات', _fmt(total_expenses), '#d97706', '#fffbeb')}
                {_card(profit_label, _fmt(abs(net_profit)), profit_color, profit_bg)}
            </tr></table>

            <table style="width:100%;border-collapse:separate;border-spacing:6px;margin-top:4px;">
            <tr>
                {_card('Received وصولی', _fmt(total_receipts), '#2563eb', '#eff6ff')}
                {_card('Paid Out ادائیگی', _fmt(total_payments), '#dc2626', '#fef2f2')}
                {_card('Cash Flow', _fmt(abs(cash_flow)), cashflow_color, '#f9fafb')}
                {_card('Txn Count', f'{t_purchases.count() + t_sales.count() + t_receipts.count() + t_payments.count() + t_expenses.count()}', '#6b7280', '#f9fafb')}
            </tr></table>
        ''')

        # ── Cash & Bank Position ──
        html_parts.append(f'''
            <h3 style="color:#6b7280;font-size:13px;margin:20px 0 8px;text-transform:uppercase;letter-spacing:1px;">🏦 Bank Position — بینک پوزیشن</h3>
            {_table_start()}
        ''')
        if bank_accounts.exists():
            for ba in bank_accounts:
                bal_color = '#059669' if ba.current_balance >= 0 else '#dc2626'
                html_parts.append(f'''
                <tr style="border-bottom:1px solid #f3f4f6;">
                    <td style="padding:8px 12px;font-size:13px;"><strong>{_esc(ba.bank_name)}</strong>
                        <br><span style="font-size:11px;color:#9ca3af;">{_esc(ba.account_number)} • {ba.get_account_type_display()}</span></td>
                    <td style="padding:8px 12px;text-align:right;font-weight:700;color:{bal_color};font-size:14px;">{_fmt(ba.current_balance)}</td>
                </tr>''')
            html_parts.append(f'''
            <tr style="background:#f0f9ff;">
                <td style="padding:10px 12px;font-weight:700;font-size:14px;">Total Bank Balance</td>
                <td style="padding:10px 12px;text-align:right;font-weight:800;color:#1e40af;font-size:16px;">{_fmt(total_bank_balance)}</td>
            </tr>''')
        else:
            html_parts.append(_empty_row('No bank accounts configured'))
        html_parts.append(_table_end())

        # Outstanding balances
        html_parts.append(f'''
            <table style="width:100%;border-collapse:separate;border-spacing:6px;margin-top:8px;">
            <tr>
                {_card('Total Receivable وصول شدنی', _fmt(total_receivable), '#059669', '#f0fdf4')}
                {_card('Total Payable واجب الادا', _fmt(total_payable), '#dc2626', '#fef2f2')}
            </tr></table>
        ''')

        # ── Today's Transactions Detail ──
        html_parts.append(f'''
            <h3 style="color:#6b7280;font-size:13px;margin:20px 0 8px;text-transform:uppercase;letter-spacing:1px;">📋 Today's Transactions — آج کے لین دین</h3>
        ''')

        # Purchases
        if t_purchases.exists():
            html_parts.append(_table_start())
            html_parts.append(_section_header('📥', 'Purchases', 'خریداری', t_purchases.count()))
            for p in t_purchases.select_related('supplier').order_by('-grand_total'):
                items_text = ', '.join([_esc(i.product.name) for i in p.items.select_related('product').all()[:3]])
                if p.items.count() > 3:
                    items_text += f' +{p.items.count()-3} more'
                html_parts.append(_txn_row(
                    _esc(p.purchase_number), _esc(p.supplier.name), items_text,
                    p.grand_total, '#ea580c'
                ))
            html_parts.append(f'<tr style="background:#fff7ed;"><td colspan="3" style="padding:8px 12px;font-weight:700;">Total Purchases</td>'
                            f'<td style="padding:8px 12px;text-align:right;font-weight:800;color:#ea580c;">{_fmt(total_purchases)}</td></tr>')
            html_parts.append(_table_end())

        # Sales
        if t_sales.exists():
            html_parts.append(_table_start())
            html_parts.append(_section_header('📤', 'Sales', 'فروخت', t_sales.count()))
            for s in t_sales.select_related('customer').order_by('-grand_total'):
                items_text = ', '.join([_esc(i.product.name) for i in s.items.select_related('product').all()[:3]])
                if s.items.count() > 3:
                    items_text += f' +{s.items.count()-3} more'
                html_parts.append(_txn_row(
                    _esc(s.invoice_number), _esc(s.customer.name), items_text,
                    s.grand_total, '#059669'
                ))
            html_parts.append(f'<tr style="background:#f0fdf4;"><td colspan="3" style="padding:8px 12px;font-weight:700;">Total Sales</td>'
                            f'<td style="padding:8px 12px;text-align:right;font-weight:800;color:#059669;">{_fmt(total_sales)}</td></tr>')
            html_parts.append(_table_end())

        # Receipts
        if t_receipts.exists():
            html_parts.append(_table_start())
            html_parts.append(_section_header('💚', 'Receipts', 'وصولیاں', t_receipts.count()))
            for r in t_receipts.select_related('party').order_by('-amount'):
                html_parts.append(_txn_row(
                    _esc(r.voucher_number), _esc(r.party.name), _esc(r.narration or '—'),
                    r.amount, '#059669', r.get_payment_method_display()
                ))
            html_parts.append(f'<tr style="background:#f0fdf4;"><td colspan="3" style="padding:8px 12px;font-weight:700;">Total Received</td>'
                            f'<td style="padding:8px 12px;text-align:right;font-weight:800;color:#059669;">{_fmt(total_receipts)}</td></tr>')
            html_parts.append(_table_end())

        # Payments
        if t_payments.exists():
            html_parts.append(_table_start())
            html_parts.append(_section_header('💸', 'Payments', 'ادائیگیاں', t_payments.count()))
            for p in t_payments.select_related('party').order_by('-amount'):
                html_parts.append(_txn_row(
                    _esc(p.voucher_number), _esc(p.party.name), _esc(p.narration or '—'),
                    p.amount, '#dc2626', p.get_payment_method_display()
                ))
            html_parts.append(f'<tr style="background:#fef2f2;"><td colspan="3" style="padding:8px 12px;font-weight:700;">Total Paid</td>'
                            f'<td style="padding:8px 12px;text-align:right;font-weight:800;color:#dc2626;">{_fmt(total_payments)}</td></tr>')
            html_parts.append(_table_end())

        # Expenses
        if t_expenses.exists():
            html_parts.append(_table_start())
            html_parts.append(_section_header('🧾', 'Expenses', 'اخراجات', t_expenses.count()))
            for e in t_expenses:
                html_parts.append(_txn_row(
                    '', e.get_category_display(), _esc(e.paid_to or e.description or '—'),
                    e.amount, '#d97706', e.get_payment_method_display()
                ))
            html_parts.append(f'<tr style="background:#fffbeb;"><td colspan="3" style="padding:8px 12px;font-weight:700;">Total Expenses</td>'
                            f'<td style="padding:8px 12px;text-align:right;font-weight:800;color:#d97706;">{_fmt(total_expenses)}</td></tr>')
            html_parts.append(_table_end())

        # No transactions today
        if not any([t_purchases.exists(), t_sales.exists(), t_receipts.exists(), t_payments.exists(), t_expenses.exists()]):
            html_parts.append(f'<p style="text-align:center;color:#9ca3af;padding:16px;">No transactions recorded today</p>')

        # ── Top Receivables & Payables ──
        html_parts.append(f'''
            <h3 style="color:#6b7280;font-size:13px;margin:20px 0 8px;text-transform:uppercase;letter-spacing:1px;">📊 Outstanding Balances — بقایا جات</h3>
        ''')

        # Top Receivables
        html_parts.append(_table_start())
        html_parts.append(_section_header('🟢', 'Top Receivables', 'وصول شدنی'))
        if top_receivables.exists():
            for p in top_receivables:
                html_parts.append(_alert_row(
                    f'<strong>{_esc(p.name)}</strong>',
                    p.current_balance, '#059669',
                    f'{p.get_party_type_display()} • {_esc(p.city or "—")}'
                ))
        else:
            html_parts.append(_empty_row('No outstanding receivables'))
        html_parts.append(_table_end())

        # Top Payables
        html_parts.append(_table_start())
        html_parts.append(_section_header('🔴', 'Top Payables', 'واجب الادا'))
        if top_payables.exists():
            for p in top_payables:
                html_parts.append(_alert_row(
                    f'<strong>{_esc(p.name)}</strong>',
                    abs(p.current_balance), '#dc2626',
                    f'{p.get_party_type_display()} • {_esc(p.city or "—")}'
                ))
        else:
            html_parts.append(_empty_row('No outstanding payables'))
        html_parts.append(_table_end())

        # ── Tomorrow's Agenda Preview ──
        tomorrow_items = cheques_tomorrow.count() + purchases_due_tomorrow.count()
        if tomorrow_items > 0:
            html_parts.append(f'''
                <h3 style="color:#6b7280;font-size:13px;margin:20px 0 8px;text-transform:uppercase;letter-spacing:1px;">📅 Tomorrow's Agenda — کل کا پروگرام ({tomorrow.strftime("%d %b")})</h3>
                {_table_start()}
            ''')
            if cheques_tomorrow.exists():
                html_parts.append(_section_header('🔔', 'Cheques Due', '', cheques_tomorrow.count()))
                for ch in cheques_tomorrow:
                    direction = '← Recv' if ch.direction == 'received' else '→ Issued'
                    html_parts.append(_alert_row(
                        f'{_esc(ch.party.name)} — #{_esc(ch.cheque_number)}',
                        ch.amount, '#d97706',
                        f'{direction} • {_esc(ch.bank_name)}'
                    ))
            if purchases_due_tomorrow.exists():
                html_parts.append(_section_header('💰', 'Payments Due', '', purchases_due_tomorrow.count()))
                for p in purchases_due_tomorrow:
                    html_parts.append(_alert_row(
                        _esc(p.supplier.name),
                        p.balance_due, '#dc2626',
                        _esc(p.purchase_number)
                    ))
            html_parts.append(_table_end())

        # ── Weekly Comparison ──
        html_parts.append(f'''
            <h3 style="color:#6b7280;font-size:13px;margin:20px 0 8px;text-transform:uppercase;letter-spacing:1px;">📈 Weekly Comparison — ہفتہ وار موازنہ</h3>
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <thead>
                    <tr style="background:#f9fafb;">
                        <th style="padding:8px 12px;text-align:left;font-weight:600;color:#6b7280;"></th>
                        <th style="padding:8px 12px;text-align:right;font-weight:600;color:#6b7280;">This Week<br><span style="font-size:10px;">{this_week_start.strftime("%d %b")}–{today.strftime("%d %b")}</span></th>
                        <th style="padding:8px 12px;text-align:right;font-weight:600;color:#6b7280;">Last Week<br><span style="font-size:10px;">{last_week_start.strftime("%d %b")}–{last_week_end.strftime("%d %b")}</span></th>
                        <th style="padding:8px 12px;text-align:right;font-weight:600;color:#6b7280;">Change</th>
                    </tr>
                </thead><tbody>
        ''')

        def _compare_row(label, this_val, last_val, color):
            this_v = float(this_val)
            last_v = float(last_val)
            diff = this_v - last_v
            pct = f'{(diff/last_v*100):+.0f}%' if last_v > 0 else ('—' if this_v == 0 else 'NEW')
            diff_color = '#059669' if diff >= 0 else '#dc2626'
            arrow = '↑' if diff > 0 else ('↓' if diff < 0 else '→')
            return f'''
            <tr style="border-bottom:1px solid #f3f4f6;">
                <td style="padding:8px 12px;font-weight:600;color:{color};">{label}</td>
                <td style="padding:8px 12px;text-align:right;font-weight:700;">{_fmt(this_v)}</td>
                <td style="padding:8px 12px;text-align:right;color:#6b7280;">{_fmt(last_v)}</td>
                <td style="padding:8px 12px;text-align:right;font-weight:700;color:{diff_color};">{arrow} {pct}</td>
            </tr>'''

        html_parts.append(_compare_row('Purchases خریداری', tw_purchases, lw_purchases, '#ea580c'))
        html_parts.append(_compare_row('Sales فروخت', tw_sales, lw_sales, '#059669'))
        html_parts.append(_compare_row('Received وصولی', tw_received, lw_received, '#2563eb'))
        html_parts.append(_compare_row('Paid Out ادائیگی', tw_paid, lw_paid, '#dc2626'))

        html_parts.append('</tbody></table>')

        # ── Footer ──
        html_parts.append(f'''
            <hr style="border:1px solid #e5e7eb;margin:20px 0;">
            <p style="color:#9ca3af;font-size:11px;text-align:center;">
                {company} — Evening Summary Report • Generated {timezone.now().strftime("%I:%M %p")} PKT
            </p>
            </div></div>
        ''')

        subject = f'🌙 {company} — Evening Summary — {today.strftime("%d %b %Y")}'
        html = ''.join(html_parts)

        success = _send_email(subject, html)
        if success:
            cs.last_report_email_at = timezone.now()
            cs.save(update_fields=['last_report_email_at'])
        return success

    except Exception as e:
        logger.error(f"Evening report failed: {e}", exc_info=True)
        return False


# ─── Legacy wrapper (backward compatibility) ────────────────────

def send_daily_report():
    """Legacy function — sends morning or evening report depending on time."""
    now = timezone.localtime()
    if now.hour < 12:
        return send_morning_report()
    else:
        return send_evening_report()


# ─── Backup functions (unchanged) ───────────────────────────────

def generate_backup_zip():
    """Generate full database backup as ZIP of CSVs.
    Format matches the import system exactly — same columns, same order.
    """
    from apps.parties.models import Party
    from apps.products.models import Product, Category, UnitOfMeasurement
    from apps.finance.models import (PaymentVoucher, ReceiptVoucher, Expense,
        BankAccount, CrossPartyAdjustment, Cheque)
    from apps.purchases.models import Purchase
    from apps.sales.models import Sale

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 1. Units (MUST be first for restore)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['abbreviation', 'name', 'name_urdu', 'conversion_to_base',
                     'unit_type', 'is_base_unit', 'sort_order'])
        for u in UnitOfMeasurement.objects.all().order_by('sort_order'):
            w.writerow([u.abbreviation, u.name, u.name_urdu, u.conversion_to_base,
                         u.unit_type, u.is_base_unit, u.sort_order])
        zf.writestr('01_units.csv', buf.getvalue())

        # 2. Categories
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['code', 'name', 'name_urdu', 'is_default'])
        for c in Category.objects.all().order_by('sort_order', 'name'):
            w.writerow([c.code, c.name, c.name_urdu, c.is_default])
        zf.writestr('02_categories.csv', buf.getvalue())

        # 3. Parties (current_balance, NOT opening_balance)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['code', 'name', 'name_urdu', 'type', 'phone', 'whatsapp', 'city', 'district',
                     'province', 'cnic', 'ntn_number', 'is_filer', 'current_balance',
                     'credit_limit', 'credit_days'])
        for p in Party.objects.filter(is_active=True).order_by('name'):
            w.writerow([p.code, p.name, p.name_urdu, p.party_type, p.phone_primary, p.whatsapp,
                        p.city, p.district, p.province, p.cnic, p.ntn_number, p.is_filer,
                        p.current_balance, p.credit_limit, p.credit_days])
        zf.writestr('03_parties.csv', buf.getvalue())

        # 4. Products
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['code', 'name', 'category', 'unit', 'current_stock',
                     'minimum_stock', 'source', 'status'])
        for p in Product.objects.filter(status='active').select_related('category', 'unit'):
            w.writerow([p.code, p.name, p.category.name if p.category else '',
                        p.unit.abbreviation if p.unit else '', p.current_stock,
                        p.minimum_stock, p.source, p.status])
        zf.writestr('04_products.csv', buf.getvalue())

        # 5. Bank Accounts
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['bank_name', 'account_number', 'account_type', 'branch', 'owner_type',
                     'opening_balance', 'current_balance'])
        for b in BankAccount.objects.all():
            w.writerow([b.bank_name, b.account_number, b.account_type, b.branch,
                        b.owner_type, b.opening_balance, b.current_balance])
        zf.writestr('05_bank_accounts.csv', buf.getvalue())

        # 6. Purchases
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['date', 'purchase_number', 'supplier', 'product', 'quantity', 'unit',
                     'rate', 'amount', 'subtotal', 'grand_total'])
        for p in Purchase.objects.filter(status='final').select_related('supplier').order_by('date'):
            for item in p.items.select_related('product', 'unit').all():
                w.writerow([p.date, p.purchase_number, p.supplier.name, item.product.name,
                            item.quantity, item.unit.abbreviation if item.unit else '',
                            item.rate, item.net_amount, p.subtotal, p.grand_total])
        zf.writestr('06_purchases.csv', buf.getvalue())

        # 7. Sales
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['date', 'invoice_number', 'customer', 'product', 'quantity', 'unit',
                     'rate', 'amount', 'subtotal', 'grand_total'])
        for s in Sale.objects.filter(status='final').select_related('customer').order_by('date'):
            for item in s.items.select_related('product', 'unit').all():
                w.writerow([s.date, s.invoice_number, s.customer.name, item.product.name,
                            item.quantity, item.unit.abbreviation if item.unit else '',
                            item.rate, item.net_amount, s.subtotal, s.grand_total])
        zf.writestr('07_sales.csv', buf.getvalue())

        # 8. Payments
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['date', 'voucher_number', 'party_name', 'amount', 'method',
                     'bank_name', 'narration'])
        for p in PaymentVoucher.objects.filter(status='final').select_related('party', 'bank_account').order_by('date'):
            w.writerow([p.date, p.voucher_number, p.party.name, p.amount, p.payment_method,
                        p.bank_account.bank_name if p.bank_account else '', p.narration])
        zf.writestr('08_payments.csv', buf.getvalue())

        # 9. Receipts
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['date', 'voucher_number', 'party_name', 'amount', 'method',
                     'bank_name', 'narration'])
        for r in ReceiptVoucher.objects.filter(status='final').select_related('party', 'bank_account').order_by('date'):
            w.writerow([r.date, r.voucher_number, r.party.name, r.amount, r.payment_method,
                        r.bank_account.bank_name if r.bank_account else '', r.narration])
        zf.writestr('09_receipts.csv', buf.getvalue())

        # 10. Expenses
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['date', 'category', 'amount', 'paid_to', 'method', 'description'])
        for e in Expense.objects.all().order_by('date'):
            w.writerow([e.date, e.category, e.amount, e.paid_to, e.payment_method, e.description])
        zf.writestr('10_expenses.csv', buf.getvalue())

        # 11. Cheques
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['cheque_number', 'date_on_cheque', 'party', 'amount', 'direction',
                     'bank_name', 'status', 'notes'])
        for ch in Cheque.objects.select_related('party').order_by('date_on_cheque'):
            w.writerow([ch.cheque_number, ch.date_on_cheque, ch.party.name, ch.amount,
                        ch.direction, ch.bank_name, ch.status, ch.notes])
        zf.writestr('11_cheques.csv', buf.getvalue())

        # 12. Adjustments
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['date', 'voucher_number', 'from_party', 'to_party', 'amount', 'narration'])
        for a in CrossPartyAdjustment.objects.filter(status='final').select_related('from_party', 'to_party').order_by('date'):
            w.writerow([a.date, a.voucher_number, a.from_party.name, a.to_party.name, a.amount, a.narration])
        zf.writestr('12_adjustments.csv', buf.getvalue())

        # RESTORE_ORDER.txt
        zf.writestr('RESTORE_ORDER.txt',
            'COTTON FACTORY — BACKUP RESTORE ORDER\n'
            '======================================\n\n'
            'Import CSV files in this EXACT order:\n\n'
            '  1. 01_units.csv        (Units)\n'
            '  2. 02_categories.csv   (Categories)\n'
            '  3. 03_parties.csv      (Parties)\n'
            '  4. 04_products.csv     (Products)\n'
            '  5. 05_bank_accounts.csv (Bank Accounts)\n'
            '  6. 06_purchases.csv    (Purchases)\n'
            '  7. 07_sales.csv        (Sales)\n'
            '  8. 08_payments.csv     (Payments)\n'
            '  9. 09_receipts.csv     (Receipts)\n'
            ' 10. 10_expenses.csv     (Expenses)\n'
            ' 11. 11_cheques.csv      (Cheques)\n\n'
            'OR: Just restore the .sqlite3 backup file directly.\n'
        )

    return zip_buffer.getvalue()


def send_backup_email():
    """Email the SQLite database file as backup attachment."""
    cs = _get_settings()
    if not cs or not cs.backup_enabled:
        return

    try:
        import os, shutil
        today = date.today()
        company = _esc(cs.company_name or 'Cotton Factory')
        db_path = str(settings.DATABASES['default']['NAME'])

        if not os.path.exists(db_path):
            logger.error(f"Database file not found: {db_path}")
            return False

        # Read the database file
        with open(db_path, 'rb') as f:
            db_data = f.read()

        # Also save local copy
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        local_path = os.path.join(backup_dir, f'backup_{today}.sqlite3')
        shutil.copy2(db_path, local_path)
        logger.info(f"Local backup saved: {local_path}")

        # Clean old backups — keep only last 10
        backups = sorted([
            os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
            if f.startswith('backup_') and f.endswith('.sqlite3')
        ])
        for old in backups[:-10]:
            os.remove(old)

        size_kb = len(db_data) // 1024
        subject = f'💾 {company} — Daily Backup — {today.strftime("%d %b %Y")} ({size_kb} KB)'
        html = f"""
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto;">
            <h2 style="color:#059669;">💾 Daily Database Backup</h2>
            <p><strong>Company:</strong> {company}</p>
            <p><strong>Date:</strong> {today.strftime("%d %B %Y")}</p>
            <p><strong>File:</strong> cotton_factory_{today}.sqlite3 ({size_kb} KB)</p>
            <hr style="border:1px solid #e5e7eb;">
            <p style="color:#6b7280;font-size:13px;">
                This is a complete SQLite database backup — it contains ALL your data
                including balances, stock, journals, and settings.<br>
                To restore: Settings → Backup & Restore → Upload this file.<br><br>
                یہ مکمل ڈیٹا بیس بیک اپ ہے — تمام بیلنس، اسٹاک اور سیٹنگز شامل ہیں۔<br>
                بحال کرنے کے لیے: ترتیبات → بیک اپ → یہ فائل اپلوڈ کریں۔
            </p>
        </div>
        """

        filename = f'cotton_factory_{today}.sqlite3'
        success = _send_email(subject, html, [(filename, db_data)])
        if success:
            cs.last_backup_email_at = timezone.now()
            cs.save(update_fields=['last_backup_email_at'])
        return success
    except Exception as e:
        logger.error(f"Backup email failed: {e}")
        return False
