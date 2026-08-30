# Obligation Agent

> **AI-Powered Reciprocal Obligation & Commitment Intelligence System**  
> *Where the Obligation — who owes what, to whom, by when, under what conditions, with evidence and source reference — is the atomic unit.*

---

## 🌟 Executive Summary & Core Philosophy

Conventional productivity tools operate on isolated, directionless "todo lists" and task checkboxes. **Obligation Agent** reconceptualizes commitments around **the Obligation as the atomic unit of work and relationship**.

### 1. The Obligation is the Atomic Unit
A task is merely an obligation rendered from the perspective of the duty bearer. Every obligation contains:
- **Owner (Duty Bearer)**: Who owes the deliverable
- **Beneficiary (Obligee)**: To whom the deliverable is owed
- **Action**: What specific duty or promise is owed
- **Deadline**: Nullable ISO timestamp (supports unconditional, relative, & conditional triggers)
- **Conditions**: Structured triggers (e.g., *"Once pricing numbers are confirmed"*)
- **Evidence**: Normalized observation timeline, audit logs, commit URLs, signed notes, or artifacts confirming completion
- **Status**: Controlled finite state machine (`DETECTED`, `CONFIRMED`, `IN_PROGRESS`, `COMPLETED`, `OVERDUE`, `CANCELLED`, `BLOCKED`)
- **Block Reason**: Structured causal explanation of prerequisite blockers (`blocked_by: [{obligation_id, owner, action, status, reason}]`)
- **Next Action**: Immediate tactical follow-up step
- **Source Reference**: Originating channel/message provenance
- **Obligation Type**: Directional categorization (`OWED_BY_ME` vs. `OWED_TO_ME`)
- **Confidence**: Field-level AI extraction & reasoning certainty breakdown

### 2. Obligations Form a Connected Graph
Real commitments are interconnected:
- **A DEPENDS ON B**: A cannot proceed until B completes. If B becomes `OVERDUE` or `BLOCKED`, A automatically becomes `BLOCKED` with full causal transparency.
- **A LINKED B**: Reciprocal or thematic connection between independent records without causing blocking.
- **Why PostgreSQL instead of Neo4j**: Relational edge junction tables with recursive traversal handle hundreds of thousands of commitments with zero distributed operational overhead and strict ACID transaction safety.

### 3. Evidence & Event Correlation (Did it actually happen?)
An obligation is a **claim about future or required action**; evidence is an **observation indicating possible fulfillment**.
The system correlates:
$$\text{Obligation} + \text{External Event / Observation} = \text{Possible Fulfillment}$$
- **Zero Blind Auto-Completion**: Human confirmation remains authoritative. High-confidence evidence produces a candidate for verification.
- **Authoritative Graph Cascade**: When human confirmation completes a prerequisite, dependent obligations in the graph automatically unblock!

### 4. Human-Controlled Interventions & Follow-Up (Phase 6)
Transforming proactive risk intelligence into human-authorized interventions:
$$\text{Risk Engine} \to \text{Intervention Plan} \to \text{Human Review} \to \text{User Approval} \to \text{Execution / Schedule} \to \text{Observation / Correlation} \to \text{Auto-Resolution}$$
- **Human in the Loop**: The agent plans drafts and suggests targets; the human user edits, approves, and triggers execution.
- **Zero Autonomous Messaging**: The agent never sends external emails or messages without explicit human action.
- **Deterministic Fact Grounding**: Message drafts are derived solely from verified obligation facts (blockers, deadlines, duty direction). Zero hallucinations.
- **Deduplication & Anti-Spam Cooldown**: 24-hour cooldown per obligation + intervention type, max chain depth of 3 with escalation recommendations.

---

## ⚡ Closed-Loop Architecture (Phases 1 to 6)

