from decimal import Decimal
"""
Finance Views — Payment, Receipt, Expense with proper form validation.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from apps.authentication.models import AuditLog
from .models import PaymentVoucher, ReceiptVoucher, Expense, CrossPartyAdjustment
from .forms import PaymentForm, ReceiptForm, ExpenseForm, CrossPartyAdjustmentForm


@login_required
def payment_list(request):
    from django.core.paginator import Paginator
    from django.db.models import Sum
    from apps.parties.models import Party
    vouchers = PaymentVoucher.objects.select_related('party', 'bank_account').all()
    search = request.GET.get('search', '')
    if search:
        vouchers = vouchers.filter(Q(voucher_number__icontains=search) | Q(party__name__icontains=search))
    status = request.GET.get('status')
    if status:
        vouchers = vouchers.filter(status=status)
    method = request.GET.get('method')
    if method:
        vouchers = vouchers.filter(payment_method=method)
    party_id = request.GET.get('party')
    if party_id:
        vouchers = vouchers.filter(party_id=party_id)
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    if date_from:
        vouchers = vouchers.filter(date__gte=date_from)
    if date_to:
        vouchers = vouchers.filter(date__lte=date_to)
    # Totals for the filtered set
    totals = vouchers.filter(status='final').aggregate(
        total=Sum('amount'),
    )
    paginator = Paginator(vouchers, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    parties = Party.objects.filter(
        is_active=True, party_type__in=['supplier', 'both', 'broker', 'transporter', 'employee', 'other']
    ).order_by('name')
    return render(request, 'finance/payment_list.html', {
        'vouchers': page_obj, 'search': search, 'page_obj': page_obj,
        'selected_status': status or '', 'selected_method': method or '',
        'selected_party': party_id or '',
        'show_status': True, 'filter_from': date_from, 'filter_to': date_to,
        'parties': parties,
        'total_amount': totals['total'] or 0,
        'total_count': vouchers.filter(status='final').count(),
    })


@login_required
def payment_create(request):
    if request.method == 'POST':
        form = PaymentForm(request.POST, request.FILES)
        if form.is_valid():
            voucher = form.save(commit=False)
            voucher.created_by = request.user
            voucher.save()
            # Always finalize immediately — no draft confusion
            voucher.finalize()
            AuditLog.log(user=request.user, action='CREATE', model_name='PaymentVoucher',
                         object_id=voucher.pk, object_repr=str(voucher), request=request,
                         description=f'Payment: {voucher.voucher_number} ₨{voucher.amount:,.0f} to {voucher.party.name}')
            messages.success(request, f'✓ Payment saved — ₨{voucher.amount:,.0f} to {voucher.party.name}')
            return redirect('finance:payment_detail', pk=voucher.pk)
    else:
        from django.utils import timezone
        initial = {'date': timezone.now().date()}
        # Pre-fill from query params (from purchase detail quick-pay)
        if request.GET.get('party'):
            initial['party'] = request.GET['party']
        if request.GET.get('amount'):
            initial['amount'] = request.GET['amount']
        form = PaymentForm(initial=initial)
    # Duplicate detection
    dup_warning = None
    if request.method == 'POST' and form.is_valid():
        pass  # Already redirected
    return render(request, 'finance/payment_form.html', {
        'form': form, 'title': 'New Payment — نئی ادائیگی',
        'back_url': '/finance/payments/',
        'prefill_ref': request.GET.get('ref', ''),
    })


@login_required
def payment_detail(request, pk):
    voucher = get_object_or_404(PaymentVoucher.objects.select_related('party', 'bank_account'), pk=pk)
    # Duplicate detection
    dup_warning = None
    if voucher.status == 'final':
        dupes = PaymentVoucher.objects.filter(
            party=voucher.party, amount=voucher.amount, date=voucher.date, status='final'
        ).exclude(pk=voucher.pk)
        if dupes.exists():
            dup_nums = ', '.join(d.voucher_number for d in dupes[:3])
            dup_warning = (f'Similar payment(s) found — same party, amount, date: {dup_nums}. '
                          f'اسی پارٹی، رقم اور تاریخ کی ادائیگی پہلے سے موجود ہے۔')
    return render(request, 'finance/payment_detail.html', {
        'v': voucher, 'title': f'Payment {voucher.voucher_number}',
        'duplicate_warning': dup_warning,
    })


@login_required
def payment_edit(request, pk):
    voucher = get_object_or_404(PaymentVoucher, pk=pk)
    if voucher.status == 'void':
        messages.error(request, 'Voided payments cannot be edited.')
        return redirect('finance:payment_detail', pk=pk)
    if request.method == 'POST':
        old_amount = voucher.amount
        old_party = voucher.party_id
        form = PaymentForm(request.POST, request.FILES, instance=voucher)
        if form.is_valid():
            v = form.save()
            changes = []
            if old_amount != v.amount:
                changes.append(f'amount: {old_amount}→{v.amount}')
            if old_party != v.party_id:
                changes.append(f'party changed')
            if voucher.status == 'draft' and request.POST.get('action') == 'finalize':
                v.finalize()
                AuditLog.log(user=request.user, action='UPDATE', model_name='PaymentVoucher',
                             object_id=v.pk, object_repr=str(v), request=request)
                messages.success(request, f'Payment {v.voucher_number} finalized ✓')
            else:
                AuditLog.log(user=request.user, action='UPDATE', model_name='PaymentVoucher',
                             object_id=v.pk, object_repr=str(v), request=request,
                             description=f'Payment edited: {", ".join(changes) or "minor changes"}')
                messages.success(request, 'Payment updated — ادائیگی اپ ڈیٹ ہو گئی')
            return redirect('finance:payment_detail', pk=v.pk)
    else:
        form = PaymentForm(instance=voucher)
    return render(request, 'finance/payment_form.html', {
        'form': form, 'title': f'Edit Payment — {voucher.voucher_number}',
        'editing': True, 'voucher': voucher,
        'back_url': f'/finance/payments/{pk}/',
        'submit_label': 'Update', 'submit_label_ur': 'اپ ڈیٹ',
    })


@login_required
def receipt_list(request):
    from django.core.paginator import Paginator
    from django.db.models import Sum
    from apps.parties.models import Party
    vouchers = ReceiptVoucher.objects.select_related('party', 'bank_account').all()
    search = request.GET.get('search', '')
    if search:
        vouchers = vouchers.filter(Q(voucher_number__icontains=search) | Q(party__name__icontains=search))
    status = request.GET.get('status')
    if status:
        vouchers = vouchers.filter(status=status)
    method = request.GET.get('method')
    if method:
        vouchers = vouchers.filter(payment_method=method)
    party_id = request.GET.get('party')
    if party_id:
        vouchers = vouchers.filter(party_id=party_id)
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    if date_from:
        vouchers = vouchers.filter(date__gte=date_from)
    if date_to:
        vouchers = vouchers.filter(date__lte=date_to)
    totals = vouchers.filter(status='final').aggregate(total=Sum('amount'))
    paginator = Paginator(vouchers, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    parties = Party.objects.filter(
        is_active=True, party_type__in=['customer', 'both', 'other']
    ).order_by('name')
    return render(request, 'finance/receipt_list.html', {
        'vouchers': page_obj, 'search': search, 'page_obj': page_obj,
        'selected_status': status or '', 'selected_method': method or '',
        'selected_party': party_id or '',
        'show_status': True, 'filter_from': date_from, 'filter_to': date_to,
        'parties': parties,
        'total_amount': totals['total'] or 0,
        'total_count': vouchers.filter(status='final').count(),
    })


@login_required
def receipt_create(request):
    if request.method == 'POST':
        form = ReceiptForm(request.POST, request.FILES)
        if form.is_valid():
            voucher = form.save(commit=False)
            voucher.created_by = request.user
            voucher.save()
            voucher.finalize()
            AuditLog.log(user=request.user, action='CREATE', model_name='ReceiptVoucher',
                         object_id=voucher.pk, object_repr=str(voucher), request=request,
                         description=f'Receipt: {voucher.voucher_number} ₨{voucher.amount:,.0f} from {voucher.party.name}')

            # Handle redirect_to_party — auto-create payment to another party
            redirect_party = form.cleaned_data.get('redirect_to_party')
            if redirect_party and redirect_party != voucher.party:
                we_owe_them = form.cleaned_data.get('we_owe_them', True)
                pmt = PaymentVoucher(
                    date=voucher.date,
                    party=redirect_party,
                    amount=voucher.amount,
                    payment_method=voucher.payment_method,  # Same method as receipt (cash/bank/cheque/online)
                    bank_account=voucher.bank_account,       # Same bank if bank/cheque/online
                    narration=f'Redirected from receipt {voucher.voucher_number} ({voucher.party.name} → {redirect_party.name}). {voucher.narration}'.strip(),
                    created_by=request.user,
                )
                pmt.save()
                if we_owe_them:
                    # Adjust to_party balance — normal finalize
                    pmt.finalize()  # Adjusts balance + bank + journal
                else:
                    # Don't adjust party balance — just record the payment
                    pmt.status = 'final'
                    pmt.save()
                    if pmt.bank_account and pmt.payment_method in ('bank', 'cheque', 'online'):
                        pmt.bank_account.current_balance -= pmt.amount
                        pmt.bank_account.save(update_fields=['current_balance'])
                    try:
                        from apps.accounting.auto_journal import journal_for_payment
                        journal_for_payment(pmt)
                    except Exception:
                        pass
                AuditLog.log(user=request.user, action='CREATE', model_name='PaymentVoucher',
                             object_id=pmt.pk, object_repr=str(pmt), request=request,
                             description=f'Auto-payment from receipt redirect: {pmt.voucher_number} ₨{pmt.amount:,.0f} to {redirect_party.name}')
                owe_label = 'settling debt' if we_owe_them else 'not a debt'
                messages.success(request,
                    f'✓ Receipt ₨{voucher.amount:,.0f} from {voucher.party.name} '
                    f'→ Payment ₨{pmt.amount:,.0f} to {redirect_party.name} ({owe_label})')
            else:
                messages.success(request, f'✓ Receipt saved — ₨{voucher.amount:,.0f} from {voucher.party.name}')

            return redirect('finance:receipt_detail', pk=voucher.pk)
    else:
        from django.utils import timezone
        initial = {'date': timezone.now().date()}
        if request.GET.get('party'):
            initial['party'] = request.GET['party']
        if request.GET.get('amount'):
            initial['amount'] = request.GET['amount']
        form = ReceiptForm(initial=initial)
    return render(request, 'finance/receipt_form.html', {
        'form': form, 'title': 'New Receipt — نئی وصولی',
        'back_url': '/finance/receipts/',
        'prefill_ref': request.GET.get('ref', ''),
    })


@login_required
def receipt_detail(request, pk):
    voucher = get_object_or_404(ReceiptVoucher.objects.select_related('party', 'bank_account'), pk=pk)
    dup_warning = None
    if voucher.status == 'final':
        dupes = ReceiptVoucher.objects.filter(
            party=voucher.party, amount=voucher.amount, date=voucher.date, status='final'
        ).exclude(pk=voucher.pk)
        if dupes.exists():
            dup_nums = ', '.join(d.voucher_number for d in dupes[:3])
            dup_warning = (f'Similar receipt(s) found — same party, amount, date: {dup_nums}. '
                          f'اسی پارٹی، رقم اور تاریخ کی وصولی پہلے سے موجود ہے۔')
    return render(request, 'finance/receipt_detail.html', {
        'v': voucher, 'title': f'Receipt {voucher.voucher_number}',
        'duplicate_warning': dup_warning,
    })


@login_required
def receipt_edit(request, pk):
    voucher = get_object_or_404(ReceiptVoucher, pk=pk)
    if voucher.status == 'void':
        messages.error(request, 'Voided receipts cannot be edited.')
        return redirect('finance:receipt_detail', pk=pk)
    if request.method == 'POST':
        old_amount = voucher.amount
        form = ReceiptForm(request.POST, request.FILES, instance=voucher)
        if form.is_valid():
            v = form.save()
            changes = []
            if old_amount != v.amount:
                changes.append(f'amount: {old_amount}→{v.amount}')
            if voucher.status == 'draft' and request.POST.get('action') == 'finalize':
                v.finalize()
                AuditLog.log(user=request.user, action='UPDATE', model_name='ReceiptVoucher',
                             object_id=v.pk, object_repr=str(v), request=request)
                messages.success(request, f'Receipt {v.voucher_number} finalized ✓')
            else:
                AuditLog.log(user=request.user, action='UPDATE', model_name='ReceiptVoucher',
                             object_id=v.pk, object_repr=str(v), request=request,
                             description=f'Receipt edited: {", ".join(changes) or "minor changes"}')
                messages.success(request, 'Receipt updated — وصولی اپ ڈیٹ ہو گئی')
            return redirect('finance:receipt_detail', pk=v.pk)
    else:
        form = ReceiptForm(instance=voucher)
    return render(request, 'finance/receipt_form.html', {
        'form': form, 'title': f'Edit Receipt — {voucher.voucher_number}',
        'editing': True, 'voucher': voucher,
        'back_url': f'/finance/receipts/{pk}/',
        'submit_label': 'Update', 'submit_label_ur': 'اپ ڈیٹ',
    })


@login_required
def expense_list(request):
    from django.core.paginator import Paginator
    from django.db.models import Sum
    expenses = Expense.objects.all()
    search = request.GET.get('search', '')
    if search:
        expenses = expenses.filter(
            Q(paid_to__icontains=search) | Q(description__icontains=search)
        )
    category = request.GET.get('category')
    if category:
        expenses = expenses.filter(category=category)
    method = request.GET.get('method')
    if method:
        expenses = expenses.filter(payment_method=method)
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    if date_from:
        expenses = expenses.filter(date__gte=date_from)
    if date_to:
        expenses = expenses.filter(date__lte=date_to)
    totals = expenses.aggregate(total=Sum('amount'))
    paginator = Paginator(expenses, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'finance/expense_list.html', {
        'expenses': page_obj, 'search': search, 'page_obj': page_obj,
        'selected_category': category or '', 'category_choices': Expense.CATEGORY_CHOICES,
        'selected_method': method or '',
        'filter_from': date_from, 'filter_to': date_to,
        'total_amount': totals['total'] or 0,
        'total_count': expenses.count(),
    })


@login_required
def expense_create(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.created_by = request.user
            expense.save()
            # Auto-journal
            try:
                from apps.accounting.auto_journal import journal_for_expense
                journal_for_expense(expense)
            except Exception:
                pass
            AuditLog.log(user=request.user, action='CREATE', model_name='Expense',
                         object_id=expense.pk, object_repr=str(expense), request=request,
                         description=f'Expense: {expense.get_category_display()} ₨{expense.amount:,.0f}')
            messages.success(request, f'Expense ₨{expense.amount:,.0f} recorded.')
            return redirect('finance:expense_list')
    else:
        from django.utils import timezone
        form = ExpenseForm(initial={'date': timezone.now().date()})
    return render(request, 'finance/expense_form.html', {'form': form, 'title': 'Add Expense — خرچہ', 'back_url': '/finance/expenses/', 'submit_label': 'Save', 'submit_label_ur': 'محفوظ کریں'})


# ─── BANK ACCOUNTS ────────────────────────────
@login_required
def bank_account_list(request):
    from django.db.models import Sum
    from .models import BankAccount
    accounts = BankAccount.objects.select_related('party').all()
    owner_filter = request.GET.get('owner', '')
    if owner_filter:
        accounts = accounts.filter(owner_type=owner_filter)
    search = request.GET.get('search', '')
    if search:
        accounts = accounts.filter(
            Q(bank_name__icontains=search) | Q(account_number__icontains=search) |
            Q(branch__icontains=search) | Q(party__name__icontains=search)
        )
    own_accounts = BankAccount.objects.filter(owner_type='own', is_active=True)
    party_accounts = BankAccount.objects.filter(owner_type='party', is_active=True)
    own_total = own_accounts.aggregate(t=Sum('current_balance'))['t'] or 0
    return render(request, 'finance/bank_account_list.html', {
        'accounts': accounts,
        'own_accounts': own_accounts.select_related('party'),
        'party_accounts': party_accounts.select_related('party'),
        'own_total': own_total,
        'selected_owner': owner_filter,
        'search': search,
    })


@login_required
def bank_account_create(request):
    from .models import BankAccount
    if request.method == 'POST':
        bank_name = (request.POST.get('bank_name') or '').strip()
        account_number = (request.POST.get('account_number') or '').strip()
        if not bank_name:
            messages.error(request, 'Bank name is required — بینک کا نام ضروری ہے')
            return render(request, 'finance/bank_account_form.html', {
                'title': 'Add Bank Account — بینک اکاؤنٹ', 'bank_choices': BankAccount.BANK_CHOICES
            })
        if not account_number:
            messages.error(request, 'Account number is required — اکاؤنٹ نمبر ضروری ہے')
            return render(request, 'finance/bank_account_form.html', {
                'title': 'Add Bank Account — بینک اکاؤنٹ', 'bank_choices': BankAccount.BANK_CHOICES
            })
        try:
            opening_bal = Decimal(request.POST.get('opening_balance') or '0')
            if opening_bal < 0:
                messages.error(request, 'Opening balance cannot be negative — رقم منفی نہیں ہو سکتی')
                return render(request, 'finance/bank_account_form.html', {
                    'title': 'Add Bank Account — بینک اکاؤنٹ', 'bank_choices': BankAccount.BANK_CHOICES
                })
        except Exception:
            opening_bal = Decimal('0')

        ba = BankAccount.objects.create(
            owner_type=request.POST.get('owner_type', 'own'),
            party_id=request.POST.get('party') or None,
            bank_code=request.POST.get('bank_code', 'other'),
            bank_name=bank_name,
            account_number=account_number,
            account_type=request.POST.get('account_type', 'current'),
            branch=request.POST.get('branch', ''),
            opening_balance=opening_bal,
            current_balance=opening_bal,
        )
        AuditLog.log(user=request.user, action='CREATE', model_name='BankAccount',
                     object_id=ba.pk, object_repr=str(ba), request=request,
                     description=f'Bank account: {ba.bank_name} — {ba.account_number}')
        messages.success(request, f'Bank account added — بینک اکاؤنٹ شامل ہو گیا')
        return redirect('finance:bank_account_list')
    from apps.parties.models import Party
    return render(request, 'finance/bank_account_form.html', {
        'title': 'Add Bank Account — بینک اکاؤنٹ', 'bank_choices': BankAccount.BANK_CHOICES,
        'parties': Party.objects.filter(is_active=True).order_by('name'),
    })


# ─── BANK LEDGER ────────────────────────────────────
@login_required
def bank_ledger(request, pk):
    """Per-bank transaction ledger with running balance — like a passbook."""
    from .models import BankAccount
    bank = get_object_or_404(BankAccount, pk=pk)

    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    from datetime import date
    today = date.today()
    try:
        start = date.fromisoformat(date_from) if date_from else today.replace(day=1)
    except (ValueError, TypeError):
        start = today.replace(day=1)
    try:
        end = date.fromisoformat(date_to) if date_to else today
    except (ValueError, TypeError):
        end = today

    entries = []

    # Payments OUT from this bank
    for p in PaymentVoucher.objects.filter(
        bank_account=bank, status='final', date__range=[start, end]
    ).select_related('party').order_by('date', 'created_at'):
        entries.append({
            'date': p.date, 'ref': p.voucher_number,
            'party': p.party.name, 'narration': p.narration or f'Payment to {p.party.name}',
            'debit': 0, 'credit': p.amount,
            'url': f'/finance/payments/{p.pk}/',
            'sort_key': (p.date, p.created_at),
        })

    # Receipts IN to this bank
    for r in ReceiptVoucher.objects.filter(
        bank_account=bank, status='final', date__range=[start, end]
    ).select_related('party').order_by('date', 'created_at'):
        entries.append({
            'date': r.date, 'ref': r.voucher_number,
            'party': r.party.name, 'narration': r.narration or f'Receipt from {r.party.name}',
            'debit': r.amount, 'credit': 0,
            'url': f'/finance/receipts/{r.pk}/',
            'sort_key': (r.date, r.created_at),
        })

    entries.sort(key=lambda x: x['sort_key'])

    # Calculate running balance
    running = bank.opening_balance
    # Add all transactions before start date to get opening
    for p in PaymentVoucher.objects.filter(bank_account=bank, status='final', date__lt=start):
        running -= p.amount
    for r in ReceiptVoucher.objects.filter(bank_account=bank, status='final', date__lt=start):
        running += r.amount

    opening_for_period = running
    for e in entries:
        running = running + e['debit'] - e['credit']
        e['balance'] = running

    total_in = sum(e['debit'] for e in entries)
    total_out = sum(e['credit'] for e in entries)

    return render(request, 'finance/bank_ledger.html', {
        'bank': bank, 'entries': entries,
        'opening_balance': opening_for_period,
        'closing_balance': running,
        'total_in': total_in, 'total_out': total_out,
        'filter_from': start, 'filter_to': end,
    })


# ─── CHEQUE MANAGEMENT ────────────────────────────
@login_required
def cheque_list(request):
    from django.core.paginator import Paginator
    from django.db.models import Sum
    from apps.parties.models import Party
    from .models import Cheque
    cheques = Cheque.objects.select_related('party', 'bank_account').all()
    search = request.GET.get('search', '')
    if search:
        cheques = cheques.filter(Q(cheque_number__icontains=search) | Q(party__name__icontains=search))
    direction = request.GET.get('direction')
    status_f = request.GET.get('status')
    party_id = request.GET.get('party')
    if direction:
        cheques = cheques.filter(direction=direction)
    if status_f:
        cheques = cheques.filter(status=status_f)
    if party_id:
        cheques = cheques.filter(party_id=party_id)
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    if date_from:
        cheques = cheques.filter(date_on_cheque__gte=date_from)
    if date_to:
        cheques = cheques.filter(date_on_cheque__lte=date_to)
    totals = cheques.exclude(status__in=['bounced', 'cancelled']).aggregate(total=Sum('amount'))
    paginator = Paginator(cheques, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    parties = Party.objects.filter(is_active=True).order_by('name')
    return render(request, 'finance/cheque_list.html', {
        'cheques': page_obj, 'page_obj': page_obj, 'search': search,
        'selected_direction': direction or '', 'selected_status': status_f or '',
        'selected_party': party_id or '',
        'filter_from': date_from, 'filter_to': date_to,
        'parties': parties,
        'total_amount': totals['total'] or 0,
        'total_count': cheques.exclude(status__in=['bounced', 'cancelled']).count(),
        'all_count': cheques.count(),
    })


@login_required
def cheque_create(request):
    from .models import Cheque, BankAccount
    from apps.parties.models import Party
    if request.method == 'POST':
        cheque_number = request.POST.get('cheque_number', '').strip()
        date_on_cheque = request.POST.get('date_on_cheque', '')
        party_id = request.POST.get('party', '')
        amount = request.POST.get('amount', '')
        if not cheque_number or not date_on_cheque or not party_id or not amount:
            messages.error(request, 'Please fill all required fields — تمام ضروری فیلڈز بھریں')
            return render(request, 'finance/cheque_form.html', {
                'title': 'Record Cheque — چیک',
                'parties': Party.objects.filter(is_active=True),
                'bank_accounts': BankAccount.objects.filter(is_active=True),
            })
        try:
            amount_val = Decimal(amount)
            if amount_val <= 0:
                messages.error(request, 'Amount must be greater than zero — رقم صفر سے زیادہ ہونی چاہیے')
                return render(request, 'finance/cheque_form.html', {
                    'title': 'Record Cheque — چیک',
                    'parties': Party.objects.filter(is_active=True),
                    'bank_accounts': BankAccount.objects.filter(is_active=True),
                })
        except Exception:
            messages.error(request, 'Invalid amount — غلط رقم')
            return render(request, 'finance/cheque_form.html', {
                'title': 'Record Cheque — چیک',
                'parties': Party.objects.filter(is_active=True),
                'bank_accounts': BankAccount.objects.filter(is_active=True),
            })
        chq = Cheque.objects.create(
            cheque_number=cheque_number,
            bank_name=request.POST.get('bank_name', ''),
            amount=amount_val,
            date_on_cheque=date_on_cheque,
            direction=request.POST.get('direction', 'received'),
            party_id=party_id,
            bank_account_id=request.POST.get('bank_account') or None,
            notes=request.POST.get('notes', ''),
        )

        # Cheque is just recorded — NO balance change until cleared
        # Receipt/Payment will be created when status changes to "Cleared"

        AuditLog.log(user=request.user, action='CREATE', model_name='Cheque',
                     object_id=chq.pk, object_repr=str(chq), request=request,
                     description=f'Cheque #{chq.cheque_number} ₨{float(chq.amount):,.0f} ({chq.get_direction_display()})')
        messages.success(request,
            f'✓ Cheque #{chq.cheque_number} recorded — ₨{chq.amount:,.0f} '
            f'({chq.get_direction_display()}) — balance will update when cleared')
        return redirect('finance:cheque_list')
    return render(request, 'finance/cheque_form.html', {
        'title': 'Record Cheque — چیک',
        'parties': Party.objects.filter(is_active=True),
        'bank_accounts': BankAccount.objects.filter(is_active=True),
    })


@login_required
@require_POST
def cheque_update_status(request, pk):
    from .models import Cheque
    cheque = get_object_or_404(Cheque, pk=pk)
    new_status = request.POST.get('status')
    from django.utils import timezone

    if new_status == 'deposited':
        cheque.deposit_date = timezone.now().date()

    elif new_status == 'cleared':
        cheque.clearance_date = timezone.now().date()
        # NOW create receipt/payment — cheque is confirmed money
        party = cheque.party
        narration = f'Cheque #{cheque.cheque_number} — {cheque.bank_name} (Cleared)'
        if cheque.notes:
            narration += f'. {cheque.notes}'

        if cheque.direction == 'received' and not cheque.receipt_voucher:
            rcv = ReceiptVoucher(
                date=cheque.clearance_date or cheque.date_on_cheque,
                party=party, amount=cheque.amount,
                payment_method='cheque', bank_account=cheque.bank_account,
                cheque_number=cheque.cheque_number, cheque_date=cheque.date_on_cheque,
                bank_name=cheque.bank_name, narration=narration,
                created_by=request.user,
            )
            rcv.save()
            rcv.finalize()
            cheque.receipt_voucher = rcv
            messages.success(request,
                f'✓ Cheque cleared — Receipt {rcv.voucher_number} created, '
                f'₨{cheque.amount:,.0f} from {party.name}. بیلنس اپ ڈیٹ ہو گیا۔')

        elif cheque.direction == 'issued' and not cheque.payment_voucher:
            pmt = PaymentVoucher(
                date=cheque.clearance_date or cheque.date_on_cheque,
                party=party, amount=cheque.amount,
                payment_method='cheque', bank_account=cheque.bank_account,
                cheque_number=cheque.cheque_number, cheque_date=cheque.date_on_cheque,
                bank_name=cheque.bank_name, narration=narration,
                created_by=request.user,
            )
            pmt.save()
            pmt.finalize()
            cheque.payment_voucher = pmt
            messages.success(request,
                f'✓ Cheque cleared — Payment {pmt.voucher_number} created, '
                f'₨{cheque.amount:,.0f} to {party.name}. بیلنس اپ ڈیٹ ہو گیا۔')

    elif new_status == 'bounced':
        cheque.bounce_date = timezone.now().date()
        # If cheque was cleared (receipt/payment exists), reverse it
        if cheque.receipt_voucher and cheque.receipt_voucher.status == 'final':
            rv = cheque.receipt_voucher
            rv.party.current_balance += rv.amount
            rv.party.save(update_fields=['current_balance'])
            if rv.bank_account and rv.payment_method in ('bank', 'cheque', 'online'):
                rv.bank_account.current_balance -= rv.amount
                rv.bank_account.save(update_fields=['current_balance'])
            from apps.accounting.models import JournalEntry
            je = JournalEntry.objects.filter(receipt=rv).first()
            if je and je.is_posted:
                for line in je.lines.all():
                    line.account.current_balance -= (line.debit - line.credit)
                    line.account.save(update_fields=['current_balance'])
                je.is_posted = False; je.save(update_fields=['is_posted'])
            rv.status = 'void'; rv.save()
            messages.warning(request, f'Cheque bounced — Receipt {rv.voucher_number} voided. چیک واپس — بیلنس واپس')
        if cheque.payment_voucher and cheque.payment_voucher.status == 'final':
            pv = cheque.payment_voucher
            pv.party.current_balance -= pv.amount
            pv.party.save(update_fields=['current_balance'])
            if pv.bank_account and pv.payment_method in ('bank', 'cheque', 'online'):
                pv.bank_account.current_balance += pv.amount
                pv.bank_account.save(update_fields=['current_balance'])
            from apps.accounting.models import JournalEntry
            je = JournalEntry.objects.filter(payment=pv).first()
            if je and je.is_posted:
                for line in je.lines.all():
                    line.account.current_balance -= (line.debit - line.credit)
                    line.account.save(update_fields=['current_balance'])
                je.is_posted = False; je.save(update_fields=['is_posted'])
            pv.status = 'void'; pv.save()
            messages.warning(request, f'Cheque bounced — Payment {pv.voucher_number} voided. چیک واپس — بیلنس واپس')
        # If cheque was never cleared, nothing to reverse
        if not cheque.receipt_voucher and not cheque.payment_voucher:
            messages.info(request, f'Cheque #{cheque.cheque_number} bounced. No balance was affected. چیک واپس — کوئی بیلنس تبدیل نہیں ہوا')

    elif new_status == 'cancelled':
        # Same as bounced — reverse if cleared, nothing if not
        if cheque.receipt_voucher and cheque.receipt_voucher.status == 'final':
            rv = cheque.receipt_voucher
            rv.party.current_balance += rv.amount
            rv.party.save(update_fields=['current_balance'])
            if rv.bank_account and rv.payment_method in ('bank', 'cheque', 'online'):
                rv.bank_account.current_balance -= rv.amount
                rv.bank_account.save(update_fields=['current_balance'])
            rv.status = 'void'; rv.save()
        if cheque.payment_voucher and cheque.payment_voucher.status == 'final':
            pv = cheque.payment_voucher
            pv.party.current_balance -= pv.amount
            pv.party.save(update_fields=['current_balance'])
            if pv.bank_account and pv.payment_method in ('bank', 'cheque', 'online'):
                pv.bank_account.current_balance += pv.amount
                pv.bank_account.save(update_fields=['current_balance'])
            pv.status = 'void'; pv.save()

    cheque.status = new_status
    cheque.save()
    AuditLog.log(user=request.user, action='UPDATE', model_name='Cheque',
                 object_id=cheque.pk, object_repr=str(cheque), request=request,
                 description=f'Cheque #{cheque.cheque_number} → {cheque.get_status_display()}')
    messages.success(request, f'Cheque #{cheque.cheque_number} → {cheque.get_status_display()}')
    return redirect('finance:cheque_list')


@login_required
@require_POST
def payment_finalize(request, pk):
    voucher = get_object_or_404(PaymentVoucher, pk=pk)
    if voucher.status != 'draft':
        messages.error(request, 'Only draft payments can be finalized.')
        return redirect('finance:payment_detail', pk=pk)
    voucher.finalize()
    AuditLog.log(user=request.user, action='UPDATE', model_name='PaymentVoucher',
                 object_id=voucher.pk, object_repr=str(voucher), request=request,
                 description=f'Payment finalized: {voucher.voucher_number} ₨{voucher.amount:,.0f}')
    messages.success(request, f'Payment {voucher.voucher_number} finalized ✓ — Party balance updated.')
    return redirect('finance:payment_detail', pk=pk)


@login_required
@require_POST
def payment_void(request, pk):
    voucher = get_object_or_404(PaymentVoucher, pk=pk)
    if voucher.status == 'final':
        voucher.party.current_balance -= voucher.amount
        voucher.party.save(update_fields=['current_balance'])
        # Reverse bank balance
        if voucher.bank_account and voucher.payment_method in ('bank', 'cheque', 'online'):
            voucher.bank_account.current_balance += voucher.amount
            voucher.bank_account.save(update_fields=['current_balance'])
        # Reverse journal entry
        from apps.accounting.models import JournalEntry
        je = JournalEntry.objects.filter(payment=voucher).first()
        if je and je.is_posted:
            for line in je.lines.all():
                line.account.current_balance -= (line.debit - line.credit)
                line.account.save(update_fields=['current_balance'])
            je.is_posted = False
            je.save(update_fields=['is_posted'])
    voucher.status = 'void'
    voucher.save()
    AuditLog.log(user=request.user, action='DELETE', model_name='PaymentVoucher',
                 object_id=voucher.pk, object_repr=str(voucher), request=request,
                 description=f'Payment VOIDED: {voucher.voucher_number} ₨{voucher.amount:,.0f}')
    messages.success(request, f'Payment {voucher.voucher_number} voided.')
    return redirect('finance:payment_list')


@login_required
@require_POST
def receipt_finalize(request, pk):
    voucher = get_object_or_404(ReceiptVoucher, pk=pk)
    if voucher.status != 'draft':
        messages.error(request, 'Only draft receipts can be finalized.')
        return redirect('finance:receipt_detail', pk=pk)
    voucher.finalize()
    AuditLog.log(user=request.user, action='UPDATE', model_name='ReceiptVoucher',
                 object_id=voucher.pk, object_repr=str(voucher), request=request,
                 description=f'Receipt finalized: {voucher.voucher_number} ₨{voucher.amount:,.0f}')
    messages.success(request, f'Receipt {voucher.voucher_number} finalized ✓ — Party balance updated.')
    return redirect('finance:receipt_detail', pk=pk)


@login_required
@require_POST
def receipt_void(request, pk):
    voucher = get_object_or_404(ReceiptVoucher, pk=pk)
    if voucher.status == 'final':
        voucher.party.current_balance += voucher.amount
        voucher.party.save(update_fields=['current_balance'])
        # Reverse bank balance
        if voucher.bank_account and voucher.payment_method in ('bank', 'cheque', 'online'):
            voucher.bank_account.current_balance -= voucher.amount
            voucher.bank_account.save(update_fields=['current_balance'])
        # Reverse journal entry
        from apps.accounting.models import JournalEntry
        je = JournalEntry.objects.filter(receipt=voucher).first()
        if je and je.is_posted:
            for line in je.lines.all():
                line.account.current_balance -= (line.debit - line.credit)
                line.account.save(update_fields=['current_balance'])
            je.is_posted = False
            je.save(update_fields=['is_posted'])
    voucher.status = 'void'
    voucher.save()
    AuditLog.log(user=request.user, action='DELETE', model_name='ReceiptVoucher',
                 object_id=voucher.pk, object_repr=str(voucher), request=request,
                 description=f'Receipt VOIDED: {voucher.voucher_number} ₨{voucher.amount:,.0f}')
    messages.success(request, f'Receipt {voucher.voucher_number} voided.')
    return redirect('finance:receipt_list')


# ─── BANK RECONCILIATION ────────────────────────────
@login_required
def reconciliation_list(request):
    from .models import BankReconciliation
    recs = BankReconciliation.objects.select_related('bank_account').all()
    return render(request, 'finance/reconciliation_list.html', {'reconciliations': recs})


@login_required
def reconciliation_create(request):
    from .models import BankAccount, BankReconciliation, BankReconciliationItem
    from apps.reports.views import _dates

    bank_accounts = BankAccount.objects.filter(is_active=True)

    if request.method == 'POST':
        bank_id = request.POST.get('bank_account', '').strip()
        recon_date = request.POST.get('date', '').strip()

        if not bank_id:
            messages.error(request, 'Please select a bank account — بینک اکاؤنٹ منتخب کریں')
            return render(request, 'finance/reconciliation_form.html', {
                'bank_accounts': bank_accounts, 'payments': [], 'receipts': [],
                'selected_bank': None, 'sys_balance': 0,
            })
        if not recon_date:
            messages.error(request, 'Date is required — تاریخ ضروری ہے')
            return render(request, 'finance/reconciliation_form.html', {
                'bank_accounts': bank_accounts, 'payments': [], 'receipts': [],
                'selected_bank': None, 'sys_balance': 0,
            })

        bank = get_object_or_404(BankAccount, pk=bank_id)
        stmt_balance = Decimal(request.POST.get('statement_balance', '0'))
        notes = request.POST.get('notes', '')

        # Get all bank transactions for this account
        bank_payments = PaymentVoucher.objects.filter(
            status='final', payment_method__in=['bank', 'cheque', 'online']
        ).order_by('date')
        bank_receipts = ReceiptVoucher.objects.filter(
            status='final', payment_method__in=['bank', 'cheque', 'online']
        ).order_by('date')

        # Calculate system balance
        total_out = sum(p.amount for p in bank_payments)
        total_in = sum(r.amount for r in bank_receipts)
        sys_balance = bank.opening_balance + total_in - total_out

        rec = BankReconciliation(
            bank_account=bank, date=recon_date,
            statement_balance=stmt_balance, system_balance=sys_balance,
            notes=notes, created_by=request.user,
        )
        rec.save()

        # Create items for unmatched transactions
        for p in bank_payments:
            matched = request.POST.get(f'match_pay_{p.pk}') == 'on'
            BankReconciliationItem.objects.create(
                reconciliation=rec, date=p.date,
                description=f'Payment to {p.party.name} ({p.voucher_number})',
                amount=p.amount, is_credit=False, is_matched=matched,
                payment_voucher=p,
            )
        for r in bank_receipts:
            matched = request.POST.get(f'match_rcv_{r.pk}') == 'on'
            BankReconciliationItem.objects.create(
                reconciliation=rec, date=r.date,
                description=f'Receipt from {r.party.name} ({r.voucher_number})',
                amount=r.amount, is_credit=True, is_matched=matched,
                receipt_voucher=r,
            )

        messages.success(request, f'Reconciliation saved. Difference: ₨{rec.difference:,.0f}')
        return redirect('finance:reconciliation_list')

    # For GET, show the form with bank transactions
    bank_id = request.GET.get('bank')
    selected_bank = None
    payments = []
    receipts = []
    sys_balance = Decimal('0')

    if bank_id:
        selected_bank = get_object_or_404(BankAccount, pk=bank_id)
        payments = PaymentVoucher.objects.filter(
            status='final', payment_method__in=['bank', 'cheque', 'online']
        ).select_related('party').order_by('date')
        receipts = ReceiptVoucher.objects.filter(
            status='final', payment_method__in=['bank', 'cheque', 'online']
        ).select_related('party').order_by('date')
        total_out = sum(p.amount for p in payments)
        total_in = sum(r.amount for r in receipts)
        sys_balance = selected_bank.opening_balance + total_in - total_out

    return render(request, 'finance/reconciliation_form.html', {
        'bank_accounts': bank_accounts, 'selected_bank': selected_bank,
        'payments': payments, 'receipts': receipts, 'sys_balance': sys_balance,
        'title': 'Bank Reconciliation — بینک مطابقت',
        'back_url': '/finance/bank-accounts/',
    })


@login_required
@require_POST
def bank_account_quick_add_api(request):
    """Quick-add a bank account — returns JSON."""
    from django.http import JsonResponse
    from .models import BankAccount
    bank_name = request.POST.get('name', '').strip()
    if not bank_name:
        return JsonResponse({'error': 'Bank name is required — بینک کا نام ضروری ہے'}, status=400)
    account_number = request.POST.get('account_number', '').strip() or 'N/A'
    ba = BankAccount.objects.create(
        bank_name=bank_name,
        account_number=account_number,
        bank_code='other',
        account_type='current',
    )
    AuditLog.log(
        user=request.user, action='CREATE', model_name='BankAccount',
        object_id=ba.pk, object_repr=str(ba), request=request,
        description=f'Quick-add bank: {ba.bank_name}',
    )
    return JsonResponse({'id': ba.pk, 'name': f'{ba.bank_name} — {ba.account_number}'})


# ─── TRANSACTION HISTORY ─────────────────────────────
@login_required
def transaction_history(request):
    """Unified view: all payments, receipts, cheques — who paid whom."""
    from django.core.paginator import Paginator
    from apps.parties.models import Party

    party_id = request.GET.get('party')
    method = request.GET.get('method')
    tx_type = request.GET.get('type')

    start, end = None, None
    from_str = request.GET.get('from')
    to_str = request.GET.get('to')
    from datetime import date
    today = date.today()
    try:
        start = date.fromisoformat(from_str) if from_str else today.replace(day=1)
    except (ValueError, TypeError):
        start = today.replace(day=1)
    try:
        end = date.fromisoformat(to_str) if to_str else today
    except (ValueError, TypeError):
        end = today

    transactions = []

    # Payments (we paid someone)
    if not tx_type or tx_type == 'payment':
        payments = PaymentVoucher.objects.filter(date__range=[start, end], status='final').select_related('party')
        if party_id:
            payments = payments.filter(party_id=party_id)
        if method:
            payments = payments.filter(payment_method=method)
        for p in payments:
            transactions.append({
                'date': p.date, 'type': 'Payment — ادائیگی', 'type_class': 'payment',
                'ref': p.voucher_number, 'party': p.party.name if p.party else '—',
                'method': p.get_payment_method_display(), 'amount': p.amount,
                'direction': 'out', 'narration': p.narration,
                'url': f'/finance/payments/{p.pk}/',
            })

    # Receipts (someone paid us)
    if not tx_type or tx_type == 'receipt':
        receipts = ReceiptVoucher.objects.filter(date__range=[start, end], status='final').select_related('party')
        if party_id:
            receipts = receipts.filter(party_id=party_id)
        if method:
            receipts = receipts.filter(payment_method=method)
        for r in receipts:
            transactions.append({
                'date': r.date, 'type': 'Receipt — وصولی', 'type_class': 'receipt',
                'ref': r.voucher_number, 'party': r.party.name if r.party else '—',
                'method': r.get_payment_method_display(), 'amount': r.amount,
                'direction': 'in', 'narration': r.narration,
                'url': f'/finance/receipts/{r.pk}/',
            })

    # Cross-Party Adjustments — NOT shown as separate rows because 
    # the auto-created Receipt + Payment already appear in the list.
    # Showing them would triple-count the same transaction.

    # Expenses (money out)
    if not tx_type or tx_type == 'expense':
        expenses_qs = Expense.objects.filter(date__range=[start, end])
        if method:
            expenses_qs = expenses_qs.filter(payment_method=method)
        for e in expenses_qs:
            transactions.append({
                'date': e.date, 'type': 'Expense — خرچہ', 'type_class': 'expense',
                'ref': f'{e.get_category_display()}',
                'party': e.paid_to or '—',
                'method': e.get_payment_method_display(), 'amount': e.amount,
                'direction': 'out', 'narration': e.description,
                'url': None,
            })

    # Cheques — NOT shown as separate rows because every cheque now
    # auto-creates a Receipt (received) or Payment (issued) which already
    # appears in the list above. Showing both would double-count.

    transactions.sort(key=lambda x: x['date'], reverse=True)

    total_in = sum(t['amount'] for t in transactions if t['direction'] == 'in')
    total_out = sum(t['amount'] for t in transactions if t['direction'] == 'out')

    parties = Party.objects.filter(is_active=True).order_by('name')

    # Selected party balance info
    selected_party_obj = None
    if party_id:
        try:
            selected_party_obj = Party.objects.get(pk=party_id)
        except Party.DoesNotExist:
            pass

    # Outstanding balances summary (top 5 each)
    from django.db.models import Sum
    parties_owe_us = Party.objects.filter(
        current_balance__gt=0, is_active=True
    ).order_by('-current_balance')[:5]
    total_receivable = Party.objects.filter(
        current_balance__gt=0, is_active=True
    ).aggregate(t=Sum('current_balance'))['t'] or 0

    we_owe_parties = Party.objects.filter(
        current_balance__lt=0, is_active=True
    ).order_by('current_balance')[:5]
    total_payable = abs(Party.objects.filter(
        current_balance__lt=0, is_active=True
    ).aggregate(t=Sum('current_balance'))['t'] or 0)

    return render(request, 'finance/transaction_history.html', {
        'transactions': transactions,
        'total_in': total_in, 'total_out': total_out, 'net': total_in - total_out,
        'parties': parties, 'selected_party': party_id,
        'selected_party_obj': selected_party_obj,
        'selected_method': method, 'selected_type': tx_type,
        'filter_from': start, 'filter_to': end,
        'parties_owe_us': parties_owe_us, 'total_receivable': total_receivable,
        'we_owe_parties': we_owe_parties, 'total_payable': total_payable,
    })


@login_required
def expense_edit(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == 'POST':
        from .forms import ExpenseForm
        old_amount = expense.amount
        old_category = expense.category
        form = ExpenseForm(request.POST, request.FILES, instance=expense)
        if form.is_valid():
            expense = form.save()
            changes = []
            if old_amount != expense.amount:
                changes.append(f'amount: {old_amount}→{expense.amount}')
            if old_category != expense.category:
                changes.append(f'category: {old_category}→{expense.category}')
            AuditLog.log(user=request.user, action='UPDATE', model_name='Expense',
                         object_id=expense.pk, object_repr=str(expense), request=request,
                         description=f'Expense edited. Changes: {", ".join(changes) or "minor"}')
            messages.success(request, 'Expense updated — خرچہ اپ ڈیٹ ہو گیا')
            return redirect('finance:expense_list')
    else:
        from .forms import ExpenseForm
        form = ExpenseForm(instance=expense)
    return render(request, 'finance/expense_form.html', {
        'form': form, 'title': f'Edit Expense — خرچہ ترمیم',
        'back_url': '/finance/expenses/', 'submit_label': 'Update', 'submit_label_ur': 'اپ ڈیٹ'
    })


@login_required
@require_POST
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    desc = f'{expense.get_category_display()} ₨{expense.amount}'
    # Reverse journal
    from apps.accounting.models import JournalEntry
    # Find the journal entry for this expense — match by type, date, and amount
    je = JournalEntry.objects.filter(
        entry_type='expense', date=expense.date
    ).filter(
        lines__debit=expense.amount
    ).order_by('-pk').first()
    if je and je.is_posted:
        for line in je.lines.all():
            line.account.current_balance -= (line.debit - line.credit)
            line.account.save(update_fields=['current_balance'])
        je.is_posted = False
        je.save(update_fields=['is_posted'])
    expense.delete()
    AuditLog.log(user=request.user, action='DELETE', model_name='Expense',
                 object_id=pk, description=f'Expense deleted: {desc}')
    messages.success(request, f'Expense deleted — خرچہ حذف ہو گیا')
    return redirect('finance:expense_list')


# ─── CROSS-PARTY ADJUSTMENT — کراس پارٹی ایڈجسٹمنٹ ─────────────
@login_required
def adjustment_list(request):
    from django.core.paginator import Paginator
    from django.db.models import Sum
    from apps.parties.models import Party
    adjustments = CrossPartyAdjustment.objects.select_related('from_party', 'to_party').all()
    search = request.GET.get('search', '')
    if search:
        adjustments = adjustments.filter(
            Q(voucher_number__icontains=search) |
            Q(from_party__name__icontains=search) |
            Q(to_party__name__icontains=search)
        )
    status = request.GET.get('status')
    if status:
        adjustments = adjustments.filter(status=status)
    party_id = request.GET.get('party')
    if party_id:
        adjustments = adjustments.filter(Q(from_party_id=party_id) | Q(to_party_id=party_id))
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    if date_from:
        adjustments = adjustments.filter(date__gte=date_from)
    if date_to:
        adjustments = adjustments.filter(date__lte=date_to)
    totals = adjustments.filter(status='final').aggregate(total=Sum('amount'))
    paginator = Paginator(adjustments, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    parties = Party.objects.filter(is_active=True).order_by('name')
    return render(request, 'finance/adjustment_list.html', {
        'adjustments': page_obj, 'search': search, 'page_obj': page_obj,
        'selected_status': status or '', 'selected_party': party_id or '',
        'filter_from': date_from, 'filter_to': date_to,
        'parties': parties,
        'total_amount': totals['total'] or 0,
    })


@login_required
def adjustment_create(request):
    if request.method == 'POST':
        form = CrossPartyAdjustmentForm(request.POST)
        if form.is_valid():
            adj = form.save(commit=False)
            adj.created_by = request.user
            adj.save()
            we_owe_them = form.cleaned_data.get('we_owe_them', True)
            method = form.cleaned_data.get('payment_method', 'cash')
            adj.finalize(we_owe_them=we_owe_them, method=method)
            owe_note = '' if we_owe_them else ' (no debt — بغیر قرض)'
            AuditLog.log(
                user=request.user, action='CREATE', model_name='CrossPartyAdjustment',
                object_id=adj.pk, object_repr=str(adj), request=request,
                description=f'Cross-Party Adjustment: {adj.voucher_number} ₨{adj.amount:,.0f} '
                            f'{adj.from_party.name} → {adj.to_party.name}{owe_note}'
            )
            messages.success(
                request,
                f'✓ Adjustment saved — ₨{adj.amount:,.0f} '
                f'({adj.from_party.name} → {adj.to_party.name})'
            )
            return redirect('finance:adjustment_detail', pk=adj.pk)
    else:
        from django.utils import timezone
        form = CrossPartyAdjustmentForm(initial={'date': timezone.now().date()})
    return render(request, 'finance/adjustment_form.html', {
        'form': form,
        'title': 'New Cross-Party Adjustment — نئی کراس پارٹی ایڈجسٹمنٹ',
        'back_url': '/finance/adjustments/',
    })


@login_required
def adjustment_detail(request, pk):
    adj = get_object_or_404(
        CrossPartyAdjustment.objects.select_related('from_party', 'to_party', 'created_by'),
        pk=pk
    )
    return render(request, 'finance/adjustment_detail.html', {
        'adj': adj,
        'title': f'Adjustment {adj.voucher_number}',
    })


@login_required
def adjustment_edit(request, pk):
    adj = get_object_or_404(CrossPartyAdjustment, pk=pk)
    if adj.status == 'void':
        messages.error(request, 'Voided adjustments cannot be edited.')
        return redirect('finance:adjustment_detail', pk=pk)
    if request.method == 'POST':
        old_amount = adj.amount
        old_from = adj.from_party_id
        old_to = adj.to_party_id
        form = CrossPartyAdjustmentForm(request.POST, instance=adj)
        if form.is_valid():
            a = form.save()
            changes = []
            if old_amount != a.amount:
                changes.append(f'amount: {old_amount}→{a.amount}')
            if old_from != a.from_party_id:
                changes.append('from_party changed')
            if old_to != a.to_party_id:
                changes.append('to_party changed')
            AuditLog.log(
                user=request.user, action='UPDATE', model_name='CrossPartyAdjustment',
                object_id=a.pk, object_repr=str(a), request=request,
                description=f'Adjustment edited: {", ".join(changes) or "minor changes"}'
            )
            messages.success(request, 'Adjustment updated — ایڈجسٹمنٹ اپ ڈیٹ ہو گئی')
            return redirect('finance:adjustment_detail', pk=a.pk)
    else:
        form = CrossPartyAdjustmentForm(instance=adj)
    return render(request, 'finance/adjustment_form.html', {
        'form': form,
        'title': f'Edit Adjustment — {adj.voucher_number}',
        'editing': True, 'adjustment': adj,
        'back_url': f'/finance/adjustments/{pk}/',
        'submit_label': 'Update', 'submit_label_ur': 'اپ ڈیٹ',
    })


@login_required
@require_POST
def adjustment_void(request, pk):
    adj = get_object_or_404(CrossPartyAdjustment, pk=pk)
    if adj.status == 'final':
        adj.void()
        AuditLog.log(
            user=request.user, action='DELETE', model_name='CrossPartyAdjustment',
            object_id=adj.pk, object_repr=str(adj), request=request,
            description=f'Adjustment VOIDED: {adj.voucher_number} ₨{adj.amount:,.0f}'
        )
        messages.success(request, f'Adjustment {adj.voucher_number} voided — ایڈجسٹمنٹ کالعدم')
    return redirect('finance:adjustment_list')
