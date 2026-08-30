# Obligation Agent

> **AI-Powered Reciprocal Obligation & Commitment Intelligence System**  
> *Where the Obligation — who owes what, to whom, by when, under what conditions, with evidence and source reference — is the atomic unit.*

---

## 🌟 Executive Summary & Core Philosophy

Conventional productivity tools operate on isolated, directionless "todo lists" and task checkboxes. **obligation agent** reconceptualizes commitments around **the Obligation as the atomic unit of work and relationship**.

### 1. The Obligation is the Atomic Unit
A task is merely an obligation rendered from the perspective of the duty bearer. Every obligation contains:
- **Owner (Duty Bearer)**: Who owes the deliverable
- **Beneficiary (Obligee)**: To whom the deliverable is owed
- **Action**: What specific duty or promise is owed
- **Deadline**: Nullable ISO timestamp (supports unconditional & conditional deadlines)
- **Conditions**: Structured triggers (e.g., *"Once pricing numbers are confirmed"*)
- **Evidence**: Audit logs, commit URLs, signed notes, or artifacts confirming completion
- **Status**: Controlled finite state machine (`DETECTED`, `CONFIRMED`, `IN_PROGRESS`, `COMPLETED`, `OVERDUE`, `CANCELLED`, `BLOCKED`)
- **Next Action**: Immediate tactical follow-up step
- **Source Reference**: Originating channel/message provenance
- **Obligation Type**: Directional categorization (`OWED_BY_ME` vs. `OWED_TO_ME`)
- **Confidence**: Field-level AI extraction certainty breakdown

### 2. Obligations are Bidirectional & Linkable
Real work is reciprocal:
- **A owes B** a report $\iff$ **B owes A** the raw database numbers first.
- The data model explicitly supports separate, linkable records via `obligation_edges` (`DEPENDS_ON`, `LINKED`), preparing the engine for dependency graph propagation.

### 3. Human-in-the-Loop is Mandatory
AI extractions are **candidates requiring human verification**. The pipeline enforces:
$$\text{Raw Communication Text} \longrightarrow \text{AI Extraction} \longrightarrow \text{Candidate Review \& Edit} \longrightarrow \text{Human Confirmation} \longrightarrow \text{Persistence}$$

---

## 🏛️ System Architecture

```
obligation_agent/
├── backend/                        # FastAPI Async Python Engine
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py             # Dependency injection & service resolution
│   │   │   └── routes/
│   │   │       ├── dashboard.py    # /api/dashboard summary & aggregations
│   │   │       ├── health.py       # /api/health
│   │   │       └── obligations.py  # /api/obligations CRUD, extract, status, edges
│   │   ├── core/
│   │   │   ├── config.py           # Pydantic Settings & environment handling
│   │   │   ├── database.py         # SQLAlchemy async engine (PostgreSQL / SQLite fallback)
│   │   │   ├── logging.py          # Structured logger
│   │   │   └── status_machine.py   # Controlled finite state machine & validation
│   │   ├── models/
│   │   │   └── obligation.py       # Obligation & ObligationEdge ORM entities
│   │   ├── schemas/
│   │   │   └── obligation.py       # Pydantic V2 Request / Response models
│   │   ├── services/
│   │   │   ├── extraction_service.py # Provider adapter pattern (DevMock & LLM adapters)
│   │   │   └── obligation_service.py # Domain CRUD, state transitions & risk calculations
│   │   └── main.py                 # FastAPI application, CORS & Lifespan
│   ├── alembic/                    # Database migrations
│   ├── tests/                      # Pytest async test suite
│   ├── seed.py                     # Canonical scenario database seeder
│   ├── requirements.txt            # Python dependencies
│   └── .env.example
│
└── frontend/                       # Modern Next.js SaaS Web Application
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx          # Root shell layout with theme
    │   │   ├── page.tsx            # Main Dashboard (You Owe / Others Owe / At Risk)
    │   │   ├── capture/page.tsx    # AI Message Extraction & Review Interface
    │   │   └── obligations/
    │   │       ├── page.tsx        # Complete Obligation Ledger & Filters
    │   │       └── [id]/page.tsx   # Detailed Obligation & State Machine Controller
    │   ├── components/
    │   │   ├── layout/             # Sidebar, Header, AppLayout
    │   │   ├── obligations/        # ObligationCard, ReviewCard
    │   │   └── ui/                 # StatusBadge, ConfidenceBadge, ToastContext
    │   └── lib/
    │       ├── api/                # Typed API client (client.ts, obligations.ts)
    │       └── types/              # TypeScript domain definitions
    ├── package.json
    └── .env.example
```

