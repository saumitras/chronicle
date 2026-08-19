import json
from datetime import datetime
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from gateway.db.models import EventModel, InvestigationModel, AlertModel


# ── Events ────────────────────────────────────────────────────────────────────

async def append_event(db: AsyncSession, envelope: dict) -> dict:
    row = EventModel(
        event_id=envelope["event_id"],
        aggregate_id=envelope["aggregate_id"],
        stream_version=envelope["stream_version"],
        event_type=envelope["event_type"],
        timestamp=datetime.fromisoformat(envelope["timestamp"]),
        producer=envelope["producer"],
        correlation_id=envelope.get("correlation_id"),
        causation_id=envelope.get("causation_id"),
        workflow_id=envelope.get("workflow_id"),
        trace_id=envelope.get("trace_id"),
        schema_version=envelope.get("schema_version", 1),
        payload=envelope["payload"] if isinstance(envelope["payload"], dict) else json.loads(envelope["payload"]),
    )
    try:
        db.add(row)
        await db.commit()
        return envelope
    except IntegrityError:
        await db.rollback()
        raise


async def get_events_by_aggregate(db: AsyncSession, aggregate_id: str) -> list[dict]:
    result = await db.execute(
        select(EventModel)
        .where(EventModel.aggregate_id == aggregate_id)
        .order_by(EventModel.stream_version)
    )
    return [_event_to_dict(r) for r in result.scalars().all()]


async def get_recent_events(db: AsyncSession, limit: int = 50, since: str | None = None) -> list[dict]:
    q = select(EventModel).order_by(EventModel.timestamp.desc())
    if since:
        q = q.where(EventModel.timestamp > datetime.fromisoformat(since))
    q = q.limit(limit)
    result = await db.execute(q)
    return [_event_to_dict(r) for r in result.scalars().all()]


def _event_to_dict(r: EventModel) -> dict:
    return {
        "event_id": r.event_id,
        "aggregate_id": r.aggregate_id,
        "stream_version": r.stream_version,
        "event_type": r.event_type,
        "timestamp": r.timestamp.isoformat(),
        "producer": r.producer,
        "correlation_id": r.correlation_id,
        "causation_id": r.causation_id,
        "workflow_id": r.workflow_id,
        "trace_id": r.trace_id,
        "schema_version": r.schema_version,
        "payload": r.payload,
    }


# ── Investigations ─────────────────────────────────────────────────────────────

async def get_investigations(db: AsyncSession, status: str | None = None, limit: int = 100) -> list[dict]:
    q = select(InvestigationModel).order_by(InvestigationModel.created_at.desc()).limit(limit)
    if status:
        q = q.where(InvestigationModel.status == status)
    result = await db.execute(q)
    return [_inv_to_dict(r) for r in result.scalars().all()]


async def get_investigation(db: AsyncSession, investigation_id: str) -> dict | None:
    result = await db.execute(
        select(InvestigationModel).where(InvestigationModel.investigation_id == investigation_id)
    )
    row = result.scalar_one_or_none()
    return _inv_to_dict(row) if row else None


def _inv_to_dict(r: InvestigationModel) -> dict:
    return {
        "investigation_id": r.investigation_id,
        "alert_id": r.alert_id,
        "workflow_id": r.workflow_id,
        "status": r.status,
        "decision": r.decision,
        "risk_score": r.risk_score,
        "reviewer_id": r.reviewer_id,
        "reviewer_comment": r.reviewer_comment,
        "payload": r.payload,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


# ── Alerts ─────────────────────────────────────────────────────────────────────

async def get_alerts(db: AsyncSession, limit: int = 50) -> list[dict]:
    result = await db.execute(
        select(AlertModel).order_by(AlertModel.created_at.desc()).limit(limit)
    )
    return [_alert_to_dict(r) for r in result.scalars().all()]


async def get_alert(db: AsyncSession, alert_id: str) -> dict | None:
    result = await db.execute(
        select(AlertModel).where(AlertModel.alert_id == alert_id)
    )
    row = result.scalar_one_or_none()
    return _alert_to_dict(row) if row else None


def _alert_to_dict(r: AlertModel) -> dict:
    return {
        "alert_id": r.alert_id,
        "customer_id": r.customer_id,
        "merchant": r.merchant,
        "amount": r.amount,
        "currency": r.currency,
        "country": r.country,
        "vpn_detected": r.vpn_detected,
        "status": r.status,
        "payload": r.payload,
        "created_at": r.created_at.isoformat(),
    }


# ── Dashboard stats ────────────────────────────────────────────────────────────

async def get_dashboard_stats(db: AsyncSession) -> dict:
    total_alerts = await db.scalar(select(func.count()).select_from(AlertModel))
    total_investigations = await db.scalar(select(func.count()).select_from(InvestigationModel))

    decision_rows = await db.execute(
        select(InvestigationModel.decision, func.count())
        .group_by(InvestigationModel.decision)
    )
    decisions = {row[0] or "PENDING": row[1] for row in decision_rows}

    status_rows = await db.execute(
        select(InvestigationModel.status, func.count())
        .group_by(InvestigationModel.status)
    )
    statuses = {row[0]: row[1] for row in status_rows}

    recent = await get_recent_events(db, limit=20)

    return {
        "total_alerts": total_alerts or 0,
        "total_investigations": total_investigations or 0,
        "decisions": decisions,
        "statuses": statuses,
        "recent_events": recent,
    }
