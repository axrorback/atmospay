import base64
import hashlib
import logging
import uuid

from datetime import datetime
from datetime import timedelta

import requests

from django.conf import settings


logger = logging.getLogger(__name__)


class AtmosService:

    BASE_URL = settings.ATMOS_BASE_URL

    @classmethod
    def get_token(cls):

        credentials = (
            f"{settings.ATMOS_CONSUMER_KEY}:"
            f"{settings.ATMOS_CONSUMER_SECRET}"
        )

        encoded = base64.b64encode(
            credentials.encode()
        ).decode()

        response = requests.post(
            f"{cls.BASE_URL}"
            "/token?grant_type=client_credentials",
            headers={
                "Authorization": (
                    f"Basic {encoded}"
                )
            },
            timeout=10,
        )

        response.raise_for_status()

        return response.json()[
            "access_token"
        ]

    @classmethod
    def build_details(cls, item):

        details = []

        if item.package_code:

            details.append(
                {
                    "name": "package_code",
                    "values": item.package_code,
                }
            )

        if item.mark_code:

            details.append(
                {
                    "name": "mark_code",
                    "values": item.mark_code,
                }
            )

        if item.tin:

            details.append(
                {
                    "name": "tin",
                    "values": item.tin,
                }
            )

        if item.discount:

            details.append(
                {
                    "name": "discount",
                    "values": str(
                        item.discount
                    ),
                }
            )

        return details

    @classmethod
    def create_invoice(cls, order):
        token = cls.get_token()
        items = []

        for item in order.items.all():
            details = cls.build_details(item)

            item_payload = {
                "items_id": item.items_id,
                "name": item.name,
                "amount": item.amount,
                "quantity": item.quantity,
            }

            if details:
                item_payload["details"] = details

            items.append(item_payload)

        payload = {
            "request_id": str(uuid.uuid4()),
            "store_id": settings.ATMOS_STORE_ID,
            "expiration_time": 10,
            "expiration_date": (
                    datetime.now()
                    + timedelta(minutes=10)
            ).strftime("%Y-%m-%dT%H:%M:%S"),
            "account": order.account,
            "amount": order.amount,
            "success_url": settings.ATMOS_SUCCESS_URL,
            "items": items,
        }

        response = requests.post(
            f"{cls.BASE_URL}/checkout/invoice/create",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )

        response.raise_for_status()
        return response.json()

    @staticmethod
    def validate_sign(store_id, transaction_id, invoice, amount, sign):
        api_key = settings.ATMOS_API_KEY

        raw_string = f"{store_id}{transaction_id}{invoice}{amount}{api_key}"

        calculated_sign = hashlib.md5(raw_string.encode('utf-8')).hexdigest()

        return calculated_sign.lower() == str(sign).lower()