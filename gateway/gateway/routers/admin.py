import httpx
import os
from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])

PROJECTION_URL = os.getenv("PROJECTION_SERVICE_URL", "http://projection-service:8004")


@router.post("/replay")
async def trigger_replay():
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{PROJECTION_URL}/projections/reset")
        return resp.json()
