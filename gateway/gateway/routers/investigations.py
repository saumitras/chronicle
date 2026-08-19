from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.session import get_db
from gateway.db.crud import get_investigations, get_investigation, get_events_by_aggregate

router = APIRouter(prefix="/investigations", tags=["investigations"])


@router.get("")
async def list_investigations(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await get_investigations(db, status=status, limit=limit)


@router.get("/{investigation_id}")
async def get_investigation_detail(investigation_id: str, db: AsyncSession = Depends(get_db)):
    inv = await get_investigation(db, investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return inv


@router.get("/{investigation_id}/events")
async def get_investigation_events(investigation_id: str, db: AsyncSession = Depends(get_db)):
    return await get_events_by_aggregate(db, investigation_id)
