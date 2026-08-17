from rest_framework import serializers
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['items_id', 'code', 'name', 'amount', 'quantity', 'package_code', 'mark_code', 'tin', 'discount']


class CreateOrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = ['account', 'amount', 'items']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        order = Order.objects.create(**validated_data)

        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)

        return order


class AtmosCallbackSerializer(serializers.Serializer):
    store_id = serializers.IntegerField()
    transaction_id = serializers.CharField()
    transaction_time = serializers.CharField()
    amount = serializers.IntegerField()
    invoice = serializers.CharField()
    sign = serializers.CharField()