import base64
import logging
import requests
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

        print(f"\n[ATMOS TOKEN RESPONSE] Status: {response.status_code} | Body: {response.text}")
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
            items_payload.append({
                "items_id": str(item.items_id),
                "code": item.code,
                "name": item.name,
                "amount": item.amount,
                "quantity": item.quantity,
                "details": [
                    {"name": "package_code", "values": str(item.package_code)},
                    {"name": "mark_code", "values": str(item.mark_code or "")},
                    {"name": "tin", "values": str(item.tin or "")},
                    {"name": "discount", "values": str(item.discount)},
                    {"name": "quantity", "values": str(item.quantity)}
                ]
            })

        payload = {
            "request_id": str(order.id),
            "store_id": int(getattr(settings, 'ATMOS_STORE_ID', 3)),
            "account": str(order.account),
            "amount": order.amount,
            "success_url": getattr(settings, 'ATMOS_SUCCESS_URL', 'https://example.com/success'),
            "items": items_payload
        }

        url = f"{cls.BASE_URL}/checkout/invoice/create"
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        # Terminal va log faylga chiqarish
        print(f"\n[ATMOS INVOICE PAYLOAD]: {payload}")
        print(f"[ATMOS INVOICE RESPONSE] Status: {response.status_code} | Body: {response.text}\n")
        logger.info(f"Atmos Invoice Response [{response.status_code}]: {response.text}")

        if response.status_code == 200:
            res_json = response.json()
            # Status xatoligini yoki url yo'qligini tekshirish
            if res_json.get('status', {}).get('code') == 'OK' and 'url' in res_json:
                return res_json
            raise Exception(f"Atmos API Error Detail: {res_json}")

        raise Exception(f"Atmos Invoice Create Error: {response.status_code} - {response.text}")