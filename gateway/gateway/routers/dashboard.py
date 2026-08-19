from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.session import get_db
from gateway.db.crud import get_dashboard_stats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    stats = await get_dashboard_stats(db)

    # Add running workflow count from Temporal
    try:
        import os
        from temporalio.client import Client
        temporal = await Client.connect(
            f"{os.getenv('TEMPORAL_HOST','temporal')}:{os.getenv('TEMPORAL_PORT','7233')}"
        )
        # Count open workflows
        count = 0
        async for _ in await temporal.list_workflows('ExecutionStatus="Running"'):
            count += 1
        stats["running_workflows"] = count
    except Exception:
        stats["running_workflows"] = stats.get("statuses", {}).get("running", 0)

    return stats
