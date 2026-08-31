# Obligation Agent — Production Operations & Deployment Guide

This guide describes operational procedures for deploying, maintaining, monitoring, backing up, and recovering the **Obligation Agent** platform in production.

---

## 1. Architecture Overview

- **Backend**: FastAPI (Python 3.12) with async SQLAlchemy 2.0.
- **Frontend**: Next.js 16 (React 19, TypeScript, TailwindCSS).
- **Background Worker**: In-process or asynchronous worker queue managing execution retries, continuous monitoring, and periodic retention cleanup.
- **Security Boundary**: Multi-tenant workspace scoping, JWT authentication (`AUTH_MODE=production`), RBAC (`OWNER`, `ADMIN`, `OPERATOR`, `MEMBER`, `VIEWER`), symmetric credential encryption at rest (Fernet AES/HMAC).

---

## 2. Production Startup & Configuration

### Environment Variables
Copy `.env.example` to `.env` and set mandatory production values:
```bash
cp .env.example .env
```

Key Production Variables:
- `APP_ENV=production`
- `AUTH_MODE=production`
- `JWT_SECRET_KEY`: Minimum 32-character random string.
- `ENCRYPTION_KEY`: 32-byte urlsafe base64 Fernet key.
- `DATABASE_URL`: Primary database connection string (PostgreSQL or SQLite).

### Production Readiness Verification
Before exposing traffic, run the diagnostic CLI:
```bash
cd backend
python -m app.ops.production_readiness
```
The command returns exit code `0` on success and fails with a descriptive error list if any required configuration or safety check fails.

### Starting via Docker Compose
```bash
docker-compose up -d --build
```

---

## 3. Database Migrations & Rollback

### Run Pending Migrations
```bash
cd backend
alembic upgrade head
```

### Rollback Migration by 1 Step
```bash
cd backend
alembic downgrade -1
```

---

## 4. Health & Observability Endpoints

- **Liveness (`GET /api/health`)**: Verifies the process is responsive and returns uptime and memory metrics.
- **Readiness (`GET /api/ready`)**: Verifies primary datastore connectivity, worker subsystem state, and secret configuration. Returns `503 Service Unavailable` if unready.
- **Metrics (`GET /api/metrics`)**: Aggregated system, obligation, event, decision, and execution metrics without leaking credentials or message contents.

---

## 5. Backup & Disaster Recovery Procedures

### 1. Database Backup
For SQLite:
```bash
sqlite3 /data/obligations.db ".backup '/data/backups/obligations_backup_$(date +%Y%m%d_%H%M%S).db'"
```
For PostgreSQL:
```bash
pg_dump -Fc -h localhost -U postgres obligation_db > /data/backups/obligation_db_$(date +%Y%m%d_%H%M%S).dump
```

### 2. Database Restore
For SQLite:
```bash
cp /data/backups/obligations_backup_YYYYMMDD_HHMMSS.db /data/obligations.db
```
For PostgreSQL:
```bash
pg_restore -c -h localhost -U postgres -d obligation_db /data/backups/obligation_db_YYYYMMDD_HHMMSS.dump
```

### 3. Application & Worker Recovery after Interruption
1. Restart the backend service (`docker-compose restart backend`).
2. The `worker_queue` reinitializes automatically.
3. In-flight execution records with status `QUEUED` or `EXECUTING` retain their `idempotency_key` and cannot produce duplicate downstream deliveries.
4. Unacknowledged or failed executions transition deterministically according to bounded retry limits.

---

## 6. Retention & Data Cleanup Routine
Run the workspace retention cleanup service periodically or via cron:
```python
from app.services.cleanup_service import CleanupService
# Prunes un-correlated raw event records older than retention window (default 90 days)
# Preserves all immutable audit logs, confirmed evidence, and decision plans
await CleanupService.run_retention_cleanup(session, workspace_id="ws-prod", retention_days=90)
```
