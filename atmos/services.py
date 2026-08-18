import base64
import logging
import time
import requests
from datetime import datetime, timedelta
import uuid
from django.conf import settings

logger.info(
    json.dumps(
        payload,
        ensure_ascii=False,
        indent=4
    )
)

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

            details = []

            if item.package_code:
                details.append({
                    "name": "package_code",
                    "values": str(item.package_code)
                })

            if item.mark_code:
                details.append({
                    "name": "mark_code",
                    "values": str(item.mark_code)
                })

            if item.tin:
                details.append({
                    "name": "tin",
                    "values": str(item.tin)
                })

            if item.discount:
                details.append({
                    "name": "discount",
                    "values": str(item.discount)
                })

            details.append({
                "name": "quantity",
                "values": str(item.quantity)
            })

            item_payload = {
                "items_id": str(item.items_id),
                "code": str(item.code),
                "name": str(item.name),
                "amount": int(item.amount),
                "quantity": int(item.quantity),
                "details": details
            }

            items.append(item_payload)

        expiration_date = (
                datetime.now() + timedelta(minutes=60)
        ).strftime("%Y-%m-%dT%H:%M:%S")

        payload = {
            "request_id": str(uuid.uuid4()),
            "store_id": int(settings.ATMOS_STORE_ID),
            "expiration_time": 60,
            "expiration_date": expiration_date,
            "account": str(order.account),
            "amount": int(order.amount),
            "success_url": settings.ATMOS_SUCCESS_URL,
            "items": items
        }

        logger.info(payload)

        response = requests.post(
            f"{cls.BASE_URL}/checkout/invoice/create",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )

        response.raise_for_status()

        return response.json()