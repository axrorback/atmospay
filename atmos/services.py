import base64
import logging
import requests
from datetime import datetime, timedelta
from django.conf import settings

logger = logging.getLogger(__name__)


class AtmosService:
    BASE_URL = "https://apigw.atmos.uz"

    @classmethod
    def get_token(cls):
        consumer_key = getattr(settings, 'ATMOS_CONSUMER_KEY', '')
        consumer_secret = getattr(settings, 'ATMOS_CONSUMER_SECRET', '')

        credentials = f"{consumer_key}:{consumer_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            'Authorization': f'Basic {encoded_credentials}'
        }

        url = f"{cls.BASE_URL}/token?grant_type=client_credentials"
        response = requests.post(url, headers=headers, timeout=10)

        logger.info(f"Atmos Token Response [{response.status_code}]: {response.text}")

        if response.status_code == 200:
            return response.json().get('access_token')
        raise Exception(f"Atmos Token Error: {response.status_code} - {response.text}")

    @classmethod
    def create_invoice(cls, order):
        token = cls.get_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        items_payload = []
        for item in order.items.all():
            # OFD detallarini shakllantirish
            details = [
                {"name": "package_code", "values": str(getattr(item, 'package_code', '123456'))},
                {"name": "quantity", "values": str(item.quantity)},
                {"name": "discount", "values": str(getattr(item, 'discount', 0))}
            ]

            if getattr(item, 'mark_code', None):
                details.append({"name": "mark_code", "values": str(item.mark_code)})
            if getattr(item, 'tin', None):
                details.append({"name": "tin", "values": str(item.tin)})

            items_payload.append({
                "items_id": str(item.items_id),
                "code": str(item.code),  # IKPU kodi
                "name": str(item.name),
                "amount": int(item.amount),  # Tiyinda
                "quantity": int(item.quantity),
                "details": details
            })

        # Unikal request_id hosil qilish (Atmos duplicate xatosi bermasligi uchun)
        unique_request_id = f"{order.id}_{int(time.time())}"

        payload = {
            "request_id": unique_request_id,
            "store_id": int(getattr(settings, 'ATMOS_STORE_ID', 100718)),
            "expiration_time": 60,  # Faqat expiration_time qoldirildi, expiration_date olib tashlandi
            "account": str(order.account),
            "amount": int(order.amount),  # Tiyinda
            "success_url": str(getattr(settings, 'ATMOS_SUCCESS_URL', 'https://example.com/success')),
            "items": items_payload
        }

        url = f"{cls.BASE_URL}/checkout/invoice/create"

        # Debug uchun payload'ni print qilib ko'ring
        print(f"\n[ATMOS PAYLOAD DEBUG]: {payload}\n")

        response = requests.post(url, json=payload, headers=headers, timeout=10)

        logger.info(f"Atmos Invoice Response [{response.status_code}]: {response.text}")

        if response.status_code == 200:
            res_json = response.json()
            if res_json.get('status', {}).get('code') == 'OK' and 'url' in res_json:
                return res_json
            raise Exception(f"Atmos API Error Detail: {res_json}")

        raise Exception(f"Atmos Invoice Create Error: {response.status_code} - {response.text}")