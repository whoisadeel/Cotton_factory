"""
Product & Category Forms — Smart validation with clear error messages.
"""
from django import forms
from .models import Category, Product, UnitOfMeasurement

# Shared styling
I = ('w-full px-4 py-3 rounded-xl text-sm transition-all duration-200 outline-none '
     'bg-white border-2 border-gray-200 hover:border-gray-300 '
     'focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 placeholder:text-gray-400')
IE = I.replace('border-gray-200', 'border-red-400').replace('bg-white', 'bg-red-50/50')
CHK = 'w-5 h-5 text-emerald-600 rounded-lg border-2 border-gray-300 focus:ring-emerald-500 cursor-pointer'


def _mark_errors(form):
    """Replace border classes on errored fields."""
    for fname in form.errors:
        if fname in form.fields:
            w = form.fields[fname].widget
            cls = w.attrs.get('class', '')
            w.attrs['class'] = cls.replace('border-gray-200', 'border-red-400').replace('bg-white', 'bg-red-50/50')


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'name_urdu', 'code', 'description', 'parent', 'is_active', 'sort_order']
        widgets = {
            'name': forms.TextInput(attrs={'class': I, 'placeholder': 'e.g., Raw Cotton'}),
            'name_urdu': forms.TextInput(attrs={'class': I, 'placeholder': 'مثلاً کچی روئی', 'dir': 'rtl'}),
            'code': forms.TextInput(attrs={'class': I, 'placeholder': 'e.g., COTTON'}),
            'description': forms.Textarea(attrs={'class': I, 'rows': 2}),
            'parent': forms.Select(attrs={'class': I}),
            'is_active': forms.CheckboxInput(attrs={'class': CHK}),
            'sort_order': forms.NumberInput(attrs={'class': I}),
        }
        labels = {
            'name': 'Category Name',
            'name_urdu': 'Name (Urdu)',
            'code': 'Code',
            'description': 'Description',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sort_order'].required = False
        self.fields['sort_order'].initial = 0
        for f in self.fields.values():
            if not hasattr(f, 'urdu_label'):
                f.urdu_label = ''
        self.fields['name'].urdu_label = 'زمرے کا نام'
        self.fields['code'].urdu_label = 'کوڈ'

    def clean_sort_order(self):
        val = self.cleaned_data.get('sort_order')
        if val is None:
            return 0
        return val

    def is_valid(self):
        r = super().is_valid()
        if not r: _mark_errors(self)
        return r


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'name_urdu', 'code', 'category', 'unit', 'source',
            'default_purchase_price', 'default_sale_price',
            'minimum_stock', 'hsn_code', 'description', 'status',
            'default_moisture_pct', 'default_trash_pct', 'acceptable_loss_pct',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': I, 'placeholder': 'e.g., Raw Cotton (Phutti)'}),
            'name_urdu': forms.TextInput(attrs={'class': I, 'placeholder': 'مثلاً پھٹی', 'dir': 'rtl'}),
            'code': forms.TextInput(attrs={'class': I, 'placeholder': 'Leave blank for auto'}),
            'category': forms.Select(attrs={'class': I}),
            'unit': forms.Select(attrs={'class': I}),
            'source': forms.Select(attrs={'class': I}),
            'default_purchase_price': forms.NumberInput(attrs={'class': I, 'step': '0.01', 'min': '0'}),
            'default_sale_price': forms.NumberInput(attrs={'class': I, 'step': '0.01', 'min': '0'}),
            'minimum_stock': forms.NumberInput(attrs={'class': I, 'step': '0.001', 'min': '0'}),
            'hsn_code': forms.TextInput(attrs={'class': I}),
            'description': forms.Textarea(attrs={'class': I, 'rows': 2}),
            'status': forms.Select(attrs={'class': I}),
            'default_moisture_pct': forms.NumberInput(attrs={'class': I, 'step': '0.01'}),
            'default_trash_pct': forms.NumberInput(attrs={'class': I, 'step': '0.01'}),
            'acceptable_loss_pct': forms.NumberInput(attrs={'class': I, 'step': '0.01'}),
        }
        labels = {
            'name': 'Product Name',
            'name_urdu': 'Name (Urdu)',
            'code': 'Product Code',
            'category': 'Category',
            'unit': 'Unit of Measurement',
            'default_purchase_price': 'Purchase Price (₨)',
            'default_sale_price': 'Sale Price (₨)',
            'minimum_stock': 'Minimum Stock Level',
            'hsn_code': 'HSN / Product Code',
            'description': 'Description / Notes',
            'status': 'Status',
            'default_moisture_pct': 'Default Moisture %',
            'default_trash_pct': 'Default Trash %',
            'acceptable_loss_pct': 'Acceptable Loss %',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(is_active=True)
        self.fields['unit'].queryset = UnitOfMeasurement.objects.filter(is_active=True)
        self.fields['code'].required = False
        # These have defaults — don't force user to fill them
        for f in ['default_purchase_price', 'default_sale_price', 'minimum_stock',
                  'default_moisture_pct', 'default_trash_pct', 'acceptable_loss_pct',
                  'hsn_code', 'name_urdu', 'description']:
            self.fields[f].required = False

        # Urdu labels
        urdu = {'name': 'پروڈکٹ کا نام', 'category': 'زمرہ', 'unit': 'اکائی', 'source': 'ذریعہ',
                'default_purchase_price': 'خرید قیمت', 'default_sale_price': 'فروخت قیمت',
                'minimum_stock': 'کم از کم اسٹاک', 'status': 'حالت'}
        for fname, f in self.fields.items():
            f.urdu_label = urdu.get(fname, '')

    def clean(self):
        cleaned = super().clean()
        code = cleaned.get('code')
        if not code:
            cat = cleaned.get('category')
            if cat:
                cleaned['code'] = Product.generate_code(cat.code)
            else:
                cleaned['code'] = Product.generate_code('PROD')
        return cleaned

    def is_valid(self):
        r = super().is_valid()
        if not r: _mark_errors(self)
        return r


class UnitForm(forms.ModelForm):
    class Meta:
        model = UnitOfMeasurement
        fields = ['name', 'name_urdu', 'abbreviation', 'unit_type',
                  'conversion_to_base', 'is_active', 'sort_order']
        widgets = {
            'name': forms.TextInput(attrs={'class': I, 'placeholder': 'e.g., Bag (Khal)'}),
            'name_urdu': forms.TextInput(attrs={'class': I, 'dir': 'rtl', 'placeholder': 'مثلاً بوری (کھل)'}),
            'abbreviation': forms.TextInput(attrs={'class': I, 'placeholder': 'e.g., KHAL-BAG'}),
            'unit_type': forms.Select(attrs={'class': I}),
            'conversion_to_base': forms.NumberInput(attrs={'class': I, 'step': '0.001', 'min': '0.001',
                                                           'placeholder': 'e.g., 56 (meaning 1 bag = 56 KG)'}),
            'is_active': forms.CheckboxInput(attrs={'class': CHK}),
            'sort_order': forms.NumberInput(attrs={'class': I, 'placeholder': '0'}),
        }
        labels = {
            'name': 'Unit Name',
            'name_urdu': 'Name (Urdu)',
            'abbreviation': 'Short Code',
            'unit_type': 'Unit Type',
            'conversion_to_base': 'How many KG in 1 unit?',
            'is_active': 'Active',
            'sort_order': 'Sort Order',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # sort_order is optional — default to 0
        self.fields['sort_order'].required = False
        self.fields['sort_order'].initial = 0
        # name_urdu is optional
        self.fields['name_urdu'].required = False
        # conversion_to_base must be > 0
        self.fields['conversion_to_base'].help_text = (
            'For weight units: how many KG in 1 of this unit. '
            'E.g. Maund=40, Bag Khal=56, Bag Phutti=85'
        )
        # Urdu labels
        urdu = {
            'name': 'اکائی کا نام',
            'name_urdu': 'اردو نام',
            'abbreviation': 'مختصر کوڈ',
            'unit_type': 'قسم',
            'conversion_to_base': 'ایک اکائی میں کتنے کلوگرام',
            'is_active': 'فعال',
            'sort_order': 'ترتیب نمبر',
        }
        for fname, f in self.fields.items():
            f.urdu_label = urdu.get(fname, '')

    def clean_sort_order(self):
        val = self.cleaned_data.get('sort_order')
        if val is None:
            return 0
        return val

    def clean_conversion_to_base(self):
        val = self.cleaned_data.get('conversion_to_base')
        if val is not None and val <= 0:
            raise forms.ValidationError('Must be greater than 0 — صفر سے زیادہ ہونا ضروری ہے')
        return val

    def is_valid(self):
        r = super().is_valid()
        if not r: _mark_errors(self)
        return r
