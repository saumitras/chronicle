# Chronicle

Chronicle is a reference implementation showing how **event sourcing**, **Apache Kafka**, **Temporal**, and a **LangGraph** agent compose into a system that is replayable, explainable, and safe to operate: every decision is derived from an immutable log of facts, agents propose evidence but deterministic policy decides, and a projection can be deleted and rebuilt from history at any time.

## How it works

```text
Alert Generator ──AlertCreated──▶ Kafka (chronicle.alerts)
                                     │
                                     ▼
                      Temporal InvestigationWorkflow
                                     │
              ┌──────────────────────┼──────────────────────┐
              │  device-agent │ geo-agent │ customer-agent  │   evidence, in parallel
              │  investigation-agent (LangGraph ReAct loop) │   reasoning (proposal)
              │  policy-agent (deterministic scoring)       │   decision
              └──────────────────────┬──────────────────────┘
                                     ▼
                     Postgres event store  (append-only, system of record)
                                     │  outbox relay
                                     ▼
                          Kafka (chronicle.events)
                                     │
                                     ▼
                     Projection service ──▶ read models ──▶ Dashboard UI
```

## Run it

Requires Docker. From the repo root:

```bash
cp .env.example .env        # defaults work; add OPENAI_API_KEY for real LLM reasoning
docker compose up -d --build
```

| Service | URL |
|---|---|
| Dashboard UI | http://localhost:3000 |
| Gateway API | http://localhost:8000 |
| Alert generator | http://localhost:8001 |
| Temporal UI | http://localhost:8080 |

Without an OpenAI key the investigation agent falls back to mock reasoning — everything else behaves identically, and the reasoning event records `degraded: true` with the reason rather than passing the fallback off as real output. On first start the seeder creates reference data and 15 historical investigations, and the generator produces a new alert every ~10s.

## Walk through a case

```bash
# 1. Generate a high-risk alert
curl -X POST "localhost:8001/alerts/generate?risk_profile=high"
# → {"alert_id": "3cb79dc4-...", "risk_profile": "high"}

# 2. Read its event stream from the store
docker exec chronicle-postgres psql -U chronicle -d chronicle \
  -c "SELECT stream_version, event_type, producer FROM events
      WHERE aggregate_id='<alert_id>' ORDER BY stream_version;"

# 3. If it landed in REVIEW (score 0.35–0.70), approve it
curl -X POST localhost:8000/investigations/<alert_id>/approve \
  -H 'content-type: application/json' \
  -d '{"reviewer_id":"you","decision":"approve","comment":"looks fine"}'

# 4. Prove the read models are disposable: wipe and rebuild them
curl -X POST localhost:8000/admin/replay
# → {"status": "done", "events_replayed": ...}
```

Or do all of it from the dashboard: generate alerts, watch events stream in live, approve/deny review cases, scrub an investigation's timeline back and forth, and trigger replay.

Try killing things mid-flight: `docker kill chronicle-agents` while an investigation is running, then `docker compose up -d agents`. Temporal retries the interrupted activity and the investigation completes as if nothing happened.

Or make an evidence source fail permanently — raise at the top of `run_customer_agent` and rebuild the agents image. The case doesn't stall: `EvidenceUnavailable` is recorded in that source's stream slot, and the policy gate refuses to approve on partial coverage, routing to human review instead.

## Repository layout

| Directory | What it is |
|---|---|
| `shared-events/` | Event vocabulary, envelope schema, upcaster registry |
| `alert-generator/` | Synthetic alert source + reference-data seeder |
| `orchestrator/` | Temporal workflow, activities, outbox relay, Kafka consumer |
| `agents/` | Five agent activities: device, geo, customer (evidence), LangGraph investigation (reasoning), policy (decision) |
| `projection-service/` | Kafka consumer folding events into read models; replay |
| `gateway/` | REST API over read models + event store; HITL approve endpoint |
| `ui/` | React dashboard (Vite + Tailwind) |
| `ops/` | Dockerfile, Postgres schema, migrations |
| `tests/smoke/` | End-to-end demo scenarios (`SMOKE_GATEWAY_URL` to point elsewhere) |

## Configuration

All via environment (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | _(empty → mock reasoning)_ | LLM for the investigation agent and reviewer clarify |
| `OPENAI_MODEL` | `gpt-6-luna` | Model used for reasoning |
| `INVESTIGATION_AGENT_MAX_STEPS` | `8` | LangGraph recursion limit — graph *supersteps*, not turns |
| `ALERT_INTERVAL_SECONDS` | `10` | Auto-generation cadence |
| `HITL_REVIEW_TIMEOUT_SECONDS` | `172800` | Review window before auto-expiry (48h) |
| `HITL_NOTIFY_CHANNEL` | `none` | `email` / `slack` / `none` reviewer notification |
| `DOMAIN` | `http://localhost:3000` | Dashboard base URL used for the review link in notifications |
| `HITL_EMAIL_FROM` | `noreply@example.com` | Sender address for review emails (set to a domain you own) |
| `OUTBOX_POLL_INTERVAL_SECONDS` | `0.5` | Outbox relay poll cadence |
