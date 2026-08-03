"""
Party Management Forms — Smart validation.
"""
from django import forms
from .models import Party

I = ('w-full px-4 py-3 rounded-xl text-sm transition-all duration-200 outline-none '
     'bg-white border-2 border-gray-200 hover:border-gray-300 '
     'focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 placeholder:text-gray-400')
CHK = 'w-5 h-5 text-emerald-600 rounded-lg border-2 border-gray-300 focus:ring-emerald-500 cursor-pointer'


def _mark_errors(form):
    for fname in form.errors:
        if fname in form.fields:
            w = form.fields[fname].widget
            cls = w.attrs.get('class', '')
            w.attrs['class'] = cls.replace('border-gray-200', 'border-red-400').replace('bg-white', 'bg-red-50/50')


class PartyForm(forms.ModelForm):
    class Meta:
        model = Party
        fields = [
            'name', 'name_urdu', 'code', 'party_type', 'company_name',
            'cnic', 'ntn_number', 'sales_tax_number', 'is_filer',
            'phone_primary', 'phone_secondary', 'whatsapp', 'email',
            'street_address', 'city', 'district', 'province', 'country',
            'opening_balance', 'opening_balance_type', 'opening_balance_date',
            'credit_limit', 'credit_days', 'commission_rate',
            'bank_name', 'account_title', 'account_number', 'iban', 'bank_branch',
            'is_active', 'notes',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': I, 'placeholder': 'Full name or business name'}),
            'name_urdu': forms.TextInput(attrs={'class': I, 'placeholder': 'مکمل نام', 'dir': 'rtl'}),
            'code': forms.TextInput(attrs={'class': I, 'placeholder': 'Auto-generated if blank'}),
            'party_type': forms.Select(attrs={'class': I, 'x-model': 'partyType'}),
            'company_name': forms.TextInput(attrs={'class': I}),
            'cnic': forms.TextInput(attrs={'class': I, 'placeholder': 'XXXXX-XXXXXXX-X'}),
            'ntn_number': forms.TextInput(attrs={'class': I}),
            'sales_tax_number': forms.TextInput(attrs={'class': I}),
            'is_filer': forms.CheckboxInput(attrs={'class': CHK}),
            'phone_primary': forms.TextInput(attrs={'class': I, 'placeholder': '03XX XXXXXXX'}),
            'phone_secondary': forms.TextInput(attrs={'class': I}),
            'whatsapp': forms.TextInput(attrs={'class': I, 'placeholder': '03XX XXXXXXX'}),
            'email': forms.EmailInput(attrs={'class': I}),
            'street_address': forms.Textarea(attrs={'class': I, 'rows': 2}),
            'city': forms.TextInput(attrs={'class': I}),
            'district': forms.TextInput(attrs={'class': I}),
            'province': forms.Select(attrs={'class': I}),
            'country': forms.TextInput(attrs={'class': I}),
            'opening_balance': forms.NumberInput(attrs={'class': I, 'step': '0.01', 'min': '0'}),
            'opening_balance_type': forms.Select(attrs={'class': I}),
            'opening_balance_date': forms.DateInput(attrs={'class': I, 'type': 'date'}),
            'credit_limit': forms.NumberInput(attrs={'class': I, 'step': '0.01'}),
            'credit_days': forms.NumberInput(attrs={'class': I}),
            'commission_rate': forms.NumberInput(attrs={'class': I, 'step': '0.01'}),
            'bank_name': forms.TextInput(attrs={'class': I}),
            'account_title': forms.TextInput(attrs={'class': I}),
            'account_number': forms.TextInput(attrs={'class': I}),
            'iban': forms.TextInput(attrs={'class': I, 'placeholder': 'PK00XXXX...'}),
            'bank_branch': forms.TextInput(attrs={'class': I}),
            'is_active': forms.CheckboxInput(attrs={'class': CHK}),
            'notes': forms.Textarea(attrs={'class': I, 'rows': 2}),
        }
        labels = {
            'name': 'Party Name',
            'name_urdu': 'Name (Urdu)',
            'party_type': 'Party Type',
            'company_name': 'Company / Business',
            'phone_primary': 'Primary Phone',
            'phone_secondary': 'Secondary Phone',
            'opening_balance': 'Opening Balance',
            'opening_balance_type': 'Balance Type',
            'opening_balance_date': 'Balance Date',
            'credit_limit': 'Credit Limit (₨)',
            'credit_days': 'Credit Days',
            'commission_rate': 'Commission %',
            'street_address': 'Address',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only name and party_type are truly required
        self.fields['code'].required = False
        self.fields['opening_balance_date'].required = False
        # Make all optional fields explicitly not required
        optional = [
            'name_urdu', 'company_name', 'cnic', 'ntn_number', 'sales_tax_number',
            'phone_primary', 'phone_secondary', 'whatsapp', 'email',
            'street_address', 'city', 'district', 'province', 'country',
            'opening_balance', 'opening_balance_type', 'opening_balance_date',
            'credit_limit', 'credit_days', 'commission_rate',
            'bank_name', 'account_title', 'account_number', 'iban', 'bank_branch',
            'notes',
        ]
        for fname in optional:
            if fname in self.fields:
                self.fields[fname].required = False

        # Urdu labels
        urdu = {'name': 'نام', 'party_type': 'قسم', 'phone_primary': 'فون',
                'city': 'شہر', 'opening_balance': 'ابتدائی بیلنس',
                'credit_limit': 'ادھار حد', 'cnic': 'شناختی کارڈ'}
        for fname, f in self.fields.items():
            f.urdu_label = urdu.get(fname, '')

    def clean(self):
        cleaned = super().clean()
        code = cleaned.get('code')
        if not code:
            party_type = cleaned.get('party_type', 'other')
            cleaned['code'] = Party.generate_code(party_type)
        # Default country to Pakistan if not provided
        if not cleaned.get('country'):
            cleaned['country'] = 'Pakistan'
        return cleaned

    def clean_cnic(self):
        cnic = self.cleaned_data.get('cnic', '').strip()
        if cnic:
            clean = cnic.replace('-', '')
            if len(clean) != 13 or not clean.isdigit():
                raise forms.ValidationError(
                    'CNIC must be 13 digits — شناختی کارڈ 13 ہندسوں کا ہونا چاہیے'
                )
        return cnic

    def is_valid(self):
        r = super().is_valid()
        if not r: _mark_errors(self)
        return r