```
                 ┌───────────────┐
                 │  Obligation   │
                 └───────┬───────┘
                         │
                         ▼
                ┌────────────────┐
                │   RiskEngine   │ (Multi-signal failure scoring)
                └───────┬────────┘
                        │
                        ▼
              ┌────────────────────┐
              │ RecommendationEngine│ (Explainable action recommendations)
              └──────────┬─────────┘
                         │
                         ▼
              ┌────────────────────┐
              │ InterventionPlanner│ (Deduplication, Cooldown, Draft Generation)
              └──────────┬─────────┘
                         │
                         ▼
               ┌──────────────────┐
               │ Human Review UI  │ (Modal & /interventions/[id])
               └────────┬─────────┘
                        │
             ┌──────────┴──────────┐
             ▼                     ▼
         APPROVE                 CANCEL
             │
             ▼
        SCHEDULE / EXECUTE
             │
             ▼
       External Event (Slack / Email / File)
             │
             ▼
       EventClassifier (Completion vs Progress vs Blocker)
             │
             ▼
 EvidenceCorrelationService (Match Scoring & HITL Review)
             │
             ▼
       StatusMachine (Transition to COMPLETED)
             │
             ▼
        GraphService (Cascade Unblock Dependents)
             │
             ▼
     InterventionService (Auto-Resolve -> RESOLVED)
             │
             ▼
          RiskEngine (Risk Drops to 0%)
```

---

## 🏛️ System Architecture

```
obligation_agent/
├── backend/                        # FastAPI Async Python Engine
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py             # Dependency injection & service resolution
│   │   │   └── routes/
│   │   │       ├── dashboard.py    # /api/dashboard summary metrics
│   │   │       ├── events.py       # /api/events analyze & ingest endpoints
│   │   │       ├── health.py       # /api/health
│   │   │       ├── obligations.py  # /api/obligations CRUD, extract, status, graph & risk
│   │   │       ├── risk.py         # /api/risk bulk prioritized risk feed
│   │   │       └── interventions.py# /api/interventions planning, approval, execution & queue
│   │   ├── core/
│   │   │   ├── config.py           # Pydantic Settings & environment handling
│   │   │   ├── confidence.py       # Centralized thresholds & ambiguity evaluation
│   │   │   ├── database.py         # SQLAlchemy async engine (PostgreSQL / SQLite fallback)
│   │   │   ├── logging.py          # Structured logger
│   │   │   ├── status_machine.py   # Controlled finite state machine, RiskLevel & ActionType
│   │   │   └── intervention_status.py # InterventionStatus, InterventionType, InterventionOutcome
│   │   ├── models/
│   │   │   └── obligation.py       # Obligation, ObligationEdge, Evidence, & Intervention ORM entities
│   │   ├── schemas/
│   │   │   ├── obligation.py       # Pydantic V2 Obligation, Risk & Evidence schemas
│   │   │   └── intervention.py     # Pydantic V2 Intervention schemas & queue models
│   │   ├── services/
│   │   │   ├── message_generator.py # Fact-grounded deterministic message draft generator
│   │   │   ├── intervention_planner.py # Multi-signal planner, deduplicator & cooldown manager
│   │   │   ├── intervention_executor.py # BaseInterventionExecutor & DevMockInterventionExecutor
│   │   │   ├── intervention_service.py # Core intervention CRUD, approval, execution & auto-resolution
│   │   │   ├── risk_engine.py      # Multi-signal scoring & graph fan-out engine
│   │   │   ├── recommendation_engine.py # Actionable, explainable recommendation generator
│   │   │   ├── event_classifier.py # Semantic role classification engine
│   │   │   ├── correlation_service.py # Multi-signal match scoring & explainability
│   │   │   ├── event_ingestion_service.py # Ingestion & deduplication service
│   │   │   ├── graph_service.py    # Graph traversal, cycle prevention & propagation engine
│   │   │   ├── context_analyzer.py # Context normalization & entity resolution
│   │   │   ├── ownership_agent.py  # 1st/2nd/3rd person, reciprocal, & ambiguity reasoning
│   │   │   ├── deadline_agent.py   # Explicit, relative, conditional, & vague date reasoning
│   │   │   ├── extraction_service.py # Multi-stage reasoning pipeline orchestrator
│   │   │   └── obligation_service.py # Domain CRUD, state transitions, evidence & auto-resolution
│   │   └── main.py                 # FastAPI application, CORS & Lifespan
│   ├── alembic/                    # Database version migrations
│   │   └── versions/
│   │       ├── 001_initial_schema.py
│   │       ├── 002_add_graph_support.py
│   │       ├── 003_add_evidence_model.py
│   │       └── 004_add_intervention_model.py
│   ├── tests/                      # Automated test suite (114 tests)
│   │   ├── test_health.py
│   │   ├── test_extraction.py
│   │   ├── test_obligations.py
│   │   ├── test_dashboard.py
│   │   ├── test_phase2_reasoning.py
│   │   ├── test_phase3_graph.py
│   │   ├── test_phase4_evidence.py
│   │   ├── test_phase5_risk.py
│   │   └── test_phase6_intervention.py # 33 comprehensive intervention tests
│   ├── seed.py                     # Canonical demo seed data with interventions, risk & graph
│   └── requirements.txt
│
└── frontend/                       # Next.js 15 App Router & React 19 Client
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx          # Root shell layout with Navigation Header
    │   │   ├── page.tsx            # Dashboard with Intervention Action Queue & Risk Rescue
    │   │   ├── capture/
    │   │   │   └── page.tsx        # Obligation Extraction & Event Simulator
    │   │   ├── interventions/
    │   │   │   └── [id]/
    │   │   │       └── page.tsx    # Intervention Audit Trail & Outcome Recording Detail
    │   │   └── obligations/
    │   │       ├── page.tsx        # Ledger view with status, risk, and type filters
    │   │       └── [id]/
    │   │           └── page.tsx    # Detail view with Interventions History & Risk Inspector
    │   ├── components/
    │   │   ├── obligations/
    │   │   │   ├── ObligationCard.tsx
    │   │   │   ├── RiskCard.tsx
    │   │   │   ├── ObligationList.tsx
    │   │   │   └── ReviewCard.tsx
    │   │   ├── interventions/
    │   │   │   ├── InterventionCard.tsx # Reusable Intervention Action Card
    │   │   │   └── InterventionReviewModal.tsx # HITL Review, Edit, Approve & Schedule Modal
    │   │   └── ui/
    │   │       ├── StatusBadge.tsx
    │   │       ├── ConfidenceBadge.tsx
    │   │       └── ToastContext.tsx
    │   └── lib/
    │       ├── api/                # API client with obligationsApi and interventionsApi
    │       └── types/              # Synchronized TypeScript domain interfaces
    └── package.json
```

---

## ⚡ Quickstart & Local Setup

### 1. Backend Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows (or source venv/bin/activate on Unix)
pip install -r requirements.txt

# Run migrations & seed demo scenarios
alembic upgrade head
python seed.py

# Start FastAPI dev server
uvicorn app.main:app --reload --port 8000
```
- API Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/health`

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
- Web Application: `http://localhost:3000`

### 5. Continuous Event Ingestion & Provider Integration (Phase 7)
Phase 7 enables continuous, provider-agnostic event ingestion through a clean adapter layer:
$$\text{Provider Webhook / Payload} \to \text{BaseProvider Adapter} \to \text{ExternalEvent} \to \text{Deduplication Check} \to \text{Semantic Classification} \to \text{Correlation & Evidence} \to \text{Intervention Update} \to \text{Immutable Audit Log}$$
- **Provider Agnostic Architecture**: Core domain is completely decoupled from external protocols. The system defines `BaseProvider` and registers providers via `ProviderRegistry`.
- **Deterministic Mock Provider**: Implements canonical Scenarios A (Completion), B (Progress), C (Blocker), D (Request), and E (Chatter) alongside custom dictionary payloads.
- **Strict Idempotency & Deduplication**: Ingesting the same provider + `source_ref` repeatedly guarantees `DUPLICATE` detection without creating double evidence records or side effects.
- **Closed-Loop Intervention Feedback**: Incoming progress events automatically acknowledge active interventions with outcome `PROGRESS_REPORTED`, reducing active risk and advancing coordination state.
- **Immutable Ingestion Audit Trail**: Every received payload is stored in `ingested_events` with semantic classifications, correlated entity IDs, match explanations, and action outcomes.

