"""
Accounting Views — Chart of Accounts, Journal Entries.
"""
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from apps.authentication.models import AuditLog
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import AccountGroup, Account, JournalEntry, JournalLine


@login_required
def chart_of_accounts(request):
    groups = AccountGroup.objects.prefetch_related('accounts').all()
    return render(request, 'accounting/chart_of_accounts.html', {'groups': groups})


@login_required
def account_ledger(request, pk):
    account = get_object_or_404(Account, pk=pk)
    lines = JournalLine.objects.filter(account=account).select_related(
        'journal', 'party'
    ).order_by('journal__date')
    return render(request, 'accounting/account_ledger.html', {'account': account, 'lines': lines})


@login_required
def journal_list(request):
    from django.core.paginator import Paginator
    from django.db.models import Q
    journals = JournalEntry.objects.prefetch_related('lines').all()
    search = request.GET.get('search', '')
    if search:
        journals = journals.filter(
            Q(entry_number__icontains=search) | Q(narration__icontains=search)
        )
    paginator = Paginator(journals, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounting/journal_list.html', {
        'journals': page_obj, 'page_obj': page_obj, 'search': search
    })


@login_required
def journal_create(request):
    if request.method == 'POST':
        date_val = (request.POST.get('date') or '').strip()
        if not date_val:
            messages.error(request, 'Date is required — تاریخ ضروری ہے')
            accounts = Account.objects.filter(is_active=True).order_by('code')
            return render(request, 'accounting/journal_form.html', {'accounts': accounts})

        # Parse and validate line items before creating anything
        lines = []
        i = 0
        while f'account_{i}' in request.POST:
            acct_id = request.POST.get(f'account_{i}')
            debit_str = request.POST.get(f'debit_{i}', '0') or '0'
            credit_str = request.POST.get(f'credit_{i}', '0') or '0'
            if acct_id:
                try:
                    acct_id = int(acct_id)
                    debit_val = Decimal(debit_str)
                    credit_val = Decimal(credit_str)
                    if debit_val < 0 or credit_val < 0:
                        messages.error(request, f'Row {i+1}: amounts cannot be negative — رقم منفی نہیں ہو سکتی')
                        accounts = Account.objects.filter(is_active=True).order_by('code')
                        return render(request, 'accounting/journal_form.html', {'accounts': accounts})
                    lines.append({'account_id': acct_id, 'debit': debit_val, 'credit': credit_val})
                except (ValueError, InvalidOperation):
                    messages.error(request, f'Row {i+1}: invalid amount — غلط رقم')
                    accounts = Account.objects.filter(is_active=True).order_by('code')
                    return render(request, 'accounting/journal_form.html', {'accounts': accounts})
            i += 1

        if not lines:
            messages.error(request, 'Add at least one line item — کم از کم ایک لائن شامل کریں')
            accounts = Account.objects.filter(is_active=True).order_by('code')
            return render(request, 'accounting/journal_form.html', {'accounts': accounts})

        je = JournalEntry(
            entry_number=JournalEntry.generate_number(),
            date=date_val,
            entry_type='journal',
            narration=request.POST.get('narration', ''),
            created_by=request.user,
        )
        je.save()

        for line in lines:
            JournalLine.objects.create(
                journal=je, account_id=line['account_id'],
                debit=line['debit'], credit=line['credit'],
            )

        if je.is_balanced:
            je.post()
            AuditLog.log(user=request.user, action='CREATE', model_name='JournalEntry',
                         object_id=je.pk, object_repr=str(je), request=request,
                         description=f'Journal voucher: {je.entry_number}')
            messages.success(request, f'Journal {je.entry_number} posted — جرنل پوسٹ ہو گیا')
        else:
            messages.warning(request, f'Journal {je.entry_number} saved but NOT balanced — Dr ≠ Cr — برابر نہیں')
        return redirect('accounting:journal_list')

    accounts = Account.objects.filter(is_active=True).order_by('code')
    return render(request, 'accounting/journal_form.html', {'accounts': accounts})


# ─── ACCOUNT CRUD ─────────────────
@login_required
def account_create(request):
    if request.method == 'POST':
        code = (request.POST.get('code') or '').strip()
        name = (request.POST.get('name') or '').strip()
        group_id = request.POST.get('group')

        # Validate required fields
        if not name:
            messages.error(request, 'Account name is required — اکاؤنٹ کا نام ضروری ہے')
            groups = AccountGroup.objects.all()
            return render(request, 'accounting/account_form.html', {
                'groups': groups, 'title': 'Add Account — اکاؤنٹ',
                'back_url': '/accounting/chart/', 'submit_label': 'Create', 'submit_label_ur': 'بنائیں'
            })
        if not code:
            messages.error(request, 'Account code is required — اکاؤنٹ کوڈ ضروری ہے')
            groups = AccountGroup.objects.all()
            return render(request, 'accounting/account_form.html', {
                'groups': groups, 'title': 'Add Account — اکاؤنٹ',
                'back_url': '/accounting/chart/', 'submit_label': 'Create', 'submit_label_ur': 'بنائیں'
            })
        if not group_id:
            messages.error(request, 'Account group is required — اکاؤنٹ گروپ ضروری ہے')
            groups = AccountGroup.objects.all()
            return render(request, 'accounting/account_form.html', {
                'groups': groups, 'title': 'Add Account — اکاؤنٹ',
                'back_url': '/accounting/chart/', 'submit_label': 'Create', 'submit_label_ur': 'بنائیں'
            })

        # Check for duplicate code
        if Account.objects.filter(code=code).exists():
            messages.error(request, f'Account code "{code}" already exists — یہ کوڈ پہلے سے موجود ہے')
            groups = AccountGroup.objects.all()
            return render(request, 'accounting/account_form.html', {
                'groups': groups, 'title': 'Add Account — اکاؤنٹ',
                'back_url': '/accounting/chart/', 'submit_label': 'Create', 'submit_label_ur': 'بنائیں'
            })

        account = Account.objects.create(
            name=name,
            name_urdu=request.POST.get('name_urdu', ''),
            code=code,
            group_id=group_id,
            description=request.POST.get('description', ''),
        )
        AuditLog.log(user=request.user, action='CREATE', model_name='Account',
                     object_id=account.pk, object_repr=str(account), request=request)
        messages.success(request, f'Account "{account.name}" created — اکاؤنٹ بن گیا')
        return redirect('accounting:chart')
    groups = AccountGroup.objects.all()
    return render(request, 'accounting/account_form.html', {
        'groups': groups, 'title': 'Add Account — اکاؤنٹ',
        'back_url': '/accounting/chart/', 'submit_label': 'Create', 'submit_label_ur': 'بنائیں'
    })


@login_required
def account_edit(request, pk):
    account = get_object_or_404(Account, pk=pk)
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        if not name:
            messages.error(request, 'Account name is required — اکاؤنٹ کا نام ضروری ہے')
            groups = AccountGroup.objects.all()
            return render(request, 'accounting/account_form.html', {
                'account': account, 'groups': groups, 'title': f'Edit: {account.name}',
                'back_url': '/accounting/chart/', 'submit_label': 'Update', 'submit_label_ur': 'اپ ڈیٹ'
            })
        account.name = name
        account.name_urdu = request.POST.get('name_urdu', '')
        account.description = request.POST.get('description', '')
        account.group_id = request.POST.get('group', account.group_id)
        account.is_active = 'is_active' in request.POST
        account.save()
        AuditLog.log(user=request.user, action='UPDATE', model_name='Account',
                     object_id=account.pk, object_repr=str(account), request=request)
        messages.success(request, f'Account {account.code} updated — اکاؤنٹ اپ ڈیٹ ہو گیا')
        return redirect('accounting:chart')
    groups = AccountGroup.objects.all()
    return render(request, 'accounting/account_form.html', {
        'account': account, 'groups': groups, 'title': f'Edit: {account.name}',
        'back_url': '/accounting/chart/', 'submit_label': 'Update', 'submit_label_ur': 'اپ ڈیٹ'
    })


@login_required
def group_create(request):
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        code = (request.POST.get('code') or '').strip()
        group_type = request.POST.get('group_type', 'asset')
        if not name or not code:
            messages.error(request, 'Name and code are required — نام اور کوڈ ضروری ہیں')
            return render(request, 'accounting/group_form.html', {
                'title': 'Add Account Group — اکاؤنٹ گروپ',
                'group_types': AccountGroup.GROUP_TYPES,
            })
        if AccountGroup.objects.filter(code=code).exists():
            messages.error(request, f'Code "{code}" already exists — یہ کوڈ پہلے سے موجود ہے')
            return render(request, 'accounting/group_form.html', {
                'title': 'Add Account Group — اکاؤنٹ گروپ',
                'group_types': AccountGroup.GROUP_TYPES,
            })
        group = AccountGroup.objects.create(
            name=name, code=code, group_type=group_type,
            name_urdu=request.POST.get('name_urdu', ''),
        )
        AuditLog.log(user=request.user, action='CREATE', model_name='AccountGroup',
                     object_id=group.pk, object_repr=str(group), request=request)
        messages.success(request, f'Account group "{name}" created — اکاؤنٹ گروپ بن گیا')
        return redirect('accounting:chart')
    return render(request, 'accounting/group_form.html', {
        'title': 'Add Account Group — اکاؤنٹ گروپ',
        'group_types': AccountGroup.GROUP_TYPES,
    })


@login_required
def balance_sheet(request):
    """Simple balance sheet: Assets vs Liabilities + Capital."""
    assets = Account.objects.filter(group__group_type='asset', current_balance__gt=0)
    liabilities = Account.objects.filter(group__group_type='liability')
    capital = Account.objects.filter(group__group_type='capital')
    
    total_assets = sum(a.current_balance for a in assets)
    total_liabilities = sum(abs(a.current_balance) for a in liabilities)
    total_capital = sum(abs(a.current_balance) for a in capital)
    
    return render(request, 'accounting/balance_sheet.html', {
        'assets': assets, 'liabilities': liabilities, 'capital': capital,
        'total_assets': total_assets, 'total_liabilities': total_liabilities,
        'total_capital': total_capital,
    })
