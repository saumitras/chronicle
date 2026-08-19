import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agents.worker import run_worker

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_worker())
    yield
    task.cancel()


app = FastAPI(title="Chronicle Agents", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agents"}
