from dataclasses import dataclass


@dataclass
class ReviewDecisionSignal:
    reviewer_id: str
    decision: str       # "approve" | "deny"
    comment: str = ""
    decided_at: str = ""
