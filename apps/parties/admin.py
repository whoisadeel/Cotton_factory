from django.contrib import admin
from .models import Party


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'party_type', 'city', 'phone_primary',
                    'current_balance', 'is_active')
    list_filter = ('party_type', 'is_active', 'province', 'is_filer')
    search_fields = ('name', 'code', 'phone_primary', 'cnic')
    readonly_fields = ('current_balance',)
