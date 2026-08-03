from django.contrib import admin
from .models import PaymentVoucher, ReceiptVoucher, Expense
admin.site.register(PaymentVoucher)
admin.site.register(ReceiptVoucher)
admin.site.register(Expense)
