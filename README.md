# Obligation Agent

> **AI-Powered Reciprocal Commitment Intelligence & Execution Governance System**  
> *Where the Obligation — who owes what, to whom, by when, under what conditions, with evidence, dependency relationships, and provenance — is the atomic unit of work.*

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16.3-black.svg?logo=next.js&logoColor=white)](https://nextjs.org)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue.svg?logo=python&logoColor=white)](https://www.python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Google Gemini](https://img.shields.io/badge/LLM-Google%20Gemini%202.5%20Flash-4285F4.svg?logo=google&logoColor=white)](https://ai.google.dev/)
[![Strands](https://img.shields.io/badge/Agent%20Runtime-AWS%20Strands-FF9900.svg?logo=amazonaws&logoColor=white)](https://strandsagents.com)
[![Tests](https://img.shields.io/badge/Tests-610%20Passed-brightgreen.svg)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

---

## Table of Contents

- [What is Obligation Agent?](#what-is-obligation-agent)
- [Core Problem](#core-problem)
- [Solution](#solution)
- [Key Features](#key-features)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Supported Integrations](#supported-integrations)
- [AI / Gemini Intelligence Layer](#ai--gemini-intelligence-layer)
- [Security & Multi-Tenancy](#security--multi-tenancy)
- [Prerequisites](#prerequisites)
- [Local Setup](#local-setup)
- [Environment Configuration](#environment-configuration)
- [Database Setup](#database-setup)
- [Running the Backend](#running-the-backend)
- [Running the Worker](#running-the-worker)
- [Running the Frontend](#running-the-frontend)
- [Seeding Demo Data](#seeding-demo-data)
- [Demo Account & Default Credentials](#demo-account--default-credentials)
- [Using the Application](#using-the-application)
- [CSV Import & Export](#csv-import--export)
- [Integrations Setup Guide](#integrations-setup-guide)
- [API & Developer Reference](#api--developer-reference)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Production & Docker Deployment](#production--docker-deployment)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)
- [Current Limitations & Operational Notes](#current-limitations--operational-notes)
- [License](#license)

---

## What is Obligation Agent?

**Obligation Agent** continuously observes organizational work signals, discovers and tracks commitments, understands who owes what to whom and by when, connects dependencies and evidence, identifies risk and blockers, provides reasoning and recommendations, and keeps consequential actions strictly under human control.

Unlike conventional issue trackers or disconnected todo checklists, Obligation Agent models work as a **directed, reciprocal commitment graph**. It actively correlates unstructured workplace communication (Slack, Gmail, Google Calendar, Jira) with formal obligations, detects contradictions, calculates temporal and prerequisite risk cascades, drafts contextual intervention plans, and maintains an append-only, SHA-256 hash-chained cryptographic audit trail.

```
Observation (Slack, Gmail, Calendar, Jira)
      ↓
Untrusted Event Ingestion & Normalization
      ↓
Semantic AI Proposal & Grounding Validation (Gemini)
      ↓
Deterministic Domain Logic & Risk Graph Evaluation
      ↓
Human Review & Explicit Authorization (HITL)
      ↓
Controlled Dispatch & Execution Record
      ↓
Continuous Evidence Reconciliation & Verification
```

---

## Core Problem

Modern organizations suffer from **commitment fragmentation**:

1. **Directionless Task Checkboxes**: Traditional task lists track isolated actions without capturing **who owes the duty** versus **who is owed the benefit**, leading to ambiguous ownership and dropped handoffs.
2. **Hidden Cascading Blockers**: Upstream prerequisite delays silently cascade into critical-path deliverables without early warning.
3. **Noisy, Unverified Status Updates**: Verbal statements in Slack or email often contradict calendar reality, issue tracker statuses, or pull request mergers.
4. **Dangerous Autonomous AI**: Unconstrained AI agents that send unauthorized messages or execute destructive API calls introduce unacceptable operational and reputational risk.

---

## Solution

Obligation Agent resolves these challenges through a principled, safety-first architecture:

1. **The Obligation as the Atomic Unit**: Every record deterministically tracks owner (duty bearer), beneficiary (obligee), action, explicit/relative/conditional deadlines, structured conditions, confidence scores, and source provenance.
2. **Graph-Aware Dependency Tracking**: Recursive DAG traversal computes upstream prerequisites, critical-path delays, and automated cascade unblocking when upstream blockers complete.
3. **Cross-Provider Evidence Reconciliation**: Ingests signals from Slack, Gmail, Google Calendar, and Jira, synthesizing consistent clusters while flagging contradictions for operator triage before status changes.
4. **Strict Human-in-the-Loop (HITL) Boundary**: External events and LLM outputs are treated strictly as **untrusted observations and proposals**. Consequential mutations, messaging, and ticket transitions require explicit human approval.
5. **Cryptographic SHA-256 Hash-Chained Audit Trails**: Every state mutation, intervention, and configuration update is immutably recorded with SHA-256 hash linking for continuous compliance and tamper detection.

---

## Key Features

### Obligation Management & Lifecycle
* **Atomic Unit Modeling**: Captures Duty Bearer (`owner`), Obligee (`beneficiary`), specific `action`, nullable `deadline`, `conditions`, `priority` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), and directional category (`OWED_BY_ME` vs `OWED_TO_ME`).
* **Authoritative Finite State Machine**: Enforces strict transitions across `DETECTED` → `CONFIRMED` → `IN_PROGRESS` → `COMPLETED` / `BLOCKED` / `OVERDUE` / `CANCELLED`.
* **Directed Dependency Graphs**: Relational DAG engine supporting `DEPENDS_ON` and `LINKED` edge relationships with cycle prevention and depth limits.
* **Causal Blocker Reasoning**: Blocked obligations maintain structured causal tracking (`blocked_by: [{obligation_id, owner, action, status, reason}]`).

### Intelligence & AI Reasoning (Google Gemini)
* **Natural-Language Extraction**: Extracts structured obligation proposals from unstructured text, chats, and emails using Google Gemini 1.5 Flash.
* **Semantic Event Interpretation**: Categorizes external events into semantic roles: `COMPLETION_SIGNAL`, `COMMITMENT`, `REQUEST`, `PROGRESS_UPDATE`, `NON_COMPLETION_SIGNAL`, or `IRRELEVANT`.
* **Grounded Explanations**: Generates fact-grounded causal summaries derived exclusively from verified database records.
* **Data Minimization & Injection Defanging**: Automatically scrubs email headers, API keys, credentials, and sanitizes prompt injection vectors before LLM invocation.
* **Deterministic Fallback (Mock Provider)**: Zero-dependency offline mode for local development, CI testing, and deterministic scenario simulation.

### Event-Driven Architecture
* **Durable Event Inbox**: Multi-provider ingestion queue supporting stream ordering, SHA-256 deduplication, idempotency keys, and trace propagation.
* **Asynchronous Processing Engine**: DB-backed durable background worker with automatic crash recovery, lease timeouts, exponential backoff retries, and Dead-Letter Queue (DLQ).
* **Circuit Breakers & Resource Limits**: Provider-level failure isolation (5 failures threshold, 60s cooldown) and request body size enforcement.

### Evidence & Multi-Source Reconciliation
* **Cross-Provider Synthesis**: Synthesizes signals across Slack, Gmail, Google Calendar, and Jira to quantify consistency versus contradiction scores.
* **Temporal Provenance Timelines**: Full chronological audit trail linking originating messages, tickets, commits, and meetings to target obligations.
* **Human Adjudication Workflow**: Operator review tools to resolve ambiguous signals or accept conflicting evidence.

### Decision Center & Adaptive Interventions
* **Automated Risk Scoring**: Multi-signal scoring engine combining temporal proximity, blocker severity, dependency graph depth, and actor history.
* **Intervention Planning**: Generates fact-grounded intervention strategies (e.g., `EXPEDITE_PREREQUISITE`, `SCHEDULE_SYNC`, `STATUS_CHECK`, `DEADLINE_RENEGOTIATION`) with 24-hour deduplication cooldowns.
* **Controlled Execution**: Staged execution pipeline (`GENERATED` → `APPROVED` → `EXECUTED` → `VERIFIED`) with complete dispatch logs.

### Enterprise Governance & Observability
* **Multi-Tenant Workspace Scoping**: Complete database query filtering, member RBAC (`OWNER`, `ADMIN`, `MEMBER`, `OBSERVER`), and domain isolation.
* **Cryptographic Audit Explorer**: Real-time SHA-256 hash-chain verification tool detecting modified payloads, deleted records, or broken links.
* **Operations & SLO Dashboard**: Live error budget monitoring, endpoint latency tracking, and security threat posture metrics.

---

## How It Works

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             EXTERNAL OBSERVATIONS                                │
│   [ Slack Messages ]    [ Gmail Threads ]    [ Calendar Events ]    [ Jira Issues ]   │
└─────────────────────────────────────────┬────────────────────────────────────────┘
                                          │
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                   INGESTION, DEDUPLICATION & NORMALIZATION                       │
│    - HMAC-SHA256 & OAuth Verification   - Replay Window Tolerance (300s)         │
│    - ExternalEvent Inbox & Deduplication - Trace ID & Span Context Attribution     │
└─────────────────────────────────────────┬────────────────────────────────────────┘
                                          │
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                     INTELLIGENCE & RECONCILIATION ENGINE                         │
│    - Data Minimizer (PII / Credential Scrubbing & Prompt Injection Defanging)     │
│    - Google Gemini 1.5 Flash / Deterministic Mock Provider                       │
│    - Cross-Provider Reconciliation & Contradiction Detection                    │
│    - Risk Engine & Recursive Graph Blocker Propagation                           │
└─────────────────────────────────────────┬────────────────────────────────────────┘
                                          │
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        HUMAN AUTHORIZATION GATEWAY                               │
│    - Evidence Verification Queue        - Decision Center Plan Approval          │
│    - Intervention Draft Review          - Contradiction Adjudication             │
└─────────────────────────────────────────┬────────────────────────────────────────┘
                                          │
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                     CONTROLLED EXECUTION & GOVERNANCE                            │
│    - Dispatch Audit Logging             - Graph Cascade Unblocking Engine        │
│    - Append-Only SHA-256 Hash Chain     - Real-Time Operations Telemetry         │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture

```mermaid
flowchart TD
    subgraph Ingestion["1. Ingestion Layer"]
        Slack[Slack Webhook]
        Gmail[Gmail Webhook / Sync]
        Cal[Google Calendar Sync]
        Jira[Jira Cloud Sync / Webhook]
        CSV[CSV Bulk Import]
    end

    subgraph CoreEngine["2. Core Processing & Workers"]
        Inbox[Event Ingestion Service]
        DurableQ[Durable DB Job Queue]
        Worker[Background Worker Loop]
        Norm[ExternalEvent Normalizer]
    end

    subgraph Intelligence["3. Intelligence & Graph Layer"]
        Minimizer[Data Minimizer & Defense]
        LLM[Google Gemini 1.5 Flash / Mock]
        Graph[DAG Dependency Engine]
        Risk[Multi-Signal Risk Engine]
        Recon[Reconciliation Engine]
    end

    subgraph Governance["4. State & Execution Governance"]
        SM[Status Machine FSM]
        HITL[Human Authorization Gate]
        Intervention[Intervention Dispatcher]
        Audit[SHA-256 Hash-Chained Audit]
    end

    Ingestion --> Inbox
    CSV --> DurableQ
    Inbox --> DurableQ
    DurableQ --> Worker
    Worker --> Norm
    Norm --> Minimizer
    Minimizer --> LLM
    LLM --> Recon
    Recon --> Graph
    Graph --> Risk
    Risk --> HITL
    HITL --> SM
    HITL --> Intervention
    SM --> Audit
    Intervention --> Audit
```

---

## Supported Integrations

| Integration | Purpose | Authentication | Ingestion Mode | Outbound Actions | Configuration Required |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Google Gemini** | NLP extraction, semantic reasoning, event role classification, grounded explanations | API Key (`GEMINI_API_KEY`) | Internal Service | None (Proposal only) | `LLM_PROVIDER=gemini`, `GEMINI_API_KEY` |
| **Jira Cloud** | Bidirectional sync of issues, subtasks, blockers, assignees, due dates, and comments | Atlassian API Token or OAuth 2.0 (3LO) | Inbound Webhooks + Scheduled / Manual Sync | Project sync, comment ingestion | `JIRA_SITE_URL`, `JIRA_USER_EMAIL`, `JIRA_API_TOKEN`, `JIRA_WEBHOOK_SECRET` |
| **Slack** | Ingest channel messages, threads, and mentions as progress or blocker evidence | Inbound HMAC-SHA256 Webhook + Bot Token | Inbound Webhook (`/api/webhooks/slack`) | Draft message proposals (operator approved) | `SLACK_SIGNING_SECRET`, `SLACK_BOT_TOKEN` |
| **Gmail** | Ingest email commitments, client responses, and audit notifications | Google OAuth 2.0 + PubSub Push | Inbound Webhook (`/api/webhooks/gmail`) | Draft email responses (operator approved) | `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_PUBSUB_TOPIC` |
| **Google Calendar**| Ingest meeting schedules, architecture syncs, and deadline milestones | Google OAuth 2.0 + Webhooks | Inbound Webhook (`/api/webhooks/google-calendar`) | None (Read-only observation) | `GOOGLE_CALENDAR_CLIENT_ID`, `GOOGLE_CALENDAR_CLIENT_SECRET` |
| **Mock Provider** | Deterministic local simulation of all providers without external network access | Built-in | Simulated via UI / API | Simulated payloads | `LLM_PROVIDER=mock` |

---

## AI / Gemini Intelligence Layer

Obligation Agent utilizes **Google Gemini** as its primary LLM intelligence engine via the official `google-genai` SDK.

### Provider Modes

1. **Gemini Live Mode (`LLM_PROVIDER=gemini`)**:
   - Uses `gemini-2.5-flash` for high-throughput, low-latency extraction and reasoning.
   - Requires `GEMINI_API_KEY`.
   - Structured JSON output schemas enforced with automatic validation against Pydantic models.

2. **Mock Mode (`LLM_PROVIDER=mock`)**:
   - Deterministic, offline provider utilizing rule-based semantic parsers and pre-calculated scenario mocks.
   - Default for local development, unit tests, and CI/CD pipelines. Zero API keys or network calls required.

3. **Strands Agent Runtime (`LLM_PROVIDER=strands`)**:
   - Uses the Strands agent SDK over Gemini for tool-using agentic workflows (investigation and recommendation).
   - Requires `GEMINI_API_KEY` and `strands-agents` (already in `requirements.txt`). No AWS account or credentials are needed -- Strands is an open-source SDK here, not an AWS service.
   - Gemini remains the model; Strands provides agent orchestration, tool calling and structured output.
   - See `docs/operations/strands_runtime.md` for the full runtime operator guide.

### Gemini Configuration Example

```env
# Enable Gemini LLM Layer
LLM_ENABLED=true
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
GEMINI_API_KEY=AIzaSyYourActualGeminiApiKeyHere

# Rate Limiting & Safety Boundaries
LLM_MAX_REQUESTS_PER_MINUTE=60
LLM_MAX_TOKENS_PER_REQUEST=2048
LLM_TIMEOUT_SECONDS=5.0
LLM_FALLBACK_TO_DETERMINISTIC=true
```

# Strands Agent Runtime (when LLM_PROVIDER=strands)
```env
STRANDS_MAX_TOOL_CALLS=6
STRANDS_TIMEOUT_SECONDS=60.0
```

### Verifying LLM Runtime Status

Check live LLM engine status via the API:

```bash
curl http://localhost:8000/api/intelligence/llm/status
```

When `LLM_PROVIDER=strands` is active, the response reports `"provider_name": "strands"` (with `"registered_providers": ["mock", "gemini", "strands"]`). See `docs/operations/strands_runtime.md` for the full response shape and the `api_key_configured` signal to watch during cutover.

Expected response:
```json
{
  "provider": "gemini",
  "model": "gemini-2.5-flash",
  "is_ready": true,
  "rate_limiter": {
    "requests_this_minute": 1,
    "limit_per_minute": 60,
    "daily_requests": 14,
    "daily_limit": 5000
  },
  "validation_status": "OPERATIONAL"
}
```

---

## Security & Multi-Tenancy

* **Strict Multi-Tenant Isolation**: Every database query, event record, and cache entry is strictly scoped by `workspace_id`. Cross-workspace data leakage is blocked at the ORM and route dependency layers.
* **Role-Based Access Control (RBAC)**: Supports `OWNER`, `ADMIN`, `MEMBER`, and `OBSERVER` roles. Sensitive actions (workspace deletion, member removal, integration credential modification) require elevated privileges.
* **Credential Encryption at Rest**: Sensitive integration tokens and webhook secrets are encrypted at rest using AES-256 symmetric encryption (`Fernet`).
* **Webhook Replay Protection**: Inbound webhooks enforce strict HMAC-SHA256 signature verification with a 300-second timestamp tolerance window.
* **LLM Trust Boundary & Defense**: User-supplied text passes through `DataMinimizer`, which strips authorization headers, access keys, email addresses, and defangs prompt injection delimiters before LLM submission.
* **Formula Injection Sanitization**: All CSV import fields starting with spreadsheet formula execution symbols (`=`, `+`, `-`, `@`, `\t`, `\r`) are automatically escaped with single quotes.
* **Tamper-Evident SHA-256 Audit Chain**: Every state transition and admin event is cryptographically linked to the previous event's hash (`previous_hash` → `record_hash`).

---

## Prerequisites

| Requirement | Supported Version | Notes |
| :--- | :--- | :--- |
| **Python** | `3.11` or `3.12` | Required for backend, worker, and operational CLI tools |
| **Node.js** | `18.18+` or `20+` | Required for Next.js 16 frontend |
| **npm** / **pnpm** | `npm 9+` or `pnpm 8+` | Package manager for frontend dependencies |
| **SQLite** | `3.35+` (Built-in) | Default zero-configuration database for development and testing |
| **PostgreSQL** | `15` or `16` (Optional) | Recommended for production deployment (via `asyncpg`) |
| **Docker & Compose** | `24+` / `v2.20+` (Optional) | For containerized multi-service deployment |

---

## Local Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-org/obligation-agent.git
cd obligation_agent
```

### Step 2: Backend Setup

```bash
# Navigate to backend
cd backend

# Create and activate virtual environment
python -m venv venv

# On Windows:
.\venv\Scripts\activate
# On macOS / Linux:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure local environment
cp .env.example .env
```

### Step 3: Frontend Setup

```bash
# Navigate to frontend (in a separate terminal)
cd frontend

# Install Node dependencies
npm install

# Configure frontend environment (optional - defaults to http://localhost:8000)
# echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
```

---

## Environment Configuration

Configuration is managed via environment variables and loaded through `pydantic-settings`.

### Environment Variables Reference Table

| Variable | Required | Default / Example | Purpose |
| :--- | :--- | :--- | :--- |
| **Core & Database** | | | |
| `APP_ENV` | Optional | `development` | Application environment (`development`, `staging`, `production`) |
| `AUTH_MODE` | Optional | `mock` | Authentication mode (`mock` for local dev bypass, `production` for strict JWT) |
| `DEBUG` | Optional | `true` | Enables detailed debug logging |
| `DATABASE_URL` | **Required** | `sqlite+aiosqlite:///./obligations.db` | SQLAlchemy async database connection URI |
| `FRONTEND_URL` | Optional | `http://localhost:3000` | Allowed CORS origin(s), comma-separated for multiple |
| **Authentication & Security** | | | |
| `JWT_SECRET_KEY` | **Required** | `dev-jwt-secret-key-change-in-production-1234567890` | Secret key for signing JWT tokens (min 32 chars in prod) |
| `JWT_ALGORITHM` | Optional | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| Optional | `1440` (24h) | Token expiration duration in minutes |
| `ENCRYPTION_KEY` | Optional | *(Auto-derived in dev)* | 32-byte url-safe base64 Fernet encryption key for secrets at rest |
| **Google Gemini AI** | | | |
| `LLM_ENABLED` | Optional | `true` | Enables the natural-language intelligence layer |
| `LLM_PROVIDER` | Optional | `mock` | Active provider: `mock` (offline/test) or `gemini` (live Google Gemini) |
| `LLM_MODEL` | Optional | `gemini-2.5-flash` | Target Gemini model identifier |
| `GEMINI_API_KEY` | Required if Gemini | `AIzaSy...` | Google AI Studio API key |
| `LLM_MAX_REQUESTS_PER_MINUTE`| Optional | `60` | Client rate limit for Gemini API calls |
| `LLM_TIMEOUT_SECONDS` | Optional | `5.0` | Timeout threshold for LLM requests |
| `LLM_FALLBACK_TO_DETERMINISTIC` | Optional | `true` | Fallback to rule-based analysis if Gemini times out |
| **Jira Cloud Integration** | | | |
| `JIRA_ENABLED` | Optional | `true` | Enables Jira Cloud provider adapter |
| `JIRA_SITE_URL` | Optional | `https://acme.atlassian.net` | Jira Cloud instance URL |
| `JIRA_USER_EMAIL` | Optional | `operator@acme.com` | Atlassian account email for API token auth |
| `JIRA_API_TOKEN` | Optional | `ATATT3xFfGF0...` | Atlassian API token |
| `JIRA_WEBHOOK_SECRET` | Optional | `jira-webhook-secret-token` | Secret for Jira webhook HMAC validation |
| **Slack Integration** | | | |
| `SLACK_ENABLED` | Optional | `false` | Enables Slack webhook and bot adapter |
| `SLACK_SIGNING_SECRET` | Optional | `slack-signing-secret` | Slack request signature verification secret |
| `SLACK_BOT_TOKEN` | Optional | `xoxb-...` | Slack Bot User OAuth Token |
| **Gmail & Google Calendar** | | | |
| `GMAIL_ENABLED` | Optional | `false` | Enables Gmail integration |
| `GMAIL_CLIENT_ID` | Optional | `google-client-id.apps.googleusercontent.com` | Google Cloud OAuth Client ID |
| `GMAIL_CLIENT_SECRET` | Optional | `google-client-secret` | Google Cloud OAuth Client Secret |
| `GOOGLE_CALENDAR_ENABLED` | Optional | `false` | Enables Google Calendar integration |
| `GOOGLE_CALENDAR_CLIENT_ID` | Optional | `google-client-id.apps.googleusercontent.com` | Google Cloud OAuth Client ID |
| `GOOGLE_CALENDAR_CLIENT_SECRET` | Optional | `google-client-secret` | Google Cloud OAuth Client Secret |
| **Background Worker & Limits** | | | |
| `WORKER_ENABLED` | Optional | `true` | Runs background queue worker |
| `WORKER_CONCURRENCY` | Optional | `4` | Worker concurrency threads / tasks |
| `WORKER_DURABLE_QUEUE` | Optional | `true` | Enables database-backed durable job queue |
| `WORKER_LEASE_TIMEOUT_SECONDS` | Optional | `300` | Stale job recovery threshold |
| **Demo & Seed** | | | |
| `DEMO_USER_EMAIL` | Optional | `demo@obligation.local` | Primary seeded demo user email |
| `DEMO_USER_PASSWORD` | Optional | `demo1234` | Seeded demo user password |
| `DEMO_WORKSPACE_NAME` | Optional | `Demo Workspace` | Seeded workspace display name |
| `DEMO_WORKSPACE_ID` | Optional | `ws-default` | Seeded workspace identifier |

---

## Database Setup

Obligation Agent supports **SQLite** for development and **PostgreSQL** for production.

### Development (SQLite)
By default, the backend uses `sqlite+aiosqlite:///./obligations.db`. Database tables and schema constraints are verified automatically on application startup in development mode (`APP_ENV=development`).

### Production (PostgreSQL & Alembic)
For production deployment, set `DATABASE_URL` to a PostgreSQL async connection:
```env
DATABASE_URL=postgresql+asyncpg://obligation_user:your_password@localhost:5432/obligations_prod
```

Run database migrations via Alembic:
```bash
cd backend
alembic upgrade head
```

---

## Running the Backend

From the `backend/` directory:

```bash
# Using uvicorn (FastAPI entrypoint with auto-reload)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The backend starts at `http://localhost:8000`.
* Interactive OpenAPI Documentation: `http://localhost:8000/docs`
* ReDoc Alternative Docs: `http://localhost:8000/redoc`
* System Health Endpoint: `http://localhost:8000/api/health`

---

## Running the Worker

The background worker is embedded directly into the FastAPI application lifespan by default (`WORKER_ENABLED=true`). It automatically initializes concurrency workers and executes recovery for any unacknowledged jobs from previous crashes.

For standalone worker deployment in containerized environments:
```bash
cd backend
python -m app.core.worker
```

---

## Running the Frontend

From the `frontend/` directory:

```bash
# Start Next.js development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Seeding Demo Data

The repository includes a comprehensive, idempotent demo seeding engine that provisions realistic organizational commitments, dependency graphs, multi-provider evidence signals, and hash-chained operational audit records.

Execute the seed script from the `backend/` directory:

```bash
# Recommended command:
python -m app.ops.seed_demo

# Alternatively (via root wrapper):
python seed.py
```

### What the Seed Creates:
* **Demo Workspace**: `Demo Workspace` (`ws-default`) with isolated tenant scoping.
* **User Accounts**:
  - `demo@obligation.local` (Workspace Owner)
  - `priya@company.com` (Engineering Lead / Member)
* **5 Domain Obligations**:
  1. `Deliver v2 REST API Technical Specifications` (Status: `IN_PROGRESS`, Healthy)
  2. `Submit SOC2 Type II Access Audit Package` (Status: `IN_PROGRESS`, Approaching Deadline)
  3. `Provide Staging Database Benchmark Results` (Status: `OVERDUE`, Prerequisite Blocker owned by Priya)
  4. `Finalize Infrastructure Migration Plan` (Status: `BLOCKED` by upstream benchmark)
  5. `Execute Zero-Downtime Production Cutover` (Status: `CONFIRMED`, Downstream dependent)
* **2 Directed Graph Edges**: Full DAG dependency chain linking Migration Plan → Benchmark → Production Cutover.
* **4 Ingested Multi-Provider Events**:
  - Slack blocker update from Priya regarding database timeouts.
  - GitHub OpenAPI schema specification PR merge.
  - Google Calendar Architecture Review meeting.
  - Gmail SOC2 compliance audit package submission notice.
* **Reconciled Cross-Provider Evidence**: Evaluated contradiction record for the blocked migration deliverable.
* **Active Decision Center Plan**: Strategy to unblock database benchmarks with human approval checkpoints.
* **Cryptographic SHA-256 Hash Chain**: 4 initialized, unbroken operational audit records.

---

## Demo Account & Default Credentials

When `AUTH_MODE=mock` (default development mode), authentication is bypassed and the application automatically authenticates as the primary operator.

For explicit login testing or when `AUTH_MODE=production`:

| Attribute | Value |
| :--- | :--- |
| **Email** | `demo@obligation.local` *(configurable via `DEMO_USER_EMAIL`)* |
| **Password** | `demo1234` *(configurable via `DEMO_USER_PASSWORD`)* |
| **Workspace ID** | `ws-default` |
| **Role** | Workspace Owner |

---

## Using the Application

Navigate through the navigation bar:

1. **Obligations Dashboard (`/`)**: Overview of high-risk commitments, active graph cascades, pending approvals, and upcoming deadlines.
2. **Obligations Hub (`/obligations`)**: Filterable, searchable repository of all commitments categorized by `OWED_BY_ME` and `OWED_TO_ME` with dependency graph views.
3. **Capture & Natural Language AI (`/capture`)**: Extract structured obligations from natural language text, Slack threads, or email snippets using Gemini.
4. **Activity Center (`/events`)**: Unified chronological timeline of all incoming events across Slack, Gmail, Google Calendar, and Jira with semantic role badges.
5. **Reconciliation & Contradictions (`/reconciliation`)**: Cross-source evidence intelligence identifying corroborating progress signals and flagging contradictions.
6. **Decision Center & Interventions (`/intelligence/decisions`)**: Human review and authorization gateway for AI-recommended strategies and drafts.
7. **Integration Management (`/integrations`)**: Connection cards and status diagnostics for Google Gemini, Jira Cloud, Slack, Gmail, and Google Calendar.
8. **Operation Audit Explorer (`/operations/audit`)**: Cryptographic audit viewer with real-time SHA-256 hash-chain verification and severity filters.
9. **Operations Telemetry Hub (`/operations`)**: Live system dashboard monitoring error budgets, provider circuit breakers, and trace graphs.

---

## CSV Import & Export

Obligation Agent supports bulk ingestion of commitments with automated duplicate detection, dependency relationship resolution, and formula-injection defenses.

### Downloading the Standard Template
Obtain the official CSV template from the running backend:
```bash
curl http://localhost:8000/api/obligations/import/csv/template -o obligations_template.csv
```

### Supported CSV Schema

| Column | Required | Allowed Values / Format | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `action` | **Yes** | String (1-500 chars) | The specific deliverable or promised action | `Deliver Q3 Financial Audit Report` |
| `owner` | **Yes** | Email or identifier | Duty bearer responsible for completion | `alice@company.com` |
| `beneficiary` | **Yes** | Email, team, or name | Obligee to whom the duty is owed | `sarah@company.com` |
| `deadline` | No | `YYYY-MM-DD` or ISO 8601 | Commitment deadline timestamp | `2026-09-30` |
| `priority` | No | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` | Priority level (defaults to `MEDIUM`) | `HIGH` |
| `obligation_type` | No | `OWED_BY_ME`, `OWED_TO_ME` | Directional category (defaults to `OWED_BY_ME`)| `OWED_BY_ME` |
| `description` | No | String | Contextual notes and conditions | `Complete sign-off on Q3 revenue` |
| `dependencies` | No | Semicolon or comma-separated actions | Action names of prerequisite obligations | `Deploy Database Migration` |

### Importing CSV via API

```bash
# 1. Preview and validate rows
curl -X POST http://localhost:8000/api/obligations/import/csv/preview \
  -H "X-Workspace-Id: ws-default" \
  -F "file=@obligations.csv"

# 2. Commit validated rows atomically
curl -X POST http://localhost:8000/api/obligations/import/csv/commit \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: ws-default" \
  -d '{"rows": [...validated_rows...], "skip_duplicates": true}'
```

---

## Integrations Setup Guide

### 1. Jira Cloud Setup
1. Log in to [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens) and generate an API Token.
2. In the Obligation Agent UI, navigate to **Integrations** → **Connect Jira**.
3. Enter your **Jira Site URL** (e.g., `https://your-domain.atlassian.net`), **Account Email**, and **API Token**.
4. Select target Jira projects to sync (e.g., `ENG`, `INFRA`).
5. To configure inbound webhooks from Jira:
   - In Jira Project Settings → Webhooks, create a webhook pointing to `http://<your-host>:8000/api/webhooks/jira`.
   - Select issue events: `Issue Created`, `Issue Updated`, `Issue Deleted`, `Comment Created`.

### 2. Slack Setup
1. Create a Slack App in your workspace at [api.slack.com/apps](https://api.slack.com/apps).
2. Under **Event Subscriptions**, enable events and set the Request URL to:
   `https://<your-domain>/api/webhooks/slack`
3. Subscribe to bot events: `message.channels`, `app_mention`.
4. Copy the **Signing Secret** and **Bot User OAuth Token** into your `.env`:
   ```env
   SLACK_ENABLED=true
   SLACK_SIGNING_SECRET=your_signing_secret_here
   SLACK_BOT_TOKEN=xoxb-your-bot-token-here
   ```

### 3. Google Gemini Setup
1. Obtain an API key from [Google AI Studio](https://aistudio.google.com/).
2. Add the key to your `.env` file:
   ```env
   LLM_ENABLED=true
   LLM_PROVIDER=gemini
   LLM_MODEL=gemini-2.5-flash
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

---

## API & Developer Reference

The backend provides a fully documented REST API. Access interactive documentation at `http://localhost:8000/docs`.

### Primary Endpoint Overview

| Path | Method | Purpose |
| :--- | :--- | :--- |
| `/api/health` | `GET` | System health check and component status |
| `/api/ready` | `GET` | Production readiness check for load balancers |
| `/api/metrics` | `GET` | Prometheus-compatible operational performance metrics |
| `/api/obligations` | `GET`, `POST` | List obligations with filters / Create obligation |
| `/api/obligations/{id}` | `GET`, `PATCH`, `DELETE`| Retrieve, update, or cancel specific obligation |
| `/api/obligations/{id}/graph` | `GET` | Dependency DAG subgraph for obligation |
| `/api/events` | `GET` | Ingested Activity Center event timeline |
| `/api/events/simulate` | `POST` | Deterministic event scenario simulator |
| `/api/reconciliation` | `GET` | List multi-provider reconciliation records |
| `/api/reconciliation/refresh` | `POST` | Re-evaluate cross-provider contradictions for workspace |
| `/api/intelligence/llm/status` | `GET` | Live Gemini / Strands provider runtime health |
| `/api/intelligence/llm/investigate` | `POST` | Agentic investigation: the agent calls read-only tools to gather the obligation's state, dependency chain, evidence and risk, then returns a grounded structured summary |
| `/api/intelligence/llm/recommend` | `POST` | Agentic recommendation against the existing DecisionPlan. Advisory only — acting on it requires human authorization |
| `/api/intelligence/decisions/generate`| `POST` | Generate fact-grounded decision plans |
| `/api/integrations` | `GET` | Status of all registered integration adapters |
| `/api/integrations/jira/projects` | `GET`, `POST` | Discover and select Jira Cloud projects |
| `/api/integrations/jira/sync` | `POST` | Trigger synchronous Jira issue pull |
| `/api/ops/audit` | `GET` | Query workspace-scoped operational audit records |
| `/api/ops/audit/integrity` | `GET` | Cryptographically verify SHA-256 hash chain |
| `/api/ops/dashboard` | `GET` | Live operations telemetry and SLO error budget stats |

---

## Testing & Quality Assurance

Obligation Agent maintains an extensive automated test suite covering unit logic, integration adapters, security boundaries, and multi-tenant isolation.

### Running the Test Suite

From the `backend/` directory:

```bash
# Run all automated tests (566 tests)
pytest tests/ -v

# Run with coverage report
pytest --cov=app tests/

# Run specific test suites
pytest tests/test_operational_audit_explorer.py -v
pytest tests/test_llm_activation.py -v
pytest tests/test_jira_integration.py -v
pytest tests/test_tenant_isolation_matrix.py -v
```

### Running Operational Diagnostics & Audits

```bash
# 1. Cryptographic SHA-256 Audit Chain Verification
python -m app.ops.audit_integrity

# 2. Automated Security & Governance Check
python -m app.ops.security_audit

# 3. Production Readiness Preflight Check
python -m app.ops.production_readiness
```

### Frontend Build & Lint Verification

From the `frontend/` directory:

```bash
# Lint code
npm run lint

# Production bundle build test
npm run build
```

---

## Production & Docker Deployment

### Multi-Service Docker Compose

The repository includes a production-ready `docker-compose.yml` deploying PostgreSQL 16, FastAPI Backend, Durable Worker, and Next.js Frontend.

```bash
# 1. Configure production environment
cp .env.production.example .env.production

# 2. Build and launch containers
docker compose up -d --build

# 3. View container status
docker compose ps

# 4. Inspect logs
docker compose logs -f backend
```

---

## Troubleshooting

### 1. Backend Cannot Connect to Database
* **SQLite (Development)**: Verify that write permissions exist for the root and `backend/` directory. Ensure `DATABASE_URL=sqlite+aiosqlite:///./obligations.db`.
* **PostgreSQL (Production)**: Ensure PostgreSQL is running (`pg_isready`) and the user has `CREATE TABLE` privileges. Confirm connection URI format: `postgresql+asyncpg://user:pass@host:5432/dbname`.

### 2. Frontend Cannot Reach Backend
* Verify the backend is running on `http://localhost:8000` (`curl http://localhost:8000/api/health`).
* In `frontend/.env.local` or environment, ensure `NEXT_PUBLIC_API_URL=http://localhost:8000`.
* Check CORS configuration in backend `.env` (`FRONTEND_URL=http://localhost:3000`).

### 3. Gemini LLM Not Activating
* Verify `LLM_PROVIDER=gemini` is set in `backend/.env`.
* Confirm `GEMINI_API_KEY` is a valid Google AI Studio key without surrounding quotes or whitespace.
* Check runtime status: `curl http://localhost:8000/api/intelligence/llm/status`.
* If no external internet access is available, set `LLM_PROVIDER=mock` for local development.
* Note: `LLM_PROVIDER=strands` also requires `GEMINI_API_KEY` (Strands runs over Gemini). Without it, Strands degrades silently to the mock provider. See `docs/operations/strands_runtime.md`.

### 4. Jira Connection Failure
* Confirm you are using **Jira Cloud** (e.g., `https://your-domain.atlassian.net`). Jira Server / Data Center is not supported.
* Ensure the email matches your Atlassian account exactly and the API Token was generated from [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
* Test connectivity: Navigate to **Integrations** → Jira Card → click **Test**.

### 5. Operation Audit Explorer Shows No Data
* Run the seed script: `python -m app.ops.seed_demo` to populate baseline records.
* In the UI, confirm you are in the default workspace (`Demo Workspace` / `ws-default`).
* Click **Verify Cryptographic Integrity** on `/operations/audit` to re-index and validate hashes.

---

## Project Structure

```text
obligation_agent/
├── backend/                        # FastAPI Backend Application
│   ├── alembic/                    # Alembic Database Migrations
│   ├── app/
│   │   ├── api/                    # REST API Route Handlers
│   │   │   └── routes/             # Feature-specific router modules
│   │   ├── core/                   # Core Infrastructure & Cross-Cutting Concerns
│   │   │   ├── config.py           # Pydantic Settings & Environment Validation
│   │   │   ├── database.py         # SQLAlchemy Async Engine & Session Factory
│   │   │   ├── durable_worker.py   # DB-backed background job queue
│   │   │   ├── errors.py           # Structured Error Handlers & ErrorCodes
│   │   │   ├── security.py         # Passwords, JWT, and Fernet Encryption
│   │   │   └── status_machine.py   # Authoritative Obligation FSM
│   │   ├── models/                 # SQLAlchemy ORM Data Models
│   │   │   ├── auth.py             # User, Workspace, WorkspaceMembership
│   │   │   ├── obligation.py       # Obligation, ObligationEdge, Evidence
│   │   │   ├── decision.py         # DecisionPlan, DecisionAction
│   │   │   ├── integration.py      # IntegrationConnection
│   │   │   └── operational_audit.py# OperationalAuditRecord (SHA-256 Chained)
│   │   ├── ops/                    # Production & Developer Tooling Scripts
│   │   │   ├── seed_demo.py        # Canonical Demo Environment Seeder
│   │   │   ├── audit_integrity.py  # SHA-256 Hash Chain Integrity Verifier
│   │   │   ├── security_audit.py   # Automated Security Compliance Check
│   │   │   └── production_readiness.py # Deployment Preflight Diagnostics
│   │   ├── schemas/                # Pydantic Request/Response DTOs
│   │   └── services/               # Business Logic & Integration Engines
│   │       ├── llm/                # Google Gemini & Mock LLM Providers
│   │       ├── providers/          # Jira, Slack, Gmail, Calendar Adapters
│   │       ├── graph_service.py    # Directed Acyclic Graph Dependency Engine
│   │       ├── risk_engine.py      # Multi-Signal Risk Scoring Engine
│   │       └── reconciliation_service.py # Cross-Provider Evidence Reconciliation
│   ├── tests/                      # Automated Test Suite (566+ pytest cases)
│   ├── Dockerfile                  # Production Backend Container
│   ├── requirements.txt            # Python Dependencies
│   └── seed.py                     # Root Seed Entrypoint Wrapper
├── frontend/                       # Next.js 16 Web Application
│   ├── src/
│   │   ├── app/                    # Next.js App Router (28 Pages & Routes)
│   │   │   ├── (auth)/             # Login, Register, Onboarding
│   │   │   ├── obligations/        # Obligations Hub & Detail Views
│   │   │   ├── events/             # Activity Center Timeline
│   │   │   ├── reconciliation/     # Evidence Contradiction Intelligence
│   │   │   ├── intelligence/       # Decision Center & Monitoring Hub
│   │   │   ├── integrations/       # Provider Connection Management
│   │   │   └── operations/         # Audit Explorer & Telemetry
│   │   ├── components/             # Reusable UI Components & Modals
│   │   ├── lib/
│   │   │   ├── api/                # Typed API Clients (obligations.ts, opsApi)
│   │   │   └── types/              # TypeScript Domain Interfaces
│   │   └── styles/                 # Tailwind CSS & Design System Tokens
│   ├── package.json                # Frontend Dependencies & Scripts
│   └── Dockerfile                  # Production Frontend Container
├── docs/                           # Architectural Specifications & RFCs
├── docker-compose.yml              # Multi-Service Production Compose File
├── .env.example                    # Example Environment Configuration
├── .env.production.example         # Example Production Environment Variables
└── README.md                       # Comprehensive Documentation
```

---

## Current Limitations & Operational Notes

* **Jira Cloud Scope**: The Jira integration is built specifically for **Jira Cloud** REST APIs and Webhooks. Jira Server / Data Center on-premise instances are not supported.
* **Live AI Requires Gemini Key**: To perform real-time semantic extraction and explanation, a valid `GEMINI_API_KEY` is required. If absent, the system operates in deterministic `mock` mode.
* **Human-in-the-Loop Constraint**: Obligation Agent is architected with intentional human boundaries. The system will **never** automatically send outbound emails, post unverified Slack messages, or close tickets without explicit operator confirmation.

---

## License

Obligation Agent is open-source software licensed under the [Apache License, Version 2.0](LICENSE).
