"""
Transport / Freight Management.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class Vehicle(models.Model):
    TYPE_CHOICES = [
        ('truck', 'Truck (ٹرک)'),
        ('tractor', 'Tractor Trolley (ٹریکٹر ٹرالی)'),
        ('pickup', 'Pickup (پک اپ)'),
        ('other', 'Other (دیگر)'),
    ]
    vehicle_number = models.CharField(max_length=30, unique=True)
    vehicle_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='truck')
    owner = models.ForeignKey('parties.Party', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='vehicles', limit_choices_to={'party_type': 'transporter'})
    capacity_maund = models.DecimalField('Capacity (Maund)', max_digits=10, decimal_places=2, default=0)
    chassis_number = models.CharField('Chassis No', max_length=50, blank=True)
    station_name = models.CharField('Station / Adda', max_length=100, blank=True)
    driver_name = models.CharField(max_length=100, blank=True)
    driver_phone = models.CharField(max_length=20, blank=True)
    driver_cnic = models.CharField('Driver CNIC', max_length=15, blank=True)
    driver_license = models.CharField('Driver License No', max_length=30, blank=True)
    bilty_number = models.CharField('Bilty Number', max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vehicles'
        ordering = ['vehicle_number']

    def __str__(self):
        return f"{self.vehicle_number} ({self.get_vehicle_type_display()})"


class FreightEntry(models.Model):
    """Per-trip freight tracking."""
    RATE_TYPE_CHOICES = [
        ('per_maund', 'Per Maund'),
        ('per_trip', 'Per Trip (فی ٹرپ)'),
        ('per_km', 'Per KM'),
    ]
    date = models.DateField(default=timezone.now)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name='freight_entries')
    transporter = models.ForeignKey('parties.Party', on_delete=models.PROTECT, related_name='freight_entries',
                                     limit_choices_to={'party_type': 'transporter'})
    from_location = models.CharField(max_length=200, blank=True)
    to_location = models.CharField(max_length=200, blank=True)
    rate_type = models.CharField(max_length=10, choices=RATE_TYPE_CHOICES, default='per_trip')
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    total_freight = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Link to purchase or sale
    purchase = models.ForeignKey('purchases.Purchase', on_delete=models.SET_NULL, null=True, blank=True)
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True)

    is_paid = models.BooleanField(default=False)
    narration = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'freight_entries'
        ordering = ['-date']

    def __str__(self):
        return f"{self.date} — {self.transporter.name} — ₨{self.total_freight}"

    def save(self, *args, **kwargs):
        self.total_freight = self.rate * self.quantity
        super().save(*args, **kwargs)


class GateEntry(models.Model):
    """Vehicle entry/exit log at factory gate."""
    vehicle_number = models.CharField(max_length=30)
    driver_name = models.CharField(max_length=100, blank=True)
    time_in = models.DateTimeField(default=timezone.now)
    time_out = models.DateTimeField(null=True, blank=True)
    purpose = models.CharField(max_length=20, choices=[
        ('purchase', 'Purchase Delivery'),
        ('sale', 'Sale Dispatch'),
        ('other', 'Other'),
    ], default='purchase')
    purchase = models.ForeignKey('purchases.Purchase', on_delete=models.SET_NULL, null=True, blank=True)
    sale = models.ForeignKey('sales.Sale', on_delete=models.SET_NULL, null=True, blank=True)
    gross_weight = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    tare_weight = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    net_weight = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gate_entries'
        ordering = ['-time_in']

    def __str__(self):
        return f"{self.vehicle_number} — {self.time_in.strftime('%d/%m %H:%M')}"

    def save(self, *args, **kwargs):
        if self.gross_weight and self.tare_weight:
            self.net_weight = self.gross_weight - self.tare_weight
        super().save(*args, **kwargs)
