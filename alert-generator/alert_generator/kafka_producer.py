import json
import logging
import os
from aiokafka import AIOKafkaProducer

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TOPIC_ALERTS = "chronicle.alerts"

_producer: AIOKafkaProducer | None = None


async def _get_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode(),
        )
        await _producer.start()
    return _producer


async def publish_alert(envelope: dict) -> None:
    """Publish the AlertCreated trigger to chronicle.alerts.

    chronicle.events is NOT published here — the stored event reaches it via
    the outbox relay, so the events topic always mirrors the event store.
    """
    producer = await _get_producer()
    await producer.send_and_wait(
        TOPIC_ALERTS,
        value=envelope,
        key=envelope["aggregate_id"].encode(),
    )
    logger.info("Published AlertCreated aggregate_id=%s", envelope["aggregate_id"])
