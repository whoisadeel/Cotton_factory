from django import forms
from .models import GinningLot
from apps.products.models import Product, UnitOfMeasurement

I = ('w-full px-4 py-3 rounded-xl text-sm transition-all duration-200 outline-none '
     'bg-white border-2 border-gray-200 hover:border-gray-300 '
     'focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 placeholder:text-gray-400')

def _mark(form):
    for fn in form.errors:
        if fn in form.fields:
            w = form.fields[fn].widget
            w.attrs['class'] = w.attrs.get('class','').replace('border-gray-200','border-red-400').replace('bg-white','bg-red-50/50')


class GinningLotForm(forms.ModelForm):
    class Meta:
        model = GinningLot
        fields = ['date', 'input_product', 'input_quantity', 'input_unit', 'source_purchase', 'machine_number', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'class': I, 'type': 'date'}),
            'input_product': forms.Select(attrs={'class': I}),
            'input_quantity': forms.NumberInput(attrs={'class': I + ' text-lg font-bold text-center', 'step': '0.001'}),
            'input_unit': forms.Select(attrs={'class': I}),
            'source_purchase': forms.Select(attrs={'class': I}),
            'machine_number': forms.TextInput(attrs={'class': I}),
            'notes': forms.Textarea(attrs={'class': I, 'rows': 2}),
        }
        labels = {
            'input_product': 'Raw Cotton / Input (پھٹی / خام مال)',
            'input_quantity': 'Quantity (مقدار)',
            'input_unit': 'Unit of Measurement (اکائی)',
            'source_purchase': 'From Purchase — optional (خریداری سے — اختیاری)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow ANY product to be used as input (not just PHUTTI category)
        self.fields['input_product'].queryset = Product.objects.filter(status='active')
        self.fields['input_unit'].queryset = UnitOfMeasurement.objects.filter(is_active=True)
        from apps.purchases.models import Purchase
        self.fields['source_purchase'].queryset = Purchase.objects.filter(status='final').select_related('supplier').order_by('-date')[:50]
        self.fields['source_purchase'].empty_label = '— Optional: link to purchase — اختیاری —'
        self.fields['machine_number'].required = False
        self.fields['notes'].required = False
        self.fields['source_purchase'].required = False
        for fn, f in self.fields.items():
            f.urdu_label = {'date':'تاریخ','input_product':'پھٹی / خام مال','input_quantity':'مقدار',
                            'input_unit':'اکائی','source_purchase':'منسلک خریداری'}.get(fn, '')

    def is_valid(self):
        r = super().is_valid()
        if not r: _mark(self)
        return r
