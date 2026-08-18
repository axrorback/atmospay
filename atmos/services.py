import base64
import logging
import time
import requests
from datetime import datetime, timedelta

from django.conf import settings

logger = logging.getLogger(__name__)


class AtmosService:
    BASE_URL = "https://apigw.atmos.uz"

    @classmethod
    def get_token(cls):
        consumer_key = settings.ATMOS_CONSUMER_KEY
        consumer_secret = settings.ATMOS_CONSUMER_SECRET

        credentials = f"{consumer_key}:{consumer_secret}"
        encoded_credentials = base64.b64encode(
            credentials.encode()
        ).decode()

        response = requests.post(
            f"{cls.BASE_URL}/token?grant_type=client_credentials",
            headers={
                "Authorization": f"Basic {encoded_credentials}"
            },
            timeout=10
        )

        response.raise_for_status()

        return response.json()["access_token"]

    @classmethod
    def create_invoice(cls, order):
        token = cls.get_token()

        items = []

        for item in order.items.all():
            # Package code yoki standart OFD qiymati
            pkg_code = str(getattr(item, "package_code", "123456"))

            item_payload = {
                "items_id": str(item.items_id),
                "name": str(item.name),
                "amount": int(item.amount),
                "quantity": int(item.quantity),
                # Details Atmos namunasidagidek single dict ko'rinishida
                "details": {
                    "name": "package_code",
                    "values": pkg_code
                }
            }

            if getattr(item, "code", None):
                item_payload["code"] = str(item.code)

            items.append(item_payload)

        # Expiration date (YYYY-MM-DDTHH:MM:SS formatida)
        expiration_dt = datetime.now() + timedelta(minutes=60)
        expiration_date_str = expiration_dt.strftime("%Y-%m-%dT%H:%M:%S")

        payload = {
            "request_id": str(int(time.time())),
            "store_id": int(settings.ATMOS_STORE_ID),
            "expiration_time": 60,
            "expiration_date": expiration_date_str,
            "account": str(order.account),
            "amount": int(order.amount),
            "success_url": settings.ATMOS_SUCCESS_URL,
            "items": items
        }

        logger.info(f"ATMOS INVOICE PAYLOAD: {payload}")

        response = requests.post(
            f"{cls.BASE_URL}/checkout/invoice/create",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )

        logger.info(f"ATMOS INVOICE RESPONSE: {response.text}")

        response.raise_for_status()

        return response.json()