import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.worker import Worker

from agents.device.agent import run_device_agent
from agents.geo.agent import run_geo_agent
from agents.customer.agent import run_customer_agent
from agents.investigation.agent import run_investigation_agent
from agents.policy.agent import run_policy_agent
from agents.shared.event_writer import append_event as _append_event
from temporalio import activity

# Re-expose append_event as a Temporal activity on the agents worker
@activity.defn(name="append_event")
async def append_event(envelope_dict: dict) -> dict:
    stored_event_id = await _append_event(envelope_dict)
    envelope_dict["event_id"] = stored_event_id
    return envelope_dict

logger = logging.getLogger(__name__)

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "temporal")
TEMPORAL_PORT = os.getenv("TEMPORAL_PORT", "7233")
TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "chronicle-agent-tasks")


async def run_worker():
    client = await Client.connect(f"{TEMPORAL_HOST}:{TEMPORAL_PORT}")
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        activities=[
            append_event,
            run_device_agent,
            run_geo_agent,
            run_customer_agent,
            run_investigation_agent,
            run_policy_agent,
        ],
    )
    logger.info("Agents worker started on task queue: %s", TASK_QUEUE)
    await worker.run()
