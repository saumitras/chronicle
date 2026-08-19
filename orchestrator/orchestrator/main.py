import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from orchestrator.worker import run_worker
from orchestrator.kafka_consumer import consume_alerts
from orchestrator.outbox_relay import run_relay

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = asyncio.create_task(run_worker())
    consumer_task = asyncio.create_task(consume_alerts())
    relay_task = asyncio.create_task(run_relay())
    yield
    worker_task.cancel()
    consumer_task.cancel()
    relay_task.cancel()


app = FastAPI(title="Chronicle Orchestrator", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "orchestrator"}
