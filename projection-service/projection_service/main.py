import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from projection_service.consumer import consume_events
from projection_service.replay import replay_all, get_replay_status

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(consume_events())
    yield
    task.cancel()


app = FastAPI(title="Chronicle Projection Service", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "projection-service"}


@app.post("/projections/reset")
async def reset_projections():
    result = await replay_all()
    return result


@app.get("/projections/status")
async def replay_status():
    return {"status": get_replay_status()}
