import { useMemo } from 'react'

export function useDerivedState(events, atTs) {
  return useMemo(() => {
    const visible = atTs
      ? events.filter(e => new Date(e.timestamp).getTime() <= atTs)
      : events

    const state = {
      status: null, decision: null, riskScore: null,
      deviceEvidence: null, geoEvidence: null, customerEvidence: null,
      llmReasoning: null, riskFlags: [], requiresReview: false,
      reviewerDecision: null,
    }

    for (const e of visible) {
      const p = e.payload || {}
      if (e.event_type === 'InvestigationStarted') state.status = 'running'
      if (e.event_type === 'DeviceEvidenceCollected') state.deviceEvidence = p.evidence
      if (e.event_type === 'GeoEvidenceCollected') state.geoEvidence = p.evidence
      if (e.event_type === 'CustomerEvidenceCollected') state.customerEvidence = p.evidence
      if (e.event_type === 'LLMReasoningGenerated') {
        state.llmReasoning = p.reasoning
        state.riskFlags = p.risk_flags || []
      }
      if (e.event_type === 'RiskAssessed') {
        state.riskScore = p.risk_score
        state.decision = p.decision
      }
      if (e.event_type === 'ManualReviewRequested') {
        state.status = 'pending_review'
        state.requiresReview = true
      }
      if (e.event_type === 'ManualReviewCompleted') {
        state.reviewerDecision = { decision: p.decision, reviewer: p.reviewer_id, comment: p.comment }
      }
      if (e.event_type === 'InvestigationCompleted') {
        state.status = 'completed'
        state.decision = p.decision
        state.riskScore = p.risk_score ?? state.riskScore
      }
    }
    return state
  }, [events, atTs])
}
