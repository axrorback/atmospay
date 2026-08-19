from rest_framework import serializers

from .models import Order
from .models import OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    package_code = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = OrderItem
        fields = (
            "items_id",
            "code",
            "name",
            "amount",
            "quantity",
            "package_code",
            "mark_code",
            "tin",
            "discount",
        )


class CreateOrderSerializer(serializers.ModelSerializer):

    items = OrderItemSerializer(
        many=True
    )

    class Meta:
        model = Order

        fields = (
            "account",
            "amount",
            "items",
        )

    def create(self, validated_data):

        items = validated_data.pop(
            "items"
        )

        order = Order.objects.create(
            **validated_data
        )

        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    **item
                )
                for item in items
            ]
        )

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