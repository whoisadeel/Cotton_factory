from django import forms
from django.core.validators import MinValueValidator
from decimal import Decimal
from .models import PaymentVoucher, ReceiptVoucher, Expense, BankAccount
from apps.parties.models import Party

I = ('w-full px-4 py-3 rounded-xl text-sm transition-all duration-200 outline-none '
     'bg-white border-2 border-gray-200 hover:border-gray-300 '
     'focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 placeholder:text-gray-400')
I_BIG = I + ' text-2xl font-bold text-center'
I_STYLE = 'width:100%;padding:10px 14px;border:2px solid #e5e7eb;border-radius:12px;font-size:14px;outline:none;'


def _mark(form):
    for fn in form.errors:
        if fn in form.fields:
            w = form.fields[fn].widget
            w.attrs['class'] = w.attrs.get('class', '').replace('border-gray-200', 'border-red-400').replace('bg-white', 'bg-red-50/50')


class PaymentForm(forms.ModelForm):
    action = forms.CharField(widget=forms.HiddenInput(), required=False, initial='draft')

    class Meta:
        model = PaymentVoucher
        fields = ['date', 'party', 'amount', 'payment_method', 'bank_account',
                  'received_by', 'handed_by', 'receipt_number',
                  'cash_given_date', 'cash_given_time',
                  'recipient_bank_name', 'recipient_account_title',
                  'recipient_account_number', 'recipient_iban',
                  'cheque_number', 'cheque_date',
                  'transaction_ref', 'narration', 'attachment']
        widgets = {
            'date': forms.DateInput(attrs={'class': I, 'style': I_STYLE, 'type': 'date'}),
            'party': forms.Select(attrs={'class': I, 'style': I_STYLE + 'background:white;'}),
            'amount': forms.NumberInput(attrs={'class': I_BIG, 'style': I_STYLE + 'font-size:24px;font-weight:700;text-align:center;', 'step': '0.01', 'min': '0', 'placeholder': '0'}),
            'payment_method': forms.HiddenInput(),
            'bank_account': forms.Select(attrs={'class': I, 'style': I_STYLE + 'background:white;'}),
            'cheque_number': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'Cheque number'}),
            'cheque_date': forms.DateInput(attrs={'class': I, 'style': I_STYLE, 'type': 'date'}),
            'transaction_ref': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'Transaction reference #'}),
            'received_by': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'Name of person who received cash'}),
            'handed_by': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'Who from our side gave the cash'}),
            'receipt_number': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'Receipt or voucher number'}),
            'cash_given_date': forms.DateInput(attrs={'class': I, 'style': I_STYLE, 'type': 'date'}),
            'cash_given_time': forms.TimeInput(attrs={'class': I, 'style': I_STYLE, 'type': 'time'}),
            'recipient_bank_name': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'Their bank name'}),
            'recipient_account_title': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'Account holder name'}),
            'recipient_account_number': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'Account or IBAN number'}),
            'recipient_iban': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'PK00XXXX0000000000000'}),
            'narration': forms.Textarea(attrs={'class': I, 'style': I_STYLE + 'resize:vertical;', 'rows': 2, 'placeholder': 'What is this payment for?'}),
            'attachment': forms.FileInput(attrs={'class': I, 'style': I_STYLE}),
        }
        labels = {
            'date': 'Date', 'party': 'Pay To', 'amount': 'Amount',
            'narration': 'Description', 'transaction_ref': 'Reference #',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['amount'].validators.append(MinValueValidator(Decimal('0'), message='Amount cannot be negative — رقم منفی نہیں ہو سکتی'))
        self.fields['party'].queryset = Party.objects.filter(
            is_active=True
        ).order_by('name')
        self.fields['party'].label_from_instance = lambda p: f"{p.name} ({p.get_party_type_display()}) — ₨{abs(p.current_balance):,.0f}"

        optional = ['cheque_number', 'cheque_date', 'transaction_ref', 'narration', 'attachment',
                     'bank_account', 'received_by', 'handed_by', 'receipt_number',
                     'cash_given_date', 'cash_given_time',
                     'recipient_bank_name', 'recipient_account_title',
                     'recipient_account_number', 'recipient_iban']
        for f in optional:
            self.fields[f].required = False

        self.fields['bank_account'].queryset = BankAccount.objects.filter(is_active=True, owner_type='own')
        self.fields['bank_account'].empty_label = '— Select Our Bank Account — ہمارا بینک اکاؤنٹ —'
        self.fields['bank_account'].label_from_instance = lambda ba: f"{ba.bank_name} — {ba.account_number} (₨{ba.current_balance:,.0f})"

        urdu = {
            'date': 'تاریخ', 'party': 'کسے ادائیگی', 'amount': 'رقم',
            'narration': 'تفصیل', 'received_by': 'کس نے وصول کیا',
            'handed_by': 'کس نے دیا', 'receipt_number': 'رسید نمبر',
            'cash_given_date': 'نقد دینے کی تاریخ', 'cash_given_time': 'نقد دینے کا وقت',
            'bank_account': 'ہمارا بینک اکاؤنٹ',
            'recipient_bank_name': 'ان کا بینک', 'recipient_account_title': 'اکاؤنٹ ٹائٹل',
            'recipient_account_number': 'اکاؤنٹ نمبر', 'recipient_iban': 'آئی بی اے این',
            'cheque_number': 'چیک نمبر', 'cheque_date': 'چیک تاریخ',
            'transaction_ref': 'ریفرنس نمبر',
        }
        for fn, f in self.fields.items():
            f.urdu_label = urdu.get(fn, '')

    def save(self, commit=True):
        instance = super().save(commit=False)
        ba = instance.bank_account
        if ba:
            instance.bank_name = f"{ba.bank_name} — {ba.account_number}"
        if commit:
            instance.save()
        return instance

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero — رقم صفر سے زیادہ ہونی چاہیے')
        return amount

    def is_valid(self):
        r = super().is_valid()
        if not r: _mark(self)
        return r


class ReceiptForm(forms.ModelForm):
    action = forms.CharField(widget=forms.HiddenInput(), required=False, initial='draft')
    redirect_to_party = forms.ModelChoiceField(
        queryset=Party.objects.filter(is_active=True).order_by('name'),
        required=False,
        empty_label='— None (keep the money) — نہیں (رقم رکھیں) —',
        widget=forms.Select(attrs={'class': I, 'style': I_STYLE + 'background:white;'}),
        label='Redirect Payment To — ادائیگی بھیجیں',
    )
    we_owe_them = forms.BooleanField(
        required=False, initial=True,
        label='This is a Payable — واجب الادا ہے',
        widget=forms.CheckboxInput(attrs={'style': 'width:18px;height:18px;accent-color:#7c3aed;cursor:pointer;'}),
    )

    class Meta:
        model = ReceiptVoucher
        fields = ['date', 'party', 'amount', 'payment_method', 'bank_account',
                  'paid_by', 'received_by_us', 'receipt_number',
                  'cash_received_date', 'cash_received_time',
                  'sender_bank_name', 'sender_account_title',
                  'sender_account_number', 'sender_iban',
                  'cheque_number', 'cheque_date',
                  'transaction_ref', 'narration', 'attachment']
        widgets = {
            'date': forms.DateInput(attrs={'class': I, 'style': I_STYLE, 'type': 'date'}),
            'party': forms.Select(attrs={'class': I, 'style': I_STYLE + 'background:white;'}),
            'amount': forms.NumberInput(attrs={'class': I_BIG, 'style': I_STYLE + 'font-size:24px;font-weight:700;text-align:center;', 'step': '0.01', 'min': '0', 'placeholder': '0'}),
            'payment_method': forms.HiddenInput(),
            'bank_account': forms.Select(attrs={'class': I, 'style': I_STYLE + 'background:white;'}),
            'cheque_number': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'Cheque number'}),
            'cheque_date': forms.DateInput(attrs={'class': I, 'style': I_STYLE, 'type': 'date'}),
            'transaction_ref': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'Transaction reference #'}),
            'paid_by': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'Person who handed cash'}),
            'received_by_us': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'Our person who received it'}),
            'receipt_number': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'Receipt number'}),
            'cash_received_date': forms.DateInput(attrs={'class': I, 'style': I_STYLE, 'type': 'date'}),
            'cash_received_time': forms.TimeInput(attrs={'class': I, 'style': I_STYLE, 'type': 'time'}),
            'sender_bank_name': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'Their bank name'}),
            'sender_account_title': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'Account holder name'}),
            'sender_account_number': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'Account or IBAN number'}),
            'sender_iban': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'PK00XXXX0000000000000'}),
            'narration': forms.Textarea(attrs={'class': I, 'style': I_STYLE + 'resize:vertical;', 'rows': 2}),
            'attachment': forms.FileInput(attrs={'class': I, 'style': I_STYLE}),
        }
        labels = {'party': 'Received From', 'amount': 'Amount', 'narration': 'Description'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['amount'].validators.append(MinValueValidator(Decimal('0'), message='Amount cannot be negative — رقم منفی نہیں ہو سکتی'))
        self.fields['party'].queryset = Party.objects.filter(is_active=True).order_by('name')
        self.fields['party'].label_from_instance = lambda p: f"{p.name} ({p.get_party_type_display()}) — ₨{abs(p.current_balance):,.0f}"

        optional = ['cheque_number', 'cheque_date', 'transaction_ref', 'narration', 'attachment',
                     'bank_account', 'paid_by', 'received_by_us', 'receipt_number',
                     'cash_received_date', 'cash_received_time',
                     'sender_bank_name', 'sender_account_title',
                     'sender_account_number', 'sender_iban']
        for f in optional:
            self.fields[f].required = False

        self.fields['bank_account'].queryset = BankAccount.objects.filter(is_active=True, owner_type='own')
        self.fields['bank_account'].empty_label = '— Select Our Bank Account — ہمارا بینک اکاؤنٹ —'
        self.fields['bank_account'].label_from_instance = lambda ba: f"{ba.bank_name} — {ba.account_number} (₨{ba.current_balance:,.0f})"

        # Redirect to party — show balance so user knows who they owe
        def redirect_label(p):
            bal = p.current_balance
            if bal < 0:
                return f"{p.name} — Payable ₨{abs(bal):,.0f}"
            elif bal > 0:
                return f"{p.name} — Receivable ₨{bal:,.0f}"
            return f"{p.name} — Balance: ₨0"
        self.fields['redirect_to_party'].label_from_instance = redirect_label

        urdu = {
            'date': 'تاریخ', 'party': 'کس سے وصولی', 'amount': 'رقم',
            'narration': 'تفصیل', 'paid_by': 'کس نے ادا کیا',
            'received_by_us': 'ہم نے کس سے لیا', 'receipt_number': 'رسید نمبر',
            'cash_received_date': 'نقد ملنے کی تاریخ', 'cash_received_time': 'نقد ملنے کا وقت',
            'bank_account': 'ہمارا بینک اکاؤنٹ',
            'sender_bank_name': 'ان کا بینک', 'sender_account_title': 'اکاؤنٹ ٹائٹل',
            'sender_account_number': 'اکاؤنٹ نمبر', 'sender_iban': 'آئی بی اے این',
            'cheque_number': 'چیک نمبر', 'cheque_date': 'چیک تاریخ',
            'transaction_ref': 'ریفرنس نمبر',
            'redirect_to_party': 'ادائیگی بھیجیں',
        }
        for fn, f in self.fields.items():
            f.urdu_label = urdu.get(fn, '')

    def save(self, commit=True):
        instance = super().save(commit=False)
        ba = instance.bank_account
        if ba:
            instance.bank_name = f"{ba.bank_name} — {ba.account_number}"
        if commit:
            instance.save()
        return instance

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero — رقم صفر سے زیادہ ہونی چاہیے')
        return amount

    def is_valid(self):
        r = super().is_valid()
        if not r: _mark(self)
        return r


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['date', 'category', 'amount', 'paid_to', 'payment_method', 'description', 'receipt_image', 'is_recurring', 'recurrence']
        widgets = {
            'date': forms.DateInput(attrs={'class': I, 'style': I_STYLE, 'type': 'date'}),
            'category': forms.Select(attrs={'class': I, 'style': I_STYLE + 'background:white;'}),
            'amount': forms.NumberInput(attrs={'class': I_BIG, 'style': I_STYLE + 'font-size:24px;font-weight:700;text-align:center;', 'step': '0.01', 'min': '0', 'placeholder': '0'}),
            'paid_to': forms.TextInput(attrs={'class': I, 'style': I_STYLE, 'placeholder': 'e.g., WAPDA, Mechanic name, etc.'}),
            'payment_method': forms.Select(attrs={'class': I, 'style': I_STYLE + 'background:white;'}),
            'description': forms.Textarea(attrs={'class': I, 'style': I_STYLE + 'resize:vertical;', 'rows': 2, 'placeholder': 'Details of expense...'}),
            'receipt_image': forms.FileInput(attrs={'class': I, 'style': I_STYLE}),
            'is_recurring': forms.CheckboxInput(attrs={'style': 'width:18px;height:18px;accent-color:#10b981;cursor:pointer;'}),
            'recurrence': forms.Select(attrs={'class': I, 'style': I_STYLE + 'background:white;'}),
        }
        labels = {'paid_to': 'Paid To', 'receipt_image': 'Receipt Photo'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ['paid_to', 'description', 'receipt_image', 'is_recurring', 'recurrence']:
            self.fields[f].required = False
        urdu = {'date': 'تاریخ', 'category': 'قسم', 'amount': 'رقم', 'paid_to': 'کسے ادائیگی',
                'payment_method': 'طریقہ', 'description': 'تفصیل', 'receipt_image': 'رسید تصویر'}
        for fn, f in self.fields.items():
            f.urdu_label = urdu.get(fn, '')


    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero — رقم صفر سے زیادہ ہونی چاہیے')
        return amount
    def is_valid(self):
        r = super().is_valid()
        if not r: _mark(self)
        return r


class CrossPartyAdjustmentForm(forms.ModelForm):
    we_owe_them = forms.BooleanField(
        required=False, initial=True,
        label='This is a Payable — واجب الادا ہے',
        widget=forms.CheckboxInput(attrs={'style': 'width:18px;height:18px;accent-color:#7c3aed;cursor:pointer;'}),
    )
    payment_method = forms.ChoiceField(
        choices=[
            ('cash', 'Cash (نقد)'),
            ('bank', 'Bank Transfer (بینک)'),
            ('cheque', 'Cheque (چیک)'),
            ('online', 'Online / JazzCash / EasyPaisa'),
            ('adjustment', 'Book Adjustment Only (صرف کھاتے)'),
        ],
        initial='cash',
        widget=forms.Select(attrs={'class': I, 'style': I_STYLE + 'background:white;'}),
        label='Payment Method — طریقہ',
    )
    class Meta:
        model = __import__('apps.finance.models', fromlist=['CrossPartyAdjustment']).CrossPartyAdjustment
        fields = ['date', 'from_party', 'to_party', 'amount', 'narration']
        widgets = {
            'date': forms.DateInput(attrs={'class': I, 'style': I_STYLE, 'type': 'date'}),
            'from_party': forms.Select(attrs={'class': I, 'style': I_STYLE + 'background:white;'}),
            'to_party': forms.Select(attrs={'class': I, 'style': I_STYLE + 'background:white;'}),
            'amount': forms.NumberInput(attrs={
                'class': I_BIG,
                'style': I_STYLE + 'font-size:24px;font-weight:700;text-align:center;',
                'step': '0.01', 'min': '0', 'placeholder': '0'
            }),
            'narration': forms.Textarea(attrs={
                'class': I, 'style': I_STYLE + 'resize:vertical;', 'rows': 2,
                'placeholder': 'e.g., Party A paid Party B on our behalf — پارٹی اے نے پارٹی بی کو براہ راست ادا کیا'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['from_party'].queryset = Party.objects.filter(is_active=True).order_by('name')
        self.fields['to_party'].queryset = Party.objects.filter(is_active=True).order_by('name')
        self.fields['from_party'].empty_label = '— Select Party — پارٹی منتخب کریں —'
        self.fields['to_party'].empty_label = '— Select Party — پارٹی منتخب کریں —'

        def party_label(p):
            bal = p.current_balance
            if bal > 0:
                return f"{p.name} — Receivable ₨{bal:,.0f}"
            elif bal < 0:
                return f"{p.name} — Payable ₨{abs(bal):,.0f}"
            return f"{p.name} — Balance: ₨0"

        self.fields['from_party'].label_from_instance = party_label
        self.fields['to_party'].label_from_instance = party_label
        self.fields['narration'].required = False

        urdu = {
            'date': 'تاریخ', 'direction': 'قسم', 'from_party': 'جس کے کھاتے سے',
            'to_party': 'جس کے کھاتے میں', 'amount': 'رقم', 'narration': 'تفصیل',
            'payment_method': 'طریقہ', 'we_owe_them': 'ہم مقروض ہیں',
        }
        for fn, f in self.fields.items():
            f.urdu_label = urdu.get(fn, '')

    def clean(self):
        cleaned = super().clean()
        from_p = cleaned.get('from_party')
        to_p = cleaned.get('to_party')
        if from_p and to_p and from_p == to_p:
            raise forms.ValidationError('From Party and To Party cannot be the same — دونوں پارٹی ایک نہیں ہو سکتیں')
        return cleaned

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero — رقم صفر سے زیادہ ہونی چاہیے')
        return amount

    def is_valid(self):
        r = super().is_valid()
        if not r: _mark(self)
        return r
