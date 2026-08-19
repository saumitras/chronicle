from datetime import datetime
from sqlalchemy import BigInteger, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from gateway.db.session import Base


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[str] = mapped_column(UUID(as_uuid=False), unique=True)
    aggregate_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    stream_version: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(100))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    producer: Mapped[str] = mapped_column(String(100))
    correlation_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    causation_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict] = mapped_column(JSONB)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InvestigationModel(Base):
    __tablename__ = "investigations"

    investigation_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    alert_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="running")
    decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewer_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlertModel(Base):
    __tablename__ = "alerts"

    alert_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    customer_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    account_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    device_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    merchant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vpn_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
