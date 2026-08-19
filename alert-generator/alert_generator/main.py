import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Query
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError

from alert_generator.seed_data import build_alert
from alert_generator.kafka_producer import publish_alert
from alert_generator.db import append_event as append_alert_event
from alert_generator.seeder import run_seed
from chronicle_shared.schema import EventEnvelope
from chronicle_shared.events import EventType

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
ALERT_INTERVAL = int(os.getenv("ALERT_INTERVAL_SECONDS", "10"))


async def ensure_topics():
    admin = AIOKafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP)
    await admin.start()
    try:
        topics = [
            NewTopic("chronicle.alerts", num_partitions=3, replication_factor=1),
            NewTopic("chronicle.events", num_partitions=3, replication_factor=1),
        ]
        try:
            await admin.create_topics(topics)
            logger.info("Kafka topics created")
        except TopicAlreadyExistsError:
            logger.info("Kafka topics already exist")
    finally:
        await admin.close()


async def _generate_and_publish(risk_profile: str = "random") -> dict:
    alert = build_alert(risk_profile)
    # stream_version 0: AlertCreated precedes InvestigationStarted (v1) in the
    # same stream — the aggregate id is the alert id is the investigation id.
    envelope = EventEnvelope(
        event_type=EventType.ALERT_CREATED,
        aggregate_id=alert["alert_id"],
        producer="alert-generator",
        stream_version=0,
        correlation_id=alert["alert_id"],
        trace_id=str(uuid.uuid4()),  # the trace starts here and follows the case
        payload=alert,
    )
    # The store is the system of record: append first, then publish the
    # trigger to chronicle.alerts. The outbox relay publishes the stored
    # event to chronicle.events.
    await append_alert_event(envelope.to_dict())
    await publish_alert(envelope.to_dict())
    return alert


async def scheduler():
    if ALERT_INTERVAL <= 0:
        logger.info("Scheduler disabled (ALERT_INTERVAL_SECONDS=0)")
        return
    logger.info("Scheduler started — generating alerts every %ss", ALERT_INTERVAL)
    while True:
        await asyncio.sleep(ALERT_INTERVAL)
        try:
            alert = await _generate_and_publish()
            logger.info("Auto-generated alert %s risk=%s", alert["alert_id"], alert["risk_profile"])
        except Exception as e:
            logger.error("Scheduler error: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_topics()
    # Auto-seed on startup if not already seeded
    try:
        result = await run_seed()
        logger.info("Seed result: %s", result)
    except Exception as e:
        logger.warning("Seed failed (non-fatal): %s", e)
    task = asyncio.create_task(scheduler())
    yield
    task.cancel()


app = FastAPI(title="Chronicle Alert Generator", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "alert-generator"}


@app.post("/alerts/generate")
async def generate_alert(
    risk_profile: str = Query(default="random", enum=["random", "low", "medium", "high"])
):
    """Manually trigger a single alert."""
    alert = await _generate_and_publish(risk_profile)
    return {"alert_id": alert["alert_id"], "risk_profile": alert["risk_profile"]}


@app.post("/seed")
async def seed():
    """Manually trigger seeding (idempotent)."""
    result = await run_seed()
    return result
