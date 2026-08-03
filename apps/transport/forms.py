from django import forms
from .models import Vehicle, FreightEntry, GateEntry
from apps.parties.models import Party

I = ('w-full px-4 py-3 rounded-xl text-sm transition-all duration-200 outline-none '
     'bg-white border-2 border-gray-200 hover:border-gray-300 '
     'focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 placeholder:text-gray-400')

def _mark(form):
    for fn in form.errors:
        if fn in form.fields:
            w = form.fields[fn].widget
            w.attrs['class'] = w.attrs.get('class','').replace('border-gray-200','border-red-400').replace('bg-white','bg-red-50/50')


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['vehicle_number', 'vehicle_type', 'owner', 'capacity_maund',
                  'chassis_number', 'station_name',
                  'driver_name', 'driver_phone', 'driver_cnic', 'driver_license', 'bilty_number']
        widgets = {
            'vehicle_number': forms.TextInput(attrs={'class': I, 'placeholder': 'LEA-1234'}),
            'vehicle_type': forms.Select(attrs={'class': I}),
            'owner': forms.Select(attrs={'class': I}),
            'capacity_maund': forms.NumberInput(attrs={'class': I, 'step': '0.01'}),
            'chassis_number': forms.TextInput(attrs={'class': I, 'placeholder': 'Chassis / Engine number'}),
            'station_name': forms.TextInput(attrs={'class': I, 'placeholder': 'Adda / Station name'}),
            'driver_name': forms.TextInput(attrs={'class': I}),
            'driver_phone': forms.TextInput(attrs={'class': I, 'placeholder': '03XX XXXXXXX'}),
            'driver_cnic': forms.TextInput(attrs={'class': I, 'placeholder': 'XXXXX-XXXXXXX-X'}),
            'driver_license': forms.TextInput(attrs={'class': I, 'placeholder': 'License number'}),
            'bilty_number': forms.TextInput(attrs={'class': I, 'placeholder': 'Bilty / Builty number'}),
        }
        labels = {'vehicle_number': 'Vehicle Number', 'capacity_maund': 'Capacity (Maund)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['owner'].queryset = Party.objects.filter(party_type='transporter', is_active=True)
        self.fields['owner'].required = False
        for f in ['capacity_maund','chassis_number','station_name','driver_name','driver_phone','driver_cnic','driver_license','bilty_number']:
            self.fields[f].required = False
        urdu = {'vehicle_number':'گاڑی نمبر','vehicle_type':'قسم','driver_name':'ڈرائیور کا نام',
                'driver_phone':'ڈرائیور فون','driver_cnic':'ڈرائیور شناختی کارڈ','driver_license':'لائسنس نمبر',
                'chassis_number':'چیسس نمبر','station_name':'اسٹیشن/اڈا','capacity_maund':'گنجائش (من)',
                'bilty_number':'بلٹی نمبر'}
        for fn, f in self.fields.items():
            f.urdu_label = urdu.get(fn, '')

    def is_valid(self):
        r = super().is_valid()
        if not r: _mark(self)
        return r


class FreightForm(forms.ModelForm):
    class Meta:
        model = FreightEntry
        fields = ['date', 'vehicle', 'transporter', 'from_location', 'to_location',
                  'rate_type', 'rate', 'quantity', 'narration']
        widgets = {
            'date': forms.DateInput(attrs={'class': I, 'type': 'date'}),
            'vehicle': forms.Select(attrs={'class': I}),
            'transporter': forms.Select(attrs={'class': I}),
            'from_location': forms.TextInput(attrs={'class': I}),
            'to_location': forms.TextInput(attrs={'class': I}),
            'rate_type': forms.Select(attrs={'class': I}),
            'rate': forms.NumberInput(attrs={'class': I, 'step': '0.01'}),
            'quantity': forms.NumberInput(attrs={'class': I, 'step': '0.01'}),
            'narration': forms.Textarea(attrs={'class': I, 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vehicle'].queryset = Vehicle.objects.filter(is_active=True)
        self.fields['vehicle'].required = False
        self.fields['transporter'].queryset = Party.objects.filter(party_type='transporter', is_active=True)
        for f in ['from_location','to_location','narration','rate','quantity']:
            self.fields[f].required = False
        for fn, f in self.fields.items():
            f.urdu_label = {'date':'تاریخ','transporter':'ٹرانسپورٹر','rate':'نرخ'}.get(fn, '')

    def is_valid(self):
        r = super().is_valid()
        if not r: _mark(self)
        return r


class GateEntryForm(forms.ModelForm):
    class Meta:
        model = GateEntry
        fields = ['vehicle_number', 'driver_name', 'purpose', 'gross_weight', 'tare_weight', 'notes']
        widgets = {
            'vehicle_number': forms.TextInput(attrs={'class': I, 'placeholder': 'Vehicle number'}),
            'driver_name': forms.TextInput(attrs={'class': I}),
            'purpose': forms.Select(attrs={'class': I}),
            'gross_weight': forms.NumberInput(attrs={'class': I, 'step': '0.001'}),
            'tare_weight': forms.NumberInput(attrs={'class': I, 'step': '0.001'}),
            'notes': forms.Textarea(attrs={'class': I, 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ['driver_name','gross_weight','tare_weight','notes']:
            self.fields[f].required = False
        for fn, f in self.fields.items():
            f.urdu_label = {'vehicle_number':'گاڑی نمبر','purpose':'مقصد'}.get(fn, '')

    def is_valid(self):
        r = super().is_valid()
        if not r: _mark(self)
        return r
