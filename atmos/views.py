import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order

from .serializers import (
    CreateOrderSerializer,
    AtmosCallbackSerializer,
)

from .services import AtmosService


logger = logging.getLogger(__name__)


class CreateOrderCheckoutView(
    APIView
):

    def post(self, request):

        serializer = (
            CreateOrderSerializer(
                data=request.data
            )
        )

        serializer.is_valid(
            raise_exception=True
        )

        order = serializer.save()

        try:

            invoice = (
                AtmosService.create_invoice(
                    order
                )
            )

            order.payment_id = (
                invoice["payment_id"]
            )

            order.token = (
                invoice["token"]
            )

            order.checkout_url = (
                invoice["url"]
            )

            order.save()

            return Response(
                {
                    "status": "success",
                    "order_id": (
                        order.account
                    ),
                    "checkout_url": (
                        order.checkout_url
                    ),
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as exc:

            logger.exception(exc)

            order.status = "failed"

            order.save()

            return Response(
                {
                    "status": "error",
                    "message": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
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