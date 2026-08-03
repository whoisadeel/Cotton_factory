from django.contrib import admin
from .models import Category, Product, UnitOfMeasurement


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'parent', 'is_active', 'is_default')
    list_filter = ('is_active', 'is_default')
    search_fields = ('name', 'code')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'unit', 'current_stock', 'status')
    list_filter = ('category', 'status')
    search_fields = ('name', 'code')


@admin.register(UnitOfMeasurement)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'abbreviation', 'unit_type', 'conversion_to_base', 'is_active')
