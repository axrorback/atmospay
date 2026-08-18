import hashlib
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Order
from .serializers import CreateOrderSerializer, AtmosCallbackSerializer
from .services import AtmosService


import logging

logger = logging.getLogger(__name__)


class CreateOrderCheckoutView(APIView):

    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        if serializer.is_valid():
            order = serializer.save()

            try:
                atmos_response = AtmosService.create_invoice(order)

                # Terminalda Atmos javobini to'liq chiqarish
                print("\n================= ATMOS FULL RESPONSE =================")
                print(atmos_response)
                print("=======================================================\n")

                result_data = atmos_response.get('result', {})

                # Har xil kalit variantlarini qidiramiz
                checkout_url = (
                    atmos_response.get('url') or
                    result_data.get('url') or
                    atmos_response.get('checkout_url') or
                    result_data.get('checkout_url')
                )

                payment_id = (
                    atmos_response.get('invoice_id') or
                    result_data.get('invoice_id') or
                    atmos_response.get('payment_id') or
                    result_data.get('payment_id')
                )

                token = (
                    atmos_response.get('token') or
                    result_data.get('token')
                )

                order.payment_id = payment_id
                order.token = token
                order.checkout_url = checkout_url
                order.save()

                return Response({
                    "status": "success",
                    "account": order.account,
                    "checkout_url": order.checkout_url,
                    "raw_atmos_response": atmos_response  # Debug uchun vaqtincha javobga ham qo'shdik
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                logger.error(f"Atmos Invoice Error: {str(e)}")
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AtmosCallbackView(APIView):

    def get(self, request):
        return Response(
            {"status": "ok", "message": "Atmos webhook ishlamoqda. Callback yuborish uchun POST ishlatiladi."},
            status=status.HTTP_200_OK
        )


    def post(self, request):
        serializer = AtmosCallbackSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"status": 0, "message": "Noto'g'ri so'rov formati"}, status=status.HTTP_200_OK)

        data = serializer.validated_data
        store_id = str(data['store_id'])
        transaction_id = str(data['transaction_id'])
        invoice = str(data['invoice'])
        amount = str(data['amount'])
        sign = data['sign']

        api_key = getattr(settings, 'ATMOS_API_KEY', '')
        sign_string = f"{store_id}{transaction_id}{invoice}{amount}{api_key}"
        calculated_sign = hashlib.md5(sign_string.encode('utf-8')).hexdigest()

        if calculated_sign.lower() != sign.lower():
            return Response({
                "status": 0,
                "message": "Raqamli imzo (sign) xatosi"
            }, status=status.HTTP_200_OK)

        try:
            order = Order.objects.get(account=invoice)
        except Order.DoesNotExist:
            return Response({
                "status": 0,
                "message": f"Инвойс с номером {invoice} отсутствует в системе"
            }, status=status.HTTP_200_OK)

        if order.amount != int(amount):
            return Response({
                "status": 0,
                "message": "To'lov summasi mos kelmadi"
            }, status=status.HTTP_200_OK)

        if order.status == 'paid':
            return Response({"status": 1, "message": "Успешно"}, status=status.HTTP_200_OK)

        order.status = 'paid'
        order.transaction_id = transaction_id
        order.transaction_time = data['transaction_time']
        order.save()

        return Response({
            "status": 1,
            "message": "Успешно"
        }, status=status.HTTP_200_OK)