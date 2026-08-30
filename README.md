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

## 📅 Phase 10: Google Calendar Provider & Temporal Obligation Intelligence

Phase 10 integrates Google Calendar as the 3rd real provider adapter (`google_calendar`), adding **temporal obligation intelligence** while strictly upholding human safety boundaries.

### Core Principle: Context Without Usurpation
> *"A calendar event can provide temporal context without necessarily becoming a deadline... NEVER silently change an obligation deadline merely because a related calendar event exists."*

1. **Data Ingestion Adapter (`GoogleCalendarProvider`)**:
   - Implements `BaseProvider` (`provider_name = "google_calendar"`, `provider_version = "1.0.0"`).
   - Capabilities: `["events", "calendar", "meetings", "attendees", "oauth", "calendar_ingestion"]`.
   - Normalization: Ingests meeting title, description, organizer, attendees, responses, start/end timestamps, and timezone into `ExternalEvent` with deterministic `source_ref` (`google_calendar:<calendar_id>:<event_id>:<sequence>`).

2. **Temporal Correlation & Risk Engine (Signal 6)**:
   - Evaluates participant alignment (organizer/attendees matching obligation owner/beneficiary).
   - `UPCOMING_RELATED_MEETING`: Meeting scheduled within 36 hours (+0.10 Risk).
   - `RELATED_MEETING_COMPLETED_WITHOUT_COMPLETION`: Associated meeting concluded without confirmed deliverable (+0.15 Risk).
   - `RELATED_MEETING_RESCHEDULED`: Associated meeting was moved (+0.05 Risk).
   - `RELATED_MEETING_CANCELLED`: Associated meeting was cancelled (+0.05 Risk).

3. **Meeting-Driven Advisory Actions**:
   - `PREPARE_FOR_MEETING`: Proactive preparation for upcoming review meetings.
   - `FOLLOW_UP_AFTER_MEETING`: Follow up on deliverables expected during concluded meetings.
   - `REVIEW_RESCHEDULED_COMMITMENT`: Review timeline adjustments following rescheduled meetings.
   - `REVIEW_CANCELLED_MEETING`: Review commitment necessity after cancelled meetings.

4. **Human Safety Gate**:
   - Calendar events NEVER auto-complete obligations, NEVER overwrite deadlines, and NEVER auto-cancel obligations.

---

## ⚖️ Phase 11: Cross-Provider Obligation Reconciliation & Contradiction Intelligence

Phase 11 introduces cross-provider reasoning and contradiction detection when disparate sources (Slack, Gmail, Google Calendar, Mock) provide conflicting or reinforcing evidence regarding an obligation.

### Core Principle: Multi-Source Intelligence with Strict Safety Invariants
> *"If Slack says 'Still working on the benchmark report' and Gmail says 'Sent the benchmark report', the system must NOT automatically complete the obligation. It must identify the contradiction, formulate causal explanations, and gate the state transition behind authoritative human adjudication."*

1. **Reconciliation Service Engine (`ReconciliationService`)**:
   - Analyzes multi-provider evidence clusters with temporal sequencing.
   - Calculates **Consistency Score** (supporting corroboration) and **Contradiction Score** (conflicting signals).
   - Generates bulleted AI reasoning findings explaining detected contradictions.
   - Evaluates 6 canonical patterns (A: Completion vs Blocker, B: Completion vs Progress, C: Later Negative Signal, D: Conditional Conflict, E: Temporal Reversal, F: Multi-Source Corroboration).

2. **Authoritative Human Safety Gate**:
   - Zero autonomous completion: High consistency prepares a verified review candidate; contradictory evidence increases risk uncertainty.
   - Supported Human Adjudication Actions: `CONFIRM_COMPLETION`, `KEEP_OBLIGATION_ACTIVE`, `MARK_AS_STALE`, `DISMISS_CONTRADICTION`, `REOPEN_OBLIGATION`.

3. **Risk Engine & Advisory Actions (Signal 7)**:
   - Evaluates reconciliation status (`CONFLICTING_EVIDENCE` +0.20, `STRONG_SUPPORTING_EVIDENCE` -0.15, `AMBIGUOUS_RECONCILIATION` +0.10).
   - Generates prioritized advisory recommendations (`REVIEW_CONFLICTING_EVIDENCE`, `CONFIRM_COMPLETION_EVIDENCE`).

4. **Frontend Intelligence**:
   - `/reconciliation`: Overview page with metrics, status filters, and quick review triggers.
   - `/reconciliation/[id]`: Chronological evidence provenance timeline distinguishing supporting, conflicting, and contextual signals with provider badges.
   - `ReconciliationReviewModal.tsx`: Explicit decision adjudication modal.
   - Dashboard (`/`) and Obligation Detail (`/obligations/[id]`): Integrated evidence reconciliation status cards.