---

## ⚡ Closed-Loop Architecture (Phases 1 to 7)

```
                 ┌───────────────┐
                 │  Obligation   │
                 └───────┬───────┘
                         │
                         ▼
                ┌────────────────┐
                │   RiskEngine   │ (Multi-signal failure scoring)
                └───────┬────────┘
                        │
                        ▼
              ┌────────────────────┐
              │ RecommendationEngine│ (Explainable action recommendations)
              └──────────┬─────────┘
                         │
                         ▼
              ┌────────────────────┐
              │ InterventionPlanner│ (Deduplication, Cooldown, Draft Generation)
              └──────────┬─────────┘
                         │
                         ▼
               ┌──────────────────┐
               │ Human Review UI  │ (Modal & /interventions/[id])
               └────────┬─────────┘
                        │
             ┌──────────┴──────────┐
             ▼                     ▼
         APPROVE                 CANCEL
             │
             ▼
        SCHEDULE / EXECUTE
             │
             ▼
       Provider Ingestion (Mock / Slack / Webhook)
             │
             ▼
       BaseProvider Adapter -> Normalized ExternalEvent
             │
             ▼
       Deduplication Check (ingested_events)
             │
             ▼
       EventClassifier (Completion vs Progress vs Blocker)
             │
             ▼
 EvidenceCorrelationService (Match Scoring & SUGGESTED Evidence)
             │
             ▼
  Intervention Correlation (Auto-Update to ACKNOWLEDGED)
             │
             ▼
       Human Review & Confirmation
             │
             ▼
       StatusMachine (Transition to COMPLETED)
             │
             ▼
        GraphService (Cascade Unblock Dependents)
```

---

## 🧪 Verification & Test Suite

Obligation Agent maintains 100% test coverage across all architectural layers.

```bash
cd backend
pytest -v
```

**Results (136/136 Tests Passing):**
- **Phase 1 Baseline (9 tests)**: CRUD, controlled state transitions, candidate extraction.
- **Phase 2 Reasoning (10 tests)**: Ownership agent, deadline agent, conditional deadlines, ambiguity checks.
- **Phase 3 Graph (14 tests)**: Relational edges, DFS cycle rejection, cascade blocking, multi-hop propagation, auto-unblocking.
- **Phase 4 Evidence (22 tests)**: Event ingestion, deduplication, semantic role classification, candidate scoring, human confirmation & rejection, graph cascade unblocking.
- **Phase 5 Risk Engine (26 tests)**: Deadline pressure, dependency blockers, progress decay, conflicting evidence, ownership uncertainty, graph fan-out priority, explainable recommendations, bulk risk filtering.
- **Phase 6 Interventions (33 tests)**: Planner logic, deterministic drafts, approval enforcement, scheduling, mock execution, cooldown (24h), deduplication, chain depth & escalation, audit logging, post-intervention event correlation, auto-resolution.
- **Phase 7 Continuous Ingestion (22 tests)**: Provider registry, MockProvider canonical scenarios, dictionary normalization, deduplication & idempotency, semantic classification, candidate scoring, intervention acknowledgement, graph propagation, audit trail queries, and webhook routing.

```bash
cd frontend
npm run lint   # 0 errors, 0 warnings
npm run build  # All 8 static and dynamic routes compile cleanly
```
