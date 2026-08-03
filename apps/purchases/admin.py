from django.contrib import admin
from .models import Purchase, PurchaseItem
class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0
@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('purchase_number', 'date', 'supplier', 'grand_total', 'status')
    list_filter = ('status', 'date')
    inlines = [PurchaseItemInline]