---

## 🚀 Quick Start Guide

### Prerequisites
- **Node.js**: v18+ (Node 22 recommended)
- **Python**: 3.10+ (Python 3.12 recommended)
- **PostgreSQL** (Optional for production; defaults to embedded SQLite for instant zero-config run)

---

### Backend Setup

1. **Navigate to backend and create virtual environment**:
   ```bash
   cd backend
   python -m venv venv
   ```

2. **Activate the virtual environment**:
   - **Windows (PowerShell)**:
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS**:
     ```bash
     source venv/bin/activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   ```
   *For PostgreSQL, update `DATABASE_URL` in `.env`:*
   ```env
   DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/obligation_db"
   ```

5. **Run database migrations & seed canonical data**:
   ```bash
   python seed.py
   ```

6. **Start the backend server**:
   ```bash
   python -m uvicorn app.main:app --reload --port 8000
   ```
   API Docs available at: **http://localhost:8000/docs**

---

### Frontend Setup

1. **Navigate to frontend**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env.local
   ```
   *Ensure `NEXT_PUBLIC_API_URL` points to your backend (`http://localhost:8000`).*

4. **Run development server**:
   ```bash
   npm run dev
   ```
   Open **http://localhost:3000** in your browser.

---

## 🧪 Testing

### Backend Test Suite
Run the comprehensive pytest suite covering extraction, no-obligation detection, ambiguous ownership, CRUD, and controlled state transitions:
```bash
cd backend
python -m pytest -v
```

### Frontend Build & Typecheck
Verify production build and linting:
```bash
cd frontend
npm run lint
npm run build
```

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check & service metadata |
| `POST` | `/api/obligations/extract` | Analyze text & return candidate obligation + confidence |
| `POST` | `/api/obligations` | Persist human-confirmed obligation |
| `GET` | `/api/obligations` | List obligations with search, type, status, and risk filters |
| `GET` | `/api/obligations/{id}` | Get single obligation with full details & evidence |
| `PATCH` | `/api/obligations/{id}` | Update obligation fields |
| `PATCH` | `/api/obligations/{id}/status` | Controlled status transition (`CONFIRMED` $\to$ `IN_PROGRESS` $\to$ `COMPLETED`) |
| `DELETE` | `/api/obligations/{id}` | Delete obligation |
| `POST` | `/api/obligations/edges` | Create bidirectional/dependency edge (`DEPENDS_ON`, `LINKED`) |
| `GET` | `/api/dashboard/summary` | Aggregated metrics for You Owe, Others Owe, and At Risk |

---

## 🗺️ Product Roadmap

- **Phase 1 (Current)**: Manual text input, AI extraction adapter, Human-in-the-loop review, Obligation persistence, Dashboard feeds (You Owe, Others Owe, At Risk), Controlled state transitions, and Edge data model.
- **Phase 2**: Context analyzer, ownership agent, deadline reasoning, confidence-gated confirmation.
- **Phase 3**: Dependency graph propagation, topological obligation edges, cascading `BLOCKED` states.
- **Phase 4**: Ingestion adapters (Gmail, WhatsApp, Slack, Google Calendar).
- **Phase 5**: Evidence-based automated completion verification.
- **Phase 6**: Proactive follow-up agent, reminder triggers, escalation engine.
- **Phase 7 & 8**: Privacy hardening, audit logs, enterprise compliance.
