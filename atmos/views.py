import base64
import logging

import requests
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
import uuid
from config import settings
from .models import Order, OrderItem
from datetime import datetime, timedelta
from .serializers import (
    CreateOrderSerializer,
    AtmosCallbackSerializer,
)

from .services import AtmosService


logger = logging.getLogger(__name__)


class CreateOrderCheckoutView(APIView):

    def post(self, request):
        """Direct Atmos integration"""
        order = None
        try:
            data = request.data
            account = data.get("account")
            amount = data.get("amount")
            items = data.get("items", [])

            if not all([account, amount, items]):
                return Response(
                    {
                        "status": "error",
                        "message": "account, amount, items majburiy",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 1. Order va OrderItem'larni yaratish
            order = Order.objects.create(account=account, amount=amount)

            for item in items:
                OrderItem.objects.create(
                    order=order,
                    items_id=item.get("items_id"),
                    name=item.get("name"),
                    amount=item.get("amount"),
                    quantity=item.get("quantity", 1),
                    code=item.get("code"),
                    package_code=item.get("package_code"),
                    mark_code=item.get("mark_code"),
                    tin=item.get("tin"),
                    discount=item.get("discount", 0),
                )

            # 2. Access Token olish
            credentials = (
                f"{settings.ATMOS_CONSUMER_KEY}:{settings.ATMOS_CONSUMER_SECRET}"
            )
            encoded = base64.b64encode(credentials.encode()).decode()

            token_response = requests.post(
                f"{settings.ATMOS_BASE_URL}/token?grant_type=client_credentials",
                headers={"Authorization": f"Basic {encoded}"},
                timeout=10,
            )
            token_response.raise_for_status()
            access_token = token_response.json()["access_token"]

            # 3. Atmos uchun Items tayyorlash
            atmos_items = []
            for item in order.items.all():
                atmos_item = {
                    "items_id": str(item.items_id),
                    "name": item.name,
                    "amount": int(item.amount),
                    "quantity": int(item.quantity),
                }

                # Atmos namunasiga mos 'details' OBYEKTI (Array emas)
                # Kerakli key/value juftligini shakllantirish:
                details_key = (
                    item.package_code
                    or item.mark_code
                    or item.tin
                    or "item_info"
                )
                details_val = (
                    str(item.discount)
                    if item.discount
                    else (item.code or "none")
                )

                atmos_item["details"] = {
                    "name": str(details_key),
                    "values": str(details_val),
                }

                atmos_items.append(atmos_item)

            # 4. Payload tayyorlash
            payload = {
                "request_id": str(uuid.uuid4()),
                "store_id": int(settings.ATMOS_STORE_ID),
                "expiration_time": 10,
                "expiration_date": (
                    datetime.now() + timedelta(minutes=10)
                ).strftime("%Y-%m-%dT%H:%M:%S"),
                "account": account,
                "amount": int(amount),
                "success_url": settings.ATMOS_SUCCESS_URL,
                "items": atmos_items,
            }

            logger.info(f"Atmos payload: {payload}")

            # 5. Atmos API'ga yuborish
            atmos_response = requests.post(
                f"{settings.ATMOS_BASE_URL}/checkout/invoice/create",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )

            atmos_response.raise_for_status()
            invoice_data = atmos_response.json()

            logger.info(f"Atmos response: {invoice_data}")

            if invoice_data.get("status", {}).get("code") != "0":
                error_msg = invoice_data.get("status", {}).get(
                    "description", "Unknown error"
                )
                order.status = "failed"
                order.save()
                return Response(
                    {"status": "error", "message": error_msg},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 6. Order statusini update qilish
            order.payment_id = invoice_data.get("payment_id")
            order.token = invoice_data.get("token")
            order.checkout_url = invoice_data.get("url")
            order.status = "pending"
            order.save()

            return Response(
                {
                    "status": "success",
                    "order_id": order.id,
                    "account": order.account,
                    "payment_id": order.payment_id,
                    "checkout_url": order.checkout_url,
                },
                status=status.HTTP_201_CREATED,
            )

        except requests.exceptions.RequestException as e:
            logger.exception(f"Atmos API error: {str(e)}")
            if order:
                order.status = "failed"
                order.save()
            return Response(
                {"status": "error", "message": f"Atmos API error: {str(e)}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            if order:
                order.status = "failed"
                order.save()
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
class AtmosCallbackView(
    APIView
):

    authentication_classes = []

    permission_classes = []

    def post(self, request):

        serializer = (
            AtmosCallbackSerializer(
                data=request.data
            )
        )

        if (
            not serializer.is_valid()
        ):

            return Response(
                {
                    "status": 0,
                    "message": (
                        "Invalid request"
                    ),
                }
            )

        data = (
            serializer.validated_data
        )

        is_valid = (
            AtmosService.validate_sign(
                store_id=data[
                    "store_id"
                ],
                transaction_id=data[
                    "transaction_id"
                ],
                invoice=data[
                    "invoice"
                ],
                amount=data[
                    "amount"
                ],
                sign=data[
                    "sign"
                ],
            )
        )

        if not is_valid:

            return Response(
                {
                    "status": 0,
                    "message": (
                        "Invalid sign"
                    ),
                }
            )

        try:

            order = (
                Order.objects.get(
                    payment_id=data[
                        "invoice"
                    ]
                )
            )

        except Order.DoesNotExist:

            return Response(
                {
                    "status": 0,
                    "message": (
                        "Invoice not found"
                    ),
                }
            )

        if (
            order.amount
            != data["amount"]
        ):

            return Response(
                {
                    "status": 0,
                    "message": (
                        "Amount mismatch"
                    ),
                }
            )

        order.status = "paid"

        order.transaction_id = (
            data[
                "transaction_id"
            ]
        )

        order.transaction_time = (
            data[
                "transaction_time"
            ]
        )

        order.save()

        return Response(
            {
                "status": 1,
                "message": "Успешно",
            }
        )