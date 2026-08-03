from django import forms
from .models import Worker, WorkerPayment

I = ('w-full px-4 py-3 rounded-xl text-sm transition-all duration-200 outline-none '
     'bg-white border-2 border-gray-200 hover:border-gray-300 '
     'focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 placeholder:text-gray-400')

def _mark(form):
    for fn in form.errors:
        if fn in form.fields:
            w = form.fields[fn].widget
            w.attrs['class'] = w.attrs.get('class','').replace('border-gray-200','border-red-400').replace('bg-white','bg-red-50/50')


class WorkerForm(forms.ModelForm):
    class Meta:
        model = Worker
        fields = ['name', 'name_urdu', 'cnic', 'phone', 'worker_type', 'department',
                  'daily_wage', 'monthly_salary', 'joining_date',
                  'contract_amount', 'contract_start', 'contract_end', 'contract_description',
                  'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': I, 'placeholder': 'Worker name — مزدور کا نام'}),
            'name_urdu': forms.TextInput(attrs={'class': I, 'dir': 'rtl', 'placeholder': 'اردو نام'}),
            'cnic': forms.TextInput(attrs={'class': I, 'placeholder': 'XXXXX-XXXXXXX-X'}),
            'phone': forms.TextInput(attrs={'class': I, 'placeholder': '03XX-XXXXXXX'}),
            'worker_type': forms.Select(attrs={'class': I, 'x-model': 'workerType', '@change': 'workerType=$event.target.value'}),
            'department': forms.Select(attrs={'class': I}),
            'daily_wage': forms.NumberInput(attrs={'class': I + ' text-lg font-bold', 'step': '0.01', 'min': '0', 'placeholder': '0'}),
            'monthly_salary': forms.NumberInput(attrs={'class': I + ' text-lg font-bold', 'step': '0.01', 'min': '0', 'placeholder': '0'}),
            'joining_date': forms.DateInput(attrs={'class': I, 'type': 'date'}),
            'contract_amount': forms.NumberInput(attrs={'class': I + ' text-lg font-bold', 'step': '0.01', 'min': '0', 'placeholder': '0'}),
            'contract_start': forms.DateInput(attrs={'class': I, 'type': 'date'}),
            'contract_end': forms.DateInput(attrs={'class': I, 'type': 'date'}),
            'contract_description': forms.Textarea(attrs={'class': I, 'rows': 2, 'placeholder': 'What work is contracted — ٹھیکے کا کام'}),
            'address': forms.Textarea(attrs={'class': I, 'rows': 2}),
        }
        labels = {
            'name': 'Worker Name',
            'daily_wage': 'Daily Wage (₨)',
            'monthly_salary': 'Monthly Salary (₨)',
            'contract_amount': 'Contract Amount (₨)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # All optional except name and worker_type
        for f in ['name_urdu', 'cnic', 'phone', 'daily_wage', 'monthly_salary',
                  'joining_date', 'contract_amount', 'contract_start', 'contract_end',
                  'contract_description', 'address']:
            self.fields[f].required = False
        urdu = {
            'name': 'نام', 'worker_type': 'قسم', 'department': 'شعبہ',
            'daily_wage': 'روزانہ اجرت', 'monthly_salary': 'ماہانہ تنخواہ',
            'joining_date': 'شمولیت کی تاریخ', 'contract_amount': 'ٹھیکے کی رقم',
            'contract_start': 'آغاز', 'contract_end': 'اختتام',
        }
        for fn, f in self.fields.items():
            f.urdu_label = urdu.get(fn, '')

    def is_valid(self):
        r = super().is_valid()
        if not r: _mark(self)
        return r


class WorkerPaymentForm(forms.ModelForm):
    class Meta:
        model = WorkerPayment
        fields = ['worker', 'date', 'days_worked', 'gross_amount', 'advance_deducted', 'net_amount', 'narration']
        widgets = {
            'worker': forms.Select(attrs={'class': I}),
            'date': forms.DateInput(attrs={'class': I, 'type': 'date'}),
            'days_worked': forms.NumberInput(attrs={'class': I + ' text-center font-bold'}),
            'gross_amount': forms.NumberInput(attrs={'class': I + ' text-center font-bold', 'step': '0.01'}),
            'advance_deducted': forms.NumberInput(attrs={'class': I + ' text-center', 'step': '0.01'}),
            'net_amount': forms.NumberInput(attrs={'class': I + ' text-2xl font-bold text-center', 'step': '0.01'}),
            'narration': forms.Textarea(attrs={'class': I, 'rows': 2}),
        }
        labels = {'net_amount': 'Net Amount (خالص رقم)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['worker'].queryset = Worker.objects.filter(is_active=True)
        self.fields['narration'].required = False
        self.fields['advance_deducted'].required = False
        for fn, f in self.fields.items():
            f.urdu_label = {'worker':'مزدور','date':'تاریخ','net_amount':'خالص رقم'}.get(fn, '')

    def is_valid(self):
        r = super().is_valid()
        if not r: _mark(self)
        return r