---

## 🧠 Phase 12: Obligation Intelligence & Predictive Pattern Learning

Phase 12 introduces historical pattern learning, explainable delay forecasting, and calibrated predictive intelligence on top of the deterministic foundation.

### Core Principle: Explainable Predictive Forecasting with Human Control
> *"The system learns from historical outcomes to project failure probabilities and delays for active commitments, providing transparent causal explanations without ever making autonomous status decisions or sending unapproved communications."*

1. **Historical Pattern Engine (`HistoricalPatternEngine`)**:
   - Computes neutral operational owner latencies, on-time delivery rates, and blocker frequencies.
   - Evaluates global delay latency distributions (`ON_TIME`, `UNDER_12_HOURS`, `12_TO_48_HOURS`, `OVER_48_HOURS`).
   - Measures prerequisite dependency bottleneck rates and intervention response turnarounds.

2. **Predictive Obligation Engine (`PredictiveObligationEngine`)**:
   - Pluggable `PredictionProvider` Protocol with reference implementation `DeterministicPredictionProvider` (`predictive-v1`).
   - Synthesizes current risk, temporal urgency, owner latency, dependency health, and cross-source evidence consistency into bounded probabilities $[0.05, 0.95]$.
   - Generates structured, human-readable explainable reason items with impact weights.
   - Formulates prioritized preventative recommendations (`FOLLOW_UP_OWNER`, `RESOLVE_DEPENDENCY`, `PREPARE_EVIDENCE_REVIEW`).

3. **Similarity Engine (`SimilarityEngine`)**:
   - Deterministic feature similarity engine ranking past commitments by keyword overlap, duty parties, and structural traits.
   - Returns factual historical comparison summaries (e.g. *"3 similar obligations observed: 2 completed on time, 1 late"*).

4. **Prediction Evaluation & Calibration (`PredictionEvaluationService`)**:
   - Compares persisted forecast snapshots against observed outcomes.
   - Calculates Brier score, Mean Absolute Error (MAE) on delay hours, calibration error, and high-risk precision.
   - Explicitly returns `INSUFFICIENT_HISTORY` when samples $< 3$.

5. **Frontend UI & User Experience**:
   - `/intelligence`: Analytics page with Active Forecasts, Historical Delay Trends, Owner Operational Delivery Patterns, and Model Calibration metrics.
   - `PredictionCard.tsx`: Reusable probability meter card with expected delay projections and explainable signals.
   - Dashboard (`/`) and Obligation Detail (`/obligations/[id]`): Integrated predictive intelligence sections.

---

## 🔄 Phase 13: Adaptive Prediction, Calibration & Intelligence Feedback Layer

Phase 13 introduces closed-loop intelligence adaptation, empirical feature usefulness scoring, and model comparison:

1. **Adaptive Prediction Provider (`adaptive-v1`)**:
   - Calibrated prediction provider implementing the `PredictionProvider` Protocol.
   - Combines baseline risk priors with learned feature contributions, bounded strictly within $[0.05, 0.95]$.

2. **Online Statistical Weight Learning (`WeightLearningEngine`)**:
   - Bounded online statistical learning rate ($\alpha = 0.15$) with weights constrained to $[0.05, 0.40]$.
   - Evaluates feature reliability scores and historical usefulness categories (`HIGHLY_PREDICTIVE`, `MODERATELY_USEFUL`, `NEUTRAL`).

3. **Statistical Calibration & Data Sufficiency (`CalibrationEngine`)**:
   - Brier score, Calibration Error, MAE delay error, and high-risk precision metrics.
   - Explicit data sufficiency gating: `INSUFFICIENT_HISTORY` ($< 3$ evaluations), `LOW_SAMPLE` ($3..9$), and `CALIBRATION_AVAILABLE` ($10+$).

4. **Model Comparison & Benchmark**:
   - Side-by-side comparative evaluation of `predictive-v1` (baseline) and `adaptive-v1` (calibrated) with transparent adjustment reasons.

5. **Objective Intervention Efficacy Analytics**:
   - Measures observed completion rates for commitments with vs without human-authorized interventions using neutral operational language.

---

## 🏢 Phase 14: Identity, Workspace, Authentication & Authorization Layer

Phase 14 transforms Obligation Agent into an enterprise multi-tenant, role-governed commitment operating system:

```text
USER → AUTHENTICATION → WORKSPACE / ORGANIZATION → MEMBERSHIP + ROLE → AUTHORIZATION → WORKSPACE-SCOPED OBLIGATION AGENT DATA
```

1. **Authentication & Cryptography Core (`app.core.security`)**:
   - **Password Hashing**: PBKDF2-HMAC-SHA256 with 100,000 iterations and 16-byte cryptorandom salt.
   - **Constant-Time Verification**: `secrets.compare_digest` to eliminate timing side-channel vulnerabilities.
   - **Cryptographically Signed Session Tokens**: HMAC-SHA256 signed tokens paired with HTTP-only cookies (`obligation_session`).

2. **Multi-Tenant Data Architecture & Alembic Migration 010**:
   - `users`: `id`, `email` (unique), `password_hash`, `display_name`, `is_active`, timestamps.
   - `workspaces`: `id`, `name`, `slug` (unique), timestamps.
   - `workspace_memberships`: `id`, `workspace_id`, `user_id`, `role` (`OWNER`, `ADMIN`, `MEMBER`, `VIEWER`), unique `(workspace_id, user_id)`.
   - **Tenancy Scoping**: `workspace_id` added across `obligations`, `obligation_edges`, `obligation_evidence`, `interventions`, `ingested_events`, `reconciliation_records`, `integration_connections`, `obligation_outcome_snapshots`, `prediction_snapshots`, and `prediction_feedbacks`.
   - **Actor Tracking**: `actor_user_id` added to `obligation_evidence`, `interventions`, and `reconciliation_records`.

3. **Role-Based Access Control (RBAC)**:
   - `OWNER (40)`: Full organization control, workspace deletion, role delegation.
   - `ADMIN (30)`: Integration management, member invitation, role promotions.
   - `MEMBER (20)`: Obligation creation, editing, intervention planning & approval, evidence review.
   - `VIEWER (10)`: Read-only ledger, graph, and intelligence visibility. Mutations return `HTTP 403 Forbidden`.

4. **Multi-Tenant Security Invariants**:
   - **Server-Side Isolation**: Every SQL query and graph traversal is scoped strictly by `workspace_id`.
   - **IDOR Protection**: Attempting to read or mutate entities belonging to a foreign workspace returns `HTTP 404 Not Found`.
   - **Zero Secrets in API Responses**: Encrypted credentials and session secrets are never exposed in serialized JSON responses.
   - **Graceful Backward-Compatibility**: Unauthenticated dev/test calls automatically fall back to the default development identity (`demo@obligation.local` in `Default Workspace`), ensuring 100% legacy test compatibility.

5. **Frontend Enterprise UI**:
   - `AuthContext`: Centralized session persistence, workspace switching, and role-based capability checking.
   - `/login` & `/register`: Modern glassmorphic authentication cards with quick demo account autofill.
   - `Sidebar.tsx`: Multi-workspace switcher dropdown, active role badge (`OWNER`, `ADMIN`, `MEMBER`, `VIEWER`), and user profile footer.

---

## 🧪 Verification & Test Suite

Obligation Agent maintains 100% test coverage across all 14 architectural phases.

```bash
cd backend
pytest -v
```

**Results (332/332 Tests Passing):**
- **Phase 1 Baseline (9 tests)**: CRUD, controlled state transitions, candidate extraction.
- **Phase 2 Reasoning (10 tests)**: Ownership agent, deadline agent, conditional deadlines, ambiguity checks.
- **Phase 3 Graph (14 tests)**: Relational edges, DFS cycle rejection, cascade blocking, multi-hop propagation, auto-unblocking.
- **Phase 4 Evidence (22 tests)**: Event ingestion, deduplication, semantic role classification, candidate scoring, human confirmation & rejection, graph cascade unblocking.
- **Phase 5 Risk Engine (26 tests)**: Deadline pressure, dependency blockers, progress decay, conflicting evidence, ownership uncertainty, graph fan-out priority, explainable recommendations, bulk risk filtering.
- **Phase 6 Interventions (33 tests)**: Planner logic, deterministic drafts, approval enforcement, scheduling, mock execution, cooldown (24h), deduplication, chain depth & escalation, audit logging, post-intervention event correlation, auto-resolution.
- **Phase 7 Continuous Ingestion (22 tests)**: Provider registry, MockProvider canonical scenarios, dictionary normalization, deduplication & idempotency, semantic classification, candidate scoring, intervention acknowledgement, graph propagation, audit trail queries, and webhook routing.
- **Phase 8 Slack Integration (28 tests)**: Slack adapter, Events API normalization, signature verification, OAuth connect & token storage, threaded messages, and health tests.
- **Phase 9 Gmail Integration (32 tests)**: Gmail adapter, email normalization, Google OAuth 2.0 with CSRF state, Pub/Sub webhook push handling, attachment metadata, and multi-provider coexistence.
- **Phase 10 Google Calendar Integration (40 tests)**: Calendar adapter, meeting normalization, attendee responses, OAuth state, temporal correlation, Risk Signal 6, meeting advisory actions, webhooks, graph cascade unblocking, and multi-provider regression.
- **Phase 11 Cross-Provider Reconciliation (14 tests)**: Single/multi-provider agreement, contradiction patterns (A-F), temporal ordering, conditional conflict, human review actions, graph unblocking cascade, reopening behavior, idempotency, audit trail immutability, Signal 7 risk scoring, and REST APIs.
- **Phase 12 Predictive Intelligence (23 tests)**: Outcome classification, owner operational metrics, delay distributions, similarity engine, predictive failure probabilities, bounded guarantees, explainability reason items, pluggable provider protocol, safety invariants, evaluation metrics, calibration tracking, and REST APIs.
- **Phase 13 Adaptive Intelligence & Feedback (14 tests)**: Feedback recording, immutability, calibration thresholds, weight learning bounds, monotonic updates, adaptive prediction provider, model comparison, intervention effectiveness, safety invariants, and REST API endpoints.
- **Phase 14 Identity, Workspace & RBAC (7 tests)**: Password cryptography, session issuance, user registration & login, workspace CRUD & membership, role-based authorization gating, cross-tenant isolation, IDOR attack prevention, and dev fallback.
- **Phase 15 Enterprise Audit, Governance & Compliance (38 tests)**: AuditEvent model, SHA-256 hash chain genesis & chaining, verification (VALID/BROKEN_LINK/TAMPERED_PAYLOAD), sanitizer zero-secret policy, request context correlation, auth event auditing, workspace event auditing, obligation mutation auditing, graph edge auditing, intervention lifecycle auditing, reconciliation auditing, governance summary KPIs, CSV/JSON export, RBAC-gated access, entity-scoped history, and REST API endpoints.

