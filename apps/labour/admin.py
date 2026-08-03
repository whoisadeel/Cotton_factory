from django.contrib import admin
from .models import Worker, Attendance, WorkerPayment, WorkerAdvance
admin.site.register(Worker)
admin.site.register(Attendance)
admin.site.register(WorkerPayment)
admin.site.register(WorkerAdvance)
