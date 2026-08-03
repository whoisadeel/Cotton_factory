"""
Labour / Worker Management — Workers, attendance, wages.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class Worker(models.Model):
    TYPE_CHOICES = [
        ('permanent', 'Permanent (مستقل)'),
        ('daily', 'Daily Wage (روزانہ)'),
        ('contract', 'Contract (ٹھیکہ)'),
    ]
    DEPARTMENT_CHOICES = [
        ('ginning', 'Ginning (جننگ)'),
        ('warehouse', 'Warehouse (گودام)'),
        ('office', 'Office (دفتر)'),
        ('transport', 'Transport (ٹرانسپورٹ)'),
        ('security', 'Security (سیکیورٹی)'),
        ('other', 'Other (دیگر)'),
    ]
    name = models.CharField(max_length=200)
    name_urdu = models.CharField(max_length=200, blank=True)
    cnic = models.CharField('CNIC', max_length=15, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    worker_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='daily')
    department = models.CharField(max_length=15, choices=DEPARTMENT_CHOICES, default='ginning')

    # Permanent fields
    monthly_salary = models.DecimalField('Monthly Salary (₨)', max_digits=10, decimal_places=2, default=0)
    joining_date = models.DateField(null=True, blank=True)

    # Daily wage fields
    daily_wage = models.DecimalField('Daily Wage (₨)', max_digits=10, decimal_places=2, default=0)

    # Contract fields
    contract_amount = models.DecimalField('Contract Amount (₨)', max_digits=12, decimal_places=2, default=0)
    contract_start = models.DateField('Contract Start', null=True, blank=True)
    contract_end = models.DateField('Contract End', null=True, blank=True)
    contract_description = models.TextField('Contract Work Description', blank=True)

    is_active = models.BooleanField(default=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'workers'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_worker_type_display()})"


class Attendance(models.Model):
    """Daily attendance record."""
    STATUS_CHOICES = [
        ('present', 'Present (حاضر)'),
        ('absent', 'Absent (غیر حاضر)'),
        ('half_day', 'Half Day (نصف دن)'),
        ('leave', 'Leave (چھٹی)'),
    ]
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='attendance')
    date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')
    overtime_hours = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'attendance'
        unique_together = ['worker', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.worker.name} — {self.date} — {self.get_status_display()}"


class WorkerPayment(models.Model):
    """Salary / wage payment to worker."""
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='payments')
    date = models.DateField(default=timezone.now)
    period_from = models.DateField(null=True, blank=True)
    period_to = models.DateField(null=True, blank=True)
    days_worked = models.IntegerField(default=0)
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance_deducted = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=15, default='cash')
    narration = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'worker_payments'
        ordering = ['-date']

    def __str__(self):
        return f"{self.worker.name} — ₨{self.net_amount} on {self.date}"


class WorkerAdvance(models.Model):
    """Advance payment to worker (deducted from salary later)."""
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='advances')
    date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_recovered = models.BooleanField(default=False)
    recovered_in = models.ForeignKey(WorkerPayment, on_delete=models.SET_NULL, null=True, blank=True)
    narration = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'worker_advances'
        ordering = ['-date']