```bash
cd frontend
npm run lint   # 0 errors, 0 warnings
npm run build  # All 15 static and dynamic routes compile cleanly (including /audit)
```

---

## 🔒 Phase 15: Enterprise Audit, Governance & Compliance

Obligation Agent maintains a **cryptographically tamper-evident audit trail** across every human and system action:

### Key Capabilities

| Capability | Implementation |
|-----------|---------------|
| **Immutable Audit Events** | `AuditEvent` ORM — append-only, never mutated |
| **SHA-256 Hash Chaining** | `hash = SHA256(prev_hash + ":" + canonical_json)` — any tamper breaks the chain |
| **Tamper Detection** | `/api/audit/verify` replays entire chain, returns `VALID`, `BROKEN_LINK`, or `TAMPERED_PAYLOAD` |
| **Zero-Secret Payloads** | `sanitize_for_audit()` scrubs passwords, tokens, API keys before persistence |
| **Request Correlation** | `RequestContextMiddleware` captures `X-Request-Id`, `X-Correlation-Id`, client IP, User-Agent |
| **RBAC-Gated Access** | `ADMIN`/`OWNER` see all events; `MEMBER`/`VIEWER` limited to entity-level history |
| **Governance KPI Dashboard** | `/api/audit/summary` — events/mutations today, top actors, security events, chain status |
| **Multi-Format Export** | `/api/audit/export?format=csv|json` — portable, sanitized, includes `event_hash` column |
| **Entity Provenance History** | `/api/audit/entity/{type}/{id}` — full lifecycle timeline for any obligation, intervention, etc. |
| **Security Anomaly Feed** | `/api/audit/security` — all `DENIED`, `FAILED`, `VIOLATION` events with filtering |

### Audited Actions (35+ event types)

```
USER_REGISTERED          LOGIN_FAILED             SESSION_CREATED
WORKSPACE_CREATED        WORKSPACE_MEMBER_INVITED  WORKSPACE_ROLE_CHANGED
OBLIGATION_CREATED       OBLIGATION_UPDATED        OBLIGATION_STATUS_CHANGED
GRAPH_EDGE_CREATED       GRAPH_EDGE_DELETED
PLAN_INTERVENTION        APPROVE_INTERVENTION      SCHEDULE_INTERVENTION
EXECUTE_INTERVENTION     RESOLVE_INTERVENTION
CONFIRM_EVIDENCE         REJECT_EVIDENCE
RESOLVE_RECONCILIATION   DISMISS_RECONCILIATION
INTEGRATION_CONNECTED    INTEGRATION_DISCONNECTED
PERMISSION_DENIED        API_ACCESS_BLOCKED
```

### Frontend: Governance Center (`/audit`)
- **KPI Cards**: Total Events, Security Anomalies, Governed Actions, Provenance Engine status
- **Live Chain Verification**: "Verify Hash Chain Now" with real-time cryptographic result
- **Filterable Audit Feed**: Action, Severity, Entity Type filters + Security Anomaly tab
- **Mutation Diff Inspector**: Before/after state modal with full cryptographic proof details
- **Top Actors & Entity Breakdown**: Who is mutating what, ranked by volume
- **One-click Export**: CSV and JSON buttons
