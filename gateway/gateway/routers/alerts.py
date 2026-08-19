from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.session import get_db
from gateway.db.crud import get_alerts, get_alert

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    return await get_alerts(db, limit=limit)


@router.get("/{alert_id}")
async def get_alert_detail(alert_id: str, db: AsyncSession = Depends(get_db)):
    alert = await get_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert
