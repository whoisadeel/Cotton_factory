"""
PDF Invoice/Voucher generation using WeasyPrint.
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

from apps.settings_app.models import CompanySettings

try:
    from weasyprint import HTML
    HAS_WEASYPRINT = True
except Exception:
    # WeasyPrint needs GTK/Pango native libraries.
    # On Windows: install GTK3 from https://github.com/nickvdyck/weasyprint-win/releases
    # or use MSYS2: pacman -S mingw-w64-x86_64-pango
    HAS_WEASYPRINT = False


def _pdf_response(html_string, filename):
    """Convert HTML string to PDF. Falls back to printable HTML if WeasyPrint not available."""
    if not HAS_WEASYPRINT:
        # Render as print-friendly HTML page with auto-print dialog
        wrapper = (
            '<!DOCTYPE html><html><head><meta charset="UTF-8">'
            '<title>' + filename + '</title>'
            '<style>'
            'body{font-family:system-ui,sans-serif;margin:0;padding:20px;color:#1e293b;}'
            '@media print{.no-print{display:none !important;}body{padding:0;}}'
            '</style></head><body>'
            '<div class="no-print" style="text-align:center;margin-bottom:20px;padding:12px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;">'
            '<span style="font-size:14px;color:#065f46;font-weight:600;">Press Ctrl+P to print or save as PDF — پرنٹ کے لیے Ctrl+P دبائیں</span>'
            '&nbsp;&nbsp;<button onclick="window.print()" style="padding:8px 20px;background:#059669;color:white;border:none;border-radius:8px;font-weight:700;cursor:pointer;">🖨 Print</button>'
            '&nbsp;<a href="javascript:history.back()" style="padding:8px 16px;background:#f3f4f6;color:#374151;border-radius:8px;text-decoration:none;font-weight:600;">← Back</a>'
            '</div>'
            + html_string +
            '<script>window.onload=function(){window.print();}</script>'
            '</body></html>'
        )
        return HttpResponse(wrapper, content_type='text/html')
    pdf = HTML(string=html_string).write_pdf()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
def sale_invoice_pdf(request, pk):
    """Generate PDF invoice for a sale."""
    from apps.sales.models import Sale
    sale = get_object_or_404(Sale, pk=pk)
    company = CompanySettings.get_settings()
    items = sale.items.select_related('product', 'unit').all()

    html = render_to_string('invoices/sale_invoice.html', {
        'sale': sale, 'company': company, 'items': items,
    })
    return _pdf_response(html, f'Invoice_{sale.invoice_number}.pdf')


@login_required
def purchase_invoice_pdf(request, pk):
    """Generate PDF voucher for a purchase."""
    from apps.purchases.models import Purchase
    purchase = get_object_or_404(Purchase, pk=pk)
    company = CompanySettings.get_settings()
    items = purchase.items.select_related('product', 'unit').all()

    html = render_to_string('invoices/purchase_invoice.html', {
        'purchase': purchase, 'company': company, 'items': items,
    })
    return _pdf_response(html, f'Purchase_{purchase.purchase_number}.pdf')


@login_required
def payment_voucher_pdf(request, pk):
    """Generate PDF for payment voucher."""
    from apps.finance.models import PaymentVoucher
    voucher = get_object_or_404(PaymentVoucher, pk=pk)
    company = CompanySettings.get_settings()

    html = render_to_string('invoices/payment_receipt.html', {
        'voucher': voucher, 'company': company,
        'title': 'PAYMENT VOUCHER', 'title_ur': 'ادائیگی واؤچر',
        'party_label': 'Paid To — کسے ادائیگی', 'amount_label': 'Amount Paid — ادا شدہ رقم',
        'receiver_label': 'Received By — وصول کنندہ',
        'color': '#dc2626',
    })
    return _pdf_response(html, f'Payment_{voucher.voucher_number}.pdf')


@login_required
def receipt_voucher_pdf(request, pk):
    """Generate PDF for receipt voucher."""
    from apps.finance.models import ReceiptVoucher
    voucher = get_object_or_404(ReceiptVoucher, pk=pk)
    company = CompanySettings.get_settings()

    html = render_to_string('invoices/payment_receipt.html', {
        'voucher': voucher, 'company': company,
        'title': 'RECEIPT VOUCHER', 'title_ur': 'وصولی واؤچر',
        'party_label': 'Received From — کس سے وصولی', 'amount_label': 'Amount Received — وصول شدہ رقم',
        'receiver_label': 'Paid By — ادا کنندہ',
        'color': '#059669',
    })
    return _pdf_response(html, f'Receipt_{voucher.voucher_number}.pdf')


@login_required
def party_statement_pdf(request, pk):
    """Generate PDF statement for a party."""
    from apps.parties.models import Party
    from apps.purchases.models import Purchase
    from apps.sales.models import Sale
    from apps.finance.models import PaymentVoucher, ReceiptVoucher
    from apps.reports.views import _dates

    party = get_object_or_404(Party, pk=pk)
    company = CompanySettings.get_settings()
    start, end, _ = _dates(request)

    # Build ledger
    ledger = []
    for p in Purchase.objects.filter(supplier=party, date__range=[start, end], status='final'):
        ledger.append({'date': p.date, 'type': 'Purchase', 'ref': p.purchase_number, 'debit': 0, 'credit': p.grand_total})
    for s in Sale.objects.filter(customer=party, date__range=[start, end], status='final'):
        ledger.append({'date': s.date, 'type': 'Sale', 'ref': s.invoice_number, 'debit': s.grand_total, 'credit': 0})
    for v in PaymentVoucher.objects.filter(party=party, date__range=[start, end], status='final'):
        ledger.append({'date': v.date, 'type': 'Payment', 'ref': v.voucher_number, 'debit': v.amount, 'credit': 0})
    for v in ReceiptVoucher.objects.filter(party=party, date__range=[start, end], status='final'):
        ledger.append({'date': v.date, 'type': 'Receipt', 'ref': v.voucher_number, 'debit': 0, 'credit': v.amount})
    ledger.sort(key=lambda x: x['date'])

    balance = party.opening_balance if party.opening_balance_type == 'debit' else -party.opening_balance
    for entry in ledger:
        balance += entry['debit'] - entry['credit']
        entry['balance'] = balance

    html = render_to_string('invoices/party_statement.html', {
        'party': party, 'company': company, 'entries': ledger,
        'start': start, 'end': end,
    })
    return _pdf_response(html, f'Statement_{party.code}_{start}_{end}.pdf')
