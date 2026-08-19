import asyncio
import logging
import os
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from orchestrator.activities.agent_activities import append_event, send_hitl_notification
    from orchestrator.signals import ReviewDecisionSignal
    from chronicle_shared.schema import EventEnvelope
    from chronicle_shared.events import EventType

logger = logging.getLogger(__name__)

RETRY = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
)

# How long a manual review may sit unanswered before the investigation
# auto-expires. Read once at worker startup; changing it mid-flight only
# applies cleanly to new workflows (the timer is part of workflow history,
# so replays of already-waiting workflows must see the same value).
REVIEW_TIMEOUT = timedelta(seconds=int(os.getenv("HITL_REVIEW_TIMEOUT_SECONDS", "172800")))  # 48h

# (activity, source name, state key, stream position). The position is where
# either the evidence event or its EvidenceUnavailable counterpart is written.
EVIDENCE_AGENTS = [
    ("run_device_agent",   "device",   "device_evidence",   2),
    ("run_geo_agent",      "geo",      "geo_evidence",      3),
    ("run_customer_agent", "customer", "customer_evidence", 4),
]


@workflow.defn
class InvestigationWorkflow:
    def __init__(self):
        self._approval: Optional[ReviewDecisionSignal] = None
        self._waiting: bool = False

    @workflow.signal
    async def review_decision(self, signal: ReviewDecisionSignal) -> None:
        # Signals are fire-and-forget, so validate defensively: accept a
        # decision only while a review is actually pending, once, and only
        # with a known verdict. Late, duplicate or malformed signals are
        # logged and ignored rather than silently overwriting state.
        if not self._waiting:
            workflow.logger.info("Ignoring review decision: no review pending")
            return
        if self._approval is not None:
            workflow.logger.info("Ignoring duplicate review decision")
            return
        if str(signal.decision).lower() not in ("approve", "deny"):
            workflow.logger.warning("Ignoring invalid review decision: %r", signal.decision)
            return
        self._approval = signal

    @workflow.query
    def is_waiting(self) -> bool:
        return self._waiting

    @workflow.run
    async def run(self, alert: dict) -> dict:
        investigation_id = alert["alert_id"]
        workflow_id = workflow.info().workflow_id

        # correlation_id ties all events in this investigation together
        # causation_id links each event to the event that caused it
        alert_event_id = alert.get("event_id")          # AlertCreated event_id
        correlation_id = investigation_id                # same for all events in this investigation
        # trace_id starts at AlertCreated and follows the case across all logs
        trace_id = alert.get("trace_id") or str(workflow.uuid4())

        state = {
            "investigation_id": investigation_id,
            "alert_id": alert["alert_id"],
            "workflow_id": workflow_id,
            "alert": alert,
            "correlation_id": correlation_id,
            "trace_id": trace_id,
        }

        # ── InvestigationStarted — caused by AlertCreated ────────────────────
        # event_id/timestamp come from workflow.uuid4()/workflow.now(): the
        # envelope is built in workflow scope, so they must be deterministic
        # under replay (raw uuid4()/now() would differ on each replay).
        started = EventEnvelope(
            event_type=EventType.INVESTIGATION_STARTED,
            aggregate_id=investigation_id,
            producer="orchestrator",
            stream_version=1,
            event_id=str(workflow.uuid4()),
            timestamp=workflow.now().isoformat(),
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            causation_id=alert_event_id,
            trace_id=trace_id,
            payload={
                "investigation_id": investigation_id,
                "alert_id": alert["alert_id"],
                "kafka": alert.get("_kafka"),
            },
        )
        result = await workflow.execute_activity(
            append_event, started.to_dict(),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY,
        )
        # Track the event_id of InvestigationStarted for downstream causation
        state["last_event_id"] = result.get("event_id", started.event_id)

        # ── Evidence agents run in parallel ──────────────────────────────────
        # Each is an independent activity with its own retries; all three
        # evidence events share causation = InvestigationStarted, which is
        # exactly what parallel effects of one cause should record.
        started_event_id = state["last_event_id"]
        evidence_results = await asyncio.gather(
            *[
                workflow.execute_activity(
                    name, state,
                    task_queue="chronicle-agent-tasks",
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RETRY,
                )
                for name, _, _, _ in EVIDENCE_AGENTS
            ],
            # Partial failure is tolerated, not fatal: one dead source must not
            # stall the case. It becomes a recorded absence instead, and the
            # policy gate is coverage-aware so it can never be read as "clean".
            return_exceptions=True,
        )

        last_evidence_event_id = started_event_id
        for (_, source, key, version), result in zip(EVIDENCE_AGENTS, evidence_results):
            if isinstance(result, BaseException):
                # Unwrap Temporal's ActivityError so the recorded reason names
                # the real cause, not just "Activity task failed".
                cause = getattr(result, "cause", None)
                reason = f"{result}: {cause}" if cause is not None else str(result)
                # Materialize the absence as a fact at the stream position the
                # evidence would have occupied — silence is never left implicit.
                unavailable = EventEnvelope(
                    event_type=EventType.EVIDENCE_UNAVAILABLE,
                    aggregate_id=investigation_id,
                    producer="orchestrator",
                    stream_version=version,
                    event_id=str(workflow.uuid4()),
                    timestamp=workflow.now().isoformat(),
                    workflow_id=workflow_id,
                    correlation_id=correlation_id,
                    causation_id=started_event_id,
                    trace_id=trace_id,
                    payload={
                        "investigation_id": investigation_id,
                        "source": source,
                        "reason": reason[:500],
                    },
                )
                appended = await workflow.execute_activity(
                    append_event, unavailable.to_dict(),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RETRY,
                )
                workflow.logger.warning("Evidence source %s unavailable for %s",
                                        source, investigation_id)
                last_evidence_event_id = appended.get("event_id", unavailable.event_id)
            else:
                state[key] = result[key]
                last_evidence_event_id = result["last_event_id"]

        # Downstream causation: the last event in stream order (v4)
        state["last_event_id"] = last_evidence_event_id

        # ── Reasoning, then policy — sequential, each needs the last ─────────
        # The reasoning agent runs a multi-call LLM loop, so it heartbeats:
        # a dead worker is detected within heartbeat_timeout instead of
        # waiting out the full start_to_close before retrying elsewhere.
        state = await workflow.execute_activity(
            "run_investigation_agent", state,
            task_queue="chronicle-agent-tasks",
            start_to_close_timeout=timedelta(minutes=5),
            heartbeat_timeout=timedelta(seconds=30),
            retry_policy=RETRY,
        )
        state = await workflow.execute_activity(
            "run_policy_agent", state,
            task_queue="chronicle-agent-tasks",
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RETRY,
        )

        # ── HITL pause if review required ────────────────────────────────────
        if state.get("requires_review"):
            risk_event_id = state.get("last_event_id", correlation_id)
            review_event = EventEnvelope(
                event_type=EventType.MANUAL_REVIEW_REQUESTED,
                aggregate_id=investigation_id,
                producer="orchestrator",
                stream_version=7,
                event_id=str(workflow.uuid4()),
                timestamp=workflow.now().isoformat(),
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                causation_id=risk_event_id,
                trace_id=trace_id,
                payload={
                    "investigation_id": investigation_id,
                    "risk_score": state.get("risk_score"),
                    "reason": "Risk score in review zone",
                },
            )
            await workflow.execute_activity(
                append_event, review_event.to_dict(),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RETRY,
            )

            await workflow.execute_activity(
                send_hitl_notification,
                args=[investigation_id, state.get("risk_score", 0.0), workflow_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            self._waiting = True
            try:
                await workflow.wait_condition(
                    lambda: self._approval is not None,
                    timeout=REVIEW_TIMEOUT,
                )
            except asyncio.TimeoutError:
                pass  # review window elapsed — auto-expire below
            self._waiting = False

            approval = self._approval
            self._approval = None

            if approval is not None:
                review_payload = {
                    "investigation_id": investigation_id,
                    "reviewer_id": approval.reviewer_id,
                    "decision": approval.decision.upper(),
                    "comment": approval.comment,
                    "decided_at": approval.decided_at,
                }
            else:
                review_payload = {
                    "investigation_id": investigation_id,
                    "reviewer_id": "system",
                    "decision": "EXPIRED",
                    "comment": f"No review received within {REVIEW_TIMEOUT}; investigation auto-expired.",
                    "decided_at": workflow.now().isoformat(),
                }

            review_completed = EventEnvelope(
                event_type=EventType.MANUAL_REVIEW_COMPLETED,
                aggregate_id=investigation_id,
                producer="orchestrator",
                stream_version=8,
                event_id=str(workflow.uuid4()),
                timestamp=workflow.now().isoformat(),
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                causation_id=review_event.event_id,
                trace_id=trace_id,
                payload=review_payload,
            )
            await workflow.execute_activity(
                append_event, review_completed.to_dict(),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RETRY,
            )
            state["decision"] = review_payload["decision"]
            state["last_event_id"] = review_completed.event_id

        # ── InvestigationCompleted ───────────────────────────────────────────
        final_version = 9 if state.get("requires_review") else 7
        completed = EventEnvelope(
            event_type=EventType.INVESTIGATION_COMPLETED,
            aggregate_id=investigation_id,
            producer="orchestrator",
            stream_version=final_version,
            event_id=str(workflow.uuid4()),
            timestamp=workflow.now().isoformat(),
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            causation_id=state.get("last_event_id", correlation_id),
            trace_id=trace_id,
            payload={
                "investigation_id": investigation_id,
                "decision": state.get("decision", "APPROVE"),
                "risk_score": state.get("risk_score", 0.0),
            },
        )
        await workflow.execute_activity(
            append_event, completed.to_dict(),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY,
        )

        return state
