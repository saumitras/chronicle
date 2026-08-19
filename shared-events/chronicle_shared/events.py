class EventType:
    # Alert lifecycle
    ALERT_CREATED = "AlertCreated"

    # Investigation lifecycle
    INVESTIGATION_STARTED = "InvestigationStarted"
    INVESTIGATION_COMPLETED = "InvestigationCompleted"

    # Agent evidence events
    DEVICE_EVIDENCE_COLLECTED = "DeviceEvidenceCollected"
    GEO_EVIDENCE_COLLECTED = "GeoEvidenceCollected"
    CUSTOMER_EVIDENCE_COLLECTED = "CustomerEvidenceCollected"
    # Absence is a fact too: an evidence source that exhausted its retries
    # is recorded explicitly, so a consumer can tell "no risk found" apart
    # from "never looked".
    EVIDENCE_UNAVAILABLE = "EvidenceUnavailable"

    # LLM reasoning
    LLM_REASONING_GENERATED = "LLMReasoningGenerated"

    # Risk assessment
    RISK_ASSESSED = "RiskAssessed"

    # Human-in-the-loop
    MANUAL_REVIEW_REQUESTED = "ManualReviewRequested"
    MANUAL_REVIEW_COMPLETED = "ManualReviewCompleted"
