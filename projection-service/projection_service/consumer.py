import asyncio
import json
import logging
import os

from aiokafka import AIOKafkaConsumer

from projection_service.handlers.event_handlers import handle_event

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
_paused = False


def pause():
    global _paused
    _paused = True


def resume():
    global _paused
    _paused = False


async def consume_events():
    consumer = AIOKafkaConsumer(
        "chronicle.events",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="projection-service",
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="earliest",
    )
    await consumer.start()
    logger.info("Projection consumer started on chronicle.events")
    try:
        async for msg in consumer:
            while _paused:
                await asyncio.sleep(0.1)
            try:
                await handle_event(msg.value)
            except Exception as e:
                logger.error("Failed to handle event: %s", e)
    finally:
        await consumer.stop()
