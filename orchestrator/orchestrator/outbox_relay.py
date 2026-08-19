"""Outbox relay: publishes committed event-store rows to Kafka.

The events table doubles as the outbox — every row is written in the same
transaction as the fact itself (it IS the fact), and published_at marks
whether the relay has shipped it to chronicle.events. This replaces the old
dual write (INSERT + separate Kafka publish), where a publish failure left
an event durable in the store but invisible to every consumer.

Delivery is at-least-once: a crash between send and the published_at update
means the row is re-sent on restart. Consumers already dedup by event_id /
(aggregate_id, stream_version), so the duplicate is a no-op downstream.
FOR UPDATE SKIP LOCKED keeps multiple relay replicas from double-claiming
a batch while both are healthy.
"""

import asyncio
import json
import logging
import os

import asyncpg
from aiokafka import AIOKafkaProducer

from orchestrator.db import get_pool

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TOPIC_EVENTS = "chronicle.events"
POLL_INTERVAL = float(os.getenv("OUTBOX_POLL_INTERVAL_SECONDS", "0.5"))
BATCH_SIZE = int(os.getenv("OUTBOX_BATCH_SIZE", "100"))

SELECT_UNPUBLISHED = """
    SELECT id, event_id, aggregate_id, stream_version, event_type, timestamp,
           producer, correlation_id, causation_id, workflow_id, trace_id,
           schema_version, payload
    FROM events
    WHERE published_at IS NULL
    ORDER BY id
    LIMIT $1
    FOR UPDATE SKIP LOCKED
"""


def _row_to_envelope(row) -> dict:
    payload = row["payload"]
    return {
        "event_id": str(row["event_id"]),
        "aggregate_id": str(row["aggregate_id"]),
        "stream_version": row["stream_version"],
        "event_type": row["event_type"],
        "timestamp": row["timestamp"].isoformat(),
        "producer": row["producer"],
        "correlation_id": str(row["correlation_id"]) if row["correlation_id"] else None,
        "causation_id": str(row["causation_id"]) if row["causation_id"] else None,
        "workflow_id": row["workflow_id"],
        "trace_id": row["trace_id"],
        "schema_version": row["schema_version"],
        "payload": payload if isinstance(payload, dict) else json.loads(payload),
    }


async def _publish_batch(conn: asyncpg.Connection, producer: AIOKafkaProducer) -> int:
    async with conn.transaction():
        rows = await conn.fetch(SELECT_UNPUBLISHED, BATCH_SIZE)
        if not rows:
            return 0
        for row in rows:
            envelope = _row_to_envelope(row)
            await producer.send_and_wait(
                TOPIC_EVENTS,
                value=envelope,
                key=envelope["aggregate_id"].encode(),
            )
        await conn.execute(
            "UPDATE events SET published_at = NOW() WHERE id = ANY($1)",
            [row["id"] for row in rows],
        )
        return len(rows)


async def run_relay() -> None:
    while True:
        try:
            pool = await get_pool()
            producer = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode(),
                enable_idempotence=True,
            )
            await producer.start()
            logger.info("Outbox relay started (batch=%d, poll=%.1fs)", BATCH_SIZE, POLL_INTERVAL)
            try:
                while True:
                    async with pool.acquire() as conn:
                        published = await _publish_batch(conn, producer)
                    if published:
                        logger.info("Outbox relay published %d event(s)", published)
                    else:
                        await asyncio.sleep(POLL_INTERVAL)
            finally:
                await producer.stop()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Outbox relay error, reconnecting in 5s: %s", e)
            await asyncio.sleep(5)
