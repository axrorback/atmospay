from django.contrib import admin

from .models import Order , OrderItem

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('account', 'status', 'amount', 'created_at')



@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'items_id', 'code', 'name', 'amount', 'quantity', 'package_code', 'mark_code', 'tin', 'discount')