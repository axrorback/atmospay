import uuid
from config import settings
from rest_framework import serializers
from datetime import datetime, timedelta
from .models import Order
from .models import OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "items_id",
            "name",
            "amount",
            "quantity",
            "code",
            "package_code",
            "mark_code",
            "tin",
            "discount",
        )
        extra_kwargs = {
            'code': {'required': False, 'allow_null': True},
            'package_code': {'required': False, 'allow_null': True},
            'mark_code': {'required': False, 'allow_null': True},
            'tin': {'required': False, 'allow_null': True},
        }


class CreateOrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = (
            "account",
            "amount",
            "items",
        )

    def create(self, validated_data):
        # ✅ items'ni olib chiqing
        items_data = validated_data.pop("items", [])

        # ✅ Order yarating
        order = Order.objects.create(**validated_data)

        # ✅ OrderItem'larni yarating
        order_items = [
            OrderItem(order=order, **item)
            for item in items_data
        ]
        OrderItem.objects.bulk_create(order_items)

        return order

class AtmosCallbackSerializer(
    serializers.Serializer
):

    store_id = serializers.IntegerField()

    transaction_id = serializers.CharField()

    transaction_time = serializers.DateTimeField()

    amount = serializers.IntegerField()

    invoice = serializers.IntegerField()

    sign = serializers.CharField()