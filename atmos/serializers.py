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
        )


class CreateOrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    # ✅ Bu fieldlarni qo'shish
    request_id = serializers.SerializerMethodField()
    store_id = serializers.SerializerMethodField()
    expiration_time = serializers.SerializerMethodField()
    expiration_date = serializers.SerializerMethodField()
    success_url = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "request_id",
            "store_id",
            "expiration_time",
            "expiration_date",
            "account",
            "amount",
            "success_url",
            "items",
        )

    def get_request_id(self, obj):
        return str(uuid.uuid4())

    def get_store_id(self, obj):
        return settings.ATMOS_STORE_ID

    def get_expiration_time(self, obj):
        return 10

    def get_expiration_date(self, obj):
        return (
                datetime.now()
                + timedelta(minutes=10)
        ).strftime("%Y-%m-%dT%H:%M:%S")

    def get_success_url(self, obj):
        return settings.ATMOS_SUCCESS_URL

class AtmosCallbackSerializer(
    serializers.Serializer
):

    store_id = serializers.IntegerField()

    transaction_id = serializers.CharField()

    transaction_time = serializers.DateTimeField()

    amount = serializers.IntegerField()

    invoice = serializers.IntegerField()

    sign = serializers.CharField()