import asyncio
import json
import logging
import os

from aiokafka import AIOKafkaConsumer
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "temporal")
TEMPORAL_PORT = os.getenv("TEMPORAL_PORT", "7233")
TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "chronicle-tasks")


async def consume_alerts():
    temporal = await Client.connect(f"{TEMPORAL_HOST}:{TEMPORAL_PORT}")

    consumer = AIOKafkaConsumer(
        "chronicle.alerts",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="orchestrator",
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="earliest",
        # Manual commits: auto-commit could persist an offset before
        # start_workflow succeeds, silently dropping an alert on crash.
        # We commit only after the workflow durably exists — at-least-once,
        # which the deterministic workflow id makes safe (duplicate → no-op).
        enable_auto_commit=False,
    )
    await consumer.start()
    logger.info("Kafka consumer started on chronicle.alerts")

    try:
        async for msg in consumer:
            envelope = msg.value
            alert_payload = envelope.get("payload", {})
            alert_id = alert_payload.get("alert_id", envelope.get("aggregate_id"))

            # Inject Kafka metadata into alert so it's available in events
            alert_payload["_kafka"] = {
                "topic": msg.topic,
                "partition": msg.partition,
                "offset": msg.offset,
            }
            # Also carry the AlertCreated event_id for causation chain,
            # and the trace_id so the whole case shares one trace
            alert_payload["event_id"] = envelope.get("event_id")
            alert_payload["trace_id"] = envelope.get("trace_id")

            workflow_id = f"inv-{alert_id}"
            # Retry THIS message until the workflow durably exists — never
            # advance past an alert that hasn't been handed to Temporal.
            # (Skipping and committing a later message would commit past the
            # failed one, silently dropping it.) Duplicate delivery is the
            # safe outcome: already-started is success, matched by exception
            # type — never by error-message string.
            while True:
                try:
                    await temporal.start_workflow(
                        "InvestigationWorkflow",
                        alert_payload,
                        id=workflow_id,
                        task_queue=TASK_QUEUE,
                    )
                    logger.info("Started workflow %s topic=%s partition=%d offset=%d",
                                workflow_id, msg.topic, msg.partition, msg.offset)
                    break
                except WorkflowAlreadyStartedError:
                    logger.info("Workflow %s already started, skipping duplicate", workflow_id)
                    break
                except Exception as e:
                    logger.error("Failed to start workflow %s (retrying in 5s): %s",
                                 workflow_id, e)
                    await asyncio.sleep(5)
            await consumer.commit()
    finally:
        await consumer.stop()
