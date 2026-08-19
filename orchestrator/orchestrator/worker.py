import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.worker import Worker

from orchestrator.workflows.investigation import InvestigationWorkflow
from orchestrator.activities.agent_activities import append_event, send_hitl_notification

logger = logging.getLogger(__name__)

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "temporal")
TEMPORAL_PORT = os.getenv("TEMPORAL_PORT", "7233")
TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "chronicle-tasks")


async def run_worker():
    client = await Client.connect(f"{TEMPORAL_HOST}:{TEMPORAL_PORT}")
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[InvestigationWorkflow],
        activities=[append_event, send_hitl_notification],
    )
    logger.info("Worker started on task queue: %s", TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
