import json
import logging

from kafka import KafkaProducer
from config import settings

logger = logging.getLogger(__name__)

_producer = None


def get_kafka_producer():
    global _producer

    if _producer is None:
        _producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda value: json.dumps(
                value,
                default=str,
            ).encode("utf-8"),
            acks="all",
            retries=5,
        )

    return _producer


def send_payment_event(event: dict) -> None:
    producer = get_kafka_producer()

    future = producer.send(
        "payment.atmos",
        value=event,
    )

    metadata = future.get(timeout=10)

    logger.info(
        "Kafka event sent: topic=%s partition=%s offset=%s",
        metadata.topic,
        metadata.partition,
        metadata.offset,
    )