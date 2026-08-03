"""
Auto-Journal Entry creation — called when purchases, sales, payments,
receipts, and expenses are finalized.

Every business transaction creates a proper double-entry journal automatically.
"""
from decimal import Decimal
from .models import Account, JournalEntry, JournalLine


def _get_account(code):
    """Get account by code, or None if not found."""
    try:
        return Account.objects.get(code=code)
    except Account.DoesNotExist:
        return None


def _create_journal(date, entry_type, narration, lines, user=None,
                    purchase=None, sale=None, payment=None, receipt=None):
    """Create a balanced journal entry with given lines.
    lines = [{'account_code': 'XXXX', 'debit': Decimal, 'credit': Decimal}, ...]
    """
    # Resolve accounts
    resolved = []
    for line in lines:
        acct = _get_account(line['account_code'])
        if not acct:
            # Skip lines where account doesn't exist
            continue
        dr = line.get('debit', Decimal('0')) or Decimal('0')
        cr = line.get('credit', Decimal('0')) or Decimal('0')
        if dr > 0 or cr > 0:
            resolved.append({'account': acct, 'debit': dr, 'credit': cr})

    if not resolved:
        return None

    je = JournalEntry(
        entry_number=JournalEntry.generate_number(),
        date=date,
        entry_type=entry_type,
        narration=narration,
        purchase=purchase,
        sale=sale,
        payment=payment,
        receipt=receipt,
        created_by=user,
    )
    je.save()

    for line in resolved:
        JournalLine.objects.create(
            journal=je,
            account=line['account'],
            debit=line['debit'],
            credit=line['credit'],
        )

    # Post if balanced
    if je.is_balanced:
        je.post()

    return je


def journal_for_purchase(purchase):
    """
    Purchase finalized — simple balanced entry:
      Dr: 5001 Purchases - Raw Cotton   (grand_total — total cost of purchase)
      Cr: 2001 Accounts Payable         (grand_total — what we owe supplier)
    Grand total already includes all charges, taxes, minus discounts.
    """
    lines = []
    gt = purchase.grand_total or Decimal('0')

    if gt > 0:
        lines.append({'account_code': '5001', 'debit': gt, 'credit': Decimal('0')})
        lines.append({'account_code': '2001', 'debit': Decimal('0'), 'credit': gt})

    return _create_journal(
        date=purchase.date,
        entry_type='purchase',
        narration=f'Purchase {purchase.purchase_number} from {purchase.supplier.name}',
        lines=lines,
        user=purchase.created_by,
        purchase=purchase,
    )


def journal_for_sale(sale):
    """
    Sale finalized:
      Dr: 1003 Accounts Receivable   (grand_total — what customer owes us)
      Cr: 4001 Sales Revenue         (grand_total — our revenue)
    Simple: the grand_total already includes all charges/taxes/discounts.
    """
    lines = []
    gt = sale.grand_total or Decimal('0')

    if gt > 0:
        lines.append({'account_code': '1003', 'debit': gt, 'credit': Decimal('0')})
        lines.append({'account_code': '4001', 'debit': Decimal('0'), 'credit': gt})

    return _create_journal(
        date=sale.date,
        entry_type='sale',
        narration=f'Sale {sale.invoice_number} to {sale.customer.name}',
        lines=lines,
        user=sale.created_by,
        sale=sale,
    )


def journal_for_payment(payment):
    """
    Payment made (we pay supplier/party):
      Dr: 2001 Accounts Payable   (clearing what we owe)
      Cr: 1001 Cash in Hand       (if cash)
      Cr: 1002 Bank Accounts      (if bank/cheque)
    """
    if payment.payment_method in ('bank', 'cheque', 'online'):
        cr_code = '1002'
    else:
        cr_code = '1001'

    lines = [
        {'account_code': '2001', 'debit': payment.amount, 'credit': Decimal('0')},
        {'account_code': cr_code, 'debit': Decimal('0'), 'credit': payment.amount},
    ]

    return _create_journal(
        date=payment.date,
        entry_type='payment',
        narration=f'Payment {payment.voucher_number} to {payment.party.name}',
        lines=lines,
        user=getattr(payment, 'created_by', None),
        payment=payment,
    )


