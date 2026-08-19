import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway.routers import events, investigations, alerts, dashboard, stream, admin, approvals

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Chronicle Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router)
app.include_router(investigations.router)
app.include_router(alerts.router)
app.include_router(dashboard.router)
app.include_router(stream.router)
app.include_router(admin.router)
app.include_router(approvals.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}
