import os
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timezone

from gateway.db.session import get_db
from gateway.db.models import InvestigationModel
from chronicle_shared.schema import EventEnvelope
from chronicle_shared.events import EventType
from gateway.db.crud import append_event, get_events_by_aggregate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/investigations", tags=["approvals"])

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "temporal")
TEMPORAL_PORT = os.getenv("TEMPORAL_PORT", "7233")
TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "chronicle-tasks")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")


class ApproveRequest(BaseModel):
    reviewer_id: str
    decision: str       # "approve" | "deny"
    comment: str = ""


class ClarifyRequest(BaseModel):
    reviewer_id: str
    question: str


async def _get_workflow_id(db: AsyncSession, investigation_id: str) -> str:
    result = await db.execute(
        select(InvestigationModel.workflow_id)
        .where(InvestigationModel.investigation_id == investigation_id)
    )
    row = result.scalar_one_or_none()
    return row or f"inv-{investigation_id}"


@router.post("/{investigation_id}/approve")
async def approve_investigation(
    investigation_id: str,
    body: ApproveRequest,
    db: AsyncSession = Depends(get_db),
):
    inv = await db.execute(
        select(InvestigationModel)
        .where(InvestigationModel.investigation_id == investigation_id)
    )
    inv_row = inv.scalar_one_or_none()
    if not inv_row:
        raise HTTPException(status_code=404, detail="Investigation not found")

    decision = body.decision.lower()
    if decision not in ("approve", "deny"):
        raise HTTPException(status_code=422, detail="decision must be 'approve' or 'deny'")

    workflow_id = inv_row.workflow_id or f"inv-{investigation_id}"
    decided_at = datetime.now(timezone.utc).isoformat()

    # Signal the Temporal workflow
    try:
        from temporalio.client import Client
        from chronicle_shared.signals import ReviewDecisionSignal
        client = await Client.connect(f"{TEMPORAL_HOST}:{TEMPORAL_PORT}")
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(
            "review_decision",
            ReviewDecisionSignal(
                reviewer_id=body.reviewer_id,
                decision=decision,
                comment=body.comment,
                decided_at=decided_at,
            ),
        )
        logger.info("Signalled workflow %s decision=%s", workflow_id, body.decision)
    except Exception as e:
        logger.error("Failed to signal workflow %s: %s", workflow_id, e)
        raise HTTPException(status_code=502, detail=f"Failed to signal workflow: {e}")

    return {"status": "signalled", "workflow_id": workflow_id, "decision": body.decision}


@router.get("/{investigation_id}/pending")
async def get_pending_status(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
):
    inv = await db.execute(
        select(InvestigationModel)
        .where(InvestigationModel.investigation_id == investigation_id)
    )
    inv_row = inv.scalar_one_or_none()
    if not inv_row:
        raise HTTPException(status_code=404, detail="Investigation not found")

    workflow_id = inv_row.workflow_id or f"inv-{investigation_id}"
    waiting = False
    try:
        from temporalio.client import Client
        client = await Client.connect(f"{TEMPORAL_HOST}:{TEMPORAL_PORT}")
        handle = client.get_workflow_handle(workflow_id)
        waiting = await handle.query("is_waiting")
    except Exception:
        pass

    return {"investigation_id": investigation_id, "waiting": waiting, "status": inv_row.status}


@router.post("/{investigation_id}/clarify")
async def clarify_investigation(
    investigation_id: str,
    body: ClarifyRequest,
    db: AsyncSession = Depends(get_db),
):
    # Load all events for context
    events = await get_events_by_aggregate(db, investigation_id)
    if not events:
        raise HTTPException(status_code=404, detail="Investigation not found")

    # Build context from events
    device_ev = next((e for e in events if e["event_type"] == "DeviceEvidenceCollected"), None)
    geo_ev = next((e for e in events if e["event_type"] == "GeoEvidenceCollected"), None)
    customer_ev = next((e for e in events if e["event_type"] == "CustomerEvidenceCollected"), None)
    llm_ev = next((e for e in events if e["event_type"] == "LLMReasoningGenerated"), None)
    risk_ev = next((e for e in events if e["event_type"] == "RiskAssessed"), None)

    context = f"""Investigation ID: {investigation_id}

Device Evidence: {device_ev['payload'].get('evidence', {}) if device_ev else 'not collected'}
Geo Evidence: {geo_ev['payload'].get('evidence', {}) if geo_ev else 'not collected'}
Customer Evidence: {customer_ev['payload'].get('evidence', {}) if customer_ev else 'not collected'}
LLM Reasoning: {llm_ev['payload'].get('reasoning', 'none') if llm_ev else 'not available'}
Risk Assessment: score={risk_ev['payload'].get('risk_score')} decision={risk_ev['payload'].get('decision')} flags={risk_ev['payload'].get('risk_flags', [])} if risk_ev else 'not assessed'"""

    prompt = f"""You are a fraud investigation assistant helping a human reviewer make an approval decision.

{context}

Reviewer question: {body.question}

Answer concisely and factually based only on the evidence above."""

    answer = await _ask_llm(prompt)
    return {"question": body.question, "answer": answer, "investigation_id": investigation_id}


async def _ask_llm(prompt: str) -> str:
    if not OPENAI_API_KEY:
        return "LLM not configured. Please review the evidence summary above to make your decision."
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a fraud investigation assistant. Be concise and factual."},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=300,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("LLM clarify failed: %s", e)
        return f"Unable to generate answer: {e}"
