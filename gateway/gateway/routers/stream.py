import asyncio
import json
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.session import AsyncSessionLocal
from gateway.db.crud import get_recent_events

router = APIRouter(tags=["stream"])


async def _event_generator():
    last_ts = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
    while True:
        await asyncio.sleep(1)
        try:
            async with AsyncSessionLocal() as db:
                events = await get_recent_events(db, limit=50, since=last_ts)
            if events:
                # events are newest-first from the query, reverse for chronological
                for event in reversed(events):
                    yield f"data: {json.dumps(event)}\n\n"
                last_ts = events[0]["timestamp"]  # newest timestamp
        except Exception:
            pass


@router.get("/stream")
async def stream_events():
    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