def journal_for_receipt(receipt):
    """
    Receipt received (customer pays us):
      Dr: 1001 Cash in Hand / 1002 Bank   (money in)
      Cr: 1003 Accounts Receivable        (clearing what they owe)
    """
    if receipt.payment_method in ('bank', 'cheque', 'online'):
        dr_code = '1002'
    else:
        dr_code = '1001'

    lines = [
        {'account_code': dr_code, 'debit': receipt.amount, 'credit': Decimal('0')},
        {'account_code': '1003', 'debit': Decimal('0'), 'credit': receipt.amount},
    ]

    return _create_journal(
        date=receipt.date,
        entry_type='receipt',
        narration=f'Receipt {receipt.voucher_number} from {receipt.party.name}',
        lines=lines,
        user=getattr(receipt, 'created_by', None),
        receipt=receipt,
    )


def journal_for_cross_party_adjustment(adjustment):
    """
    Cross-party adjustment — no cash moves through us.

    Direction: debtor_pays_creditor
      from_party (debtor) pays to_party (creditor) directly.
      Dr: 2001 Accounts Payable (clearing what we owe to_party)
      Cr: 1003 Accounts Receivable (clearing what from_party owes us)

    Direction: creditor_settles_debtor
      from_party (creditor) collects from to_party (debtor).
      Dr: 2001 Accounts Payable (clearing what we owe from_party)
      Cr: 1003 Accounts Receivable (clearing what to_party owes us)
    """
    amt = adjustment.amount or Decimal('0')
    if amt <= 0:
        return None

    if adjustment.direction == 'debtor_pays_creditor':
        lines = [
            {'account_code': '2001', 'debit': amt, 'credit': Decimal('0')},
            {'account_code': '1003', 'debit': Decimal('0'), 'credit': amt},
        ]
        narration = (f'Cross-Party Adjustment {adjustment.voucher_number}: '
                     f'{adjustment.from_party.name} paid {adjustment.to_party.name} directly')
    else:
        lines = [
            {'account_code': '2001', 'debit': amt, 'credit': Decimal('0')},
            {'account_code': '1003', 'debit': Decimal('0'), 'credit': amt},
        ]
        narration = (f'Cross-Party Adjustment {adjustment.voucher_number}: '
                     f'{adjustment.from_party.name} collected from {adjustment.to_party.name}')

    return _create_journal(
        date=adjustment.date,
        entry_type='adjustment',
        narration=narration,
        lines=lines,
        user=getattr(adjustment, 'created_by', None),
    )


def journal_for_expense(expense):
    """
    Expense recorded:
      Dr: 6001-6016 (appropriate expense account)
      Cr: 1001 Cash / 1002 Bank
    """
    # Map expense category to account code
    category_map = {
        'electricity': '6001', 'gas_fuel': '6002', 'diesel': '6003',
        'salary': '6004', 'daily_labour': '6005', 'repair': '6006',
        'spare_parts': '6007', 'transport': '6008', 'office': '6009',
        'communication': '6010', 'rent': '6011', 'insurance': '6012',
        'legal': '6013', 'govt_fees': '6014', 'entertainment': '6015',
        'misc': '6016',
    }
    dr_code = category_map.get(expense.category, '6016')

    if expense.payment_method in ('bank', 'cheque', 'online'):
        cr_code = '1002'
    else:
        cr_code = '1001'

    lines = [
        {'account_code': dr_code, 'debit': expense.amount, 'credit': Decimal('0')},
        {'account_code': cr_code, 'debit': Decimal('0'), 'credit': expense.amount},
    ]

    return _create_journal(
        date=expense.date,
        entry_type='expense',
        narration=f'Expense: {expense.description or expense.get_category_display()}',
        lines=lines,
    )
