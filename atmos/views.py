import logging
from config import settings
from .serializers import AtmosCallbackSerializer
from .services import AtmosService
import base64
import uuid
from datetime import datetime, timedelta
import requests
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Order, OrderItem
from .kafka_sender import send_payment_event
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
logger = logging.getLogger(__name__)


class CreateOrderCheckoutView(APIView):

    def post(self, request):
        order = None
        try:
            data = request.data
            amount = data.get("amount")
            return_url = data.get("return_url")
            items = data.get("items", [])

            if not amount or not items:
                return Response(
                    {"status": "error", "message": "amount va items majburiy"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 1. Order yaratamiz
            # Modelda account=models.CharField(default=uuid.uuid4) bo'lgani uchun account avto beriladi
            # Agar request'dan kelsa shuni, aks holda yangi uuid string qilib olamiz
            account_val = str(data.get("account") or uuid.uuid4())

            order = Order.objects.create(
                account=account_val,
                amount=int(amount),
                return_url=str(return_url),
            )

            # 2. OrderItem'larni saqlash
            for item in items:
                OrderItem.objects.create(
                    order=order,
                    items_id=str(item.get("items_id", "")),
                    code=item.get("code"),
                    name=item.get("name", "Product"),
                    amount=int(item.get("amount", 0)),
                    quantity=int(item.get("quantity", 1)),
                    package_code=item.get("package_code"),
                    mark_code=item.get("mark_code"),
                    tin=item.get("tin"),
                    discount=int(item.get("discount", 0)),
                )

            # 3. Atmos Access Token olish
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

            # 4. Atmos tayyor payload uchun items shakllantirish
            # Support yuborgan JSON bilan 1:1 mos bo'lishi kerak
            atmos_items = []
            for item in order.items.all():
                item_dict = {
                    "items_id": str(item.items_id),
                    "name": str(item.name),
                    "amount": int(item.amount),
                    "quantity": int(item.quantity),
                    "details": {
                        "name":"some_key",
                        "values": "some_value"
                    }
                }


                atmos_items.append(item_dict)

            payload = {
                "request_id": str(uuid.uuid4()),
                "store_id": int(100718),
                "expiration_time": 10,
                "expiration_date": (
                    datetime.now() + timedelta(minutes=10)
                ).strftime("%Y-%m-%dT%H:%M:%S"),
                "account": str(order.account),
                "amount": int(order.amount),
                "success_url": order.return_url,
                "items": atmos_items,
            }

            logger.info(f"Atmos Request Payload: {payload}")

            # 6. Atmos Invoice yaratish
            atmos_response = requests.post(
                f"{settings.ATMOS_BASE_URL}/checkout/invoice/create",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )

            res_json = atmos_response.json()
            logger.info(f"Atmos API Response: {res_json}")

            # Status tekshirish
            status_data = res_json.get("status", {})
            status_code = str(status_data.get("code", ""))

            if status_code != "0":
                error_description = (
                    status_data.get("description")
                    or res_json.get("message")
                    or f"Error code: {status_code}"
                )

                order.status = "failed"
                order.save()

                return Response(
                    {
                        "status": "error",
                        "message": error_description,
                        "raw_atmos_response": res_json,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 7. Muvaffaqiyatli saqlash
            order.payment_id = res_json.get("payment_id")
            order.token = res_json.get("token")
            order.checkout_url = res_json.get("url")
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
            logger.exception(f"Atmos HTTP Connection Error: {str(e)}")
            if order:
                order.status = "failed"
                order.save()

            return Response(
                {
                    "status": "error",
                    "message": f"Atmos serveriga bog'lanishda xatolik: {str(e)}",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        except Exception as e:
            logger.exception(f"Kutilmagan xatolik: {str(e)}")
            if order:
                order.status = "failed"
                order.save()

            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AtmosCallbackView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = AtmosCallbackSerializer(data=request.data)

        if not serializer.is_valid():
            logger.warning(
                "Invalid Atmos callback: %s",
                serializer.errors,
            )
            return Response(
                {"status": 0, "message": "Invalid request parameters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data

        is_valid = AtmosService.validate_sign(
            store_id=data["store_id"],
            transaction_id=data["transaction_id"],
            invoice=data["account"],
            amount=data["amount"],
            sign=data["sign"],
        )

        if not is_valid:
            logger.warning("Invalid Atmos signature")
            return Response(
                {"status": 0, "message": "Invalid sign signature"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            with transaction.atomic():
                order = (
                    Order.objects
                    .select_for_update()
                    .get(account=str(data["account"]))
                )


                if Decimal(str(order.amount)) != Decimal(str(data["amount"])):
                    return Response(
                        {"status": 0, "message": "Amount mismatch"},
                        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    )

                transaction_id = str(data["transaction_id"])

                # Takror kelgan callback uchun idempotent ishlov.
                if order.status == "paid":
                    if order.transaction_id != transaction_id:
                        logger.error(
                            "Order already paid with another transaction: %s",
                            order.pk,
                        )
                        return Response(
                            {"status": 0, "message": "Order already paid"},
                            status=status.HTTP_409_CONFLICT,
                        )

                    # Aynan shu tranzaksiya uchun retry:
                    # eventni qayta publish qilishga ruxsat beramiz.
                else:
                    order.status = "paid"
                    order.transaction_id = transaction_id
                    order.transaction_time = str(
                        data["transaction_time"]
                    )
                    order.save(
                        update_fields=[
                            "status",
                            "transaction_id",
                            "transaction_time",
                        ]
                    )

                event = {
                    "event": "payment.paid",
                    "provider": "atmos",
                    "order_id": str(order.id),
                    "transaction_id": transaction_id,
                    "amount": str(order.amount),
                    "status": "paid",
                    "paid_at": timezone.localtime(timezone.now()).isoformat(),
                }

                def publish_after_commit():
                    try:
                        send_payment_event(event)
                    except Exception:
                        logger.exception(
                            "Failed to publish Atmos event: order_id=%s",
                            order.id,
                        )

                transaction.on_commit(publish_after_commit)

        except Order.DoesNotExist:
            logger.warning(
                "Atmos order not found: account=%s",
                data["account"],
            )
            return Response(
                {
                    "status": 0,
                    "message": "Invoice not found",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {"status": 1, "message": "Успешно"},
            status=status.HTTP_200_OK,
        )