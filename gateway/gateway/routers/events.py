from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from gateway.db.session import get_db
from gateway.db.crud import append_event, get_events_by_aggregate, get_recent_events

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", status_code=201)
async def post_event(envelope: dict, db: AsyncSession = Depends(get_db)):
    try:
        return await append_event(db, envelope)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Duplicate stream_version for aggregate")


@router.get("/{aggregate_id}")
async def get_aggregate_events(aggregate_id: str, db: AsyncSession = Depends(get_db)):
    return await get_events_by_aggregate(db, aggregate_id)


@router.get("")
async def list_recent_events(
    limit: int = Query(default=50, le=10000),
    since: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return await get_recent_events(db, limit=limit, since=since)
