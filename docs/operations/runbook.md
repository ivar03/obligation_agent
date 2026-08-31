# SRE & Incident Response Runbook

## Overview
This runbook guides operators through triage, diagnostic workflows, and remediation procedures for Obligation Agent production incidents.

---

## Service Endpoints & Probes

| Endpoint | Type | Expected Status | Description |
|---|---|---|---|
| `GET /api/health` | Liveness | 200 OK | Process liveness probe. Fails only if process deadlocked or crashed. |
| `GET /api/ready` | Readiness | 200 OK / 503 Unavailable | Dependency readiness probe. Checks database, worker queue, config. |
| `GET /api/metrics` | Observability | 200 OK | Real-time system, API latency percentiles (p50/p95/p99), and queue metrics. |

---

## Standard Incident Scenarios & Remediation

### 1. Database Connection Exhaustion (HTTP 500 / 503)
**Symptoms**: High API latency, `/api/ready` reporting database errors, log messages containing `QueuePool limit exceeded`.
**Remediation**:
1. Check active database connections: `SELECT count(*) FROM pg_stat_activity WHERE datname = 'obligations_prod';`
2. Increase pool size in `.env.production`: `DB_POOL_SIZE=30`, `DB_MAX_OVERFLOW=20`.
3. Check for leaked or unclosed sessions in worker tasks.
4. Restart application workers gracefully to flush stale connections: `docker-compose restart backend worker`.

### 2. Circuit Breaker OPEN for External Provider (Slack/Gmail)
**Symptoms**: Execution requests returning `CIRCUIT_OPEN`, logs indicating consecutive outbound dispatch failures.
**Remediation**:
1. Inspect provider status via `GET /api/metrics` (under `circuit_breakers`).
2. Verify provider credentials (`SLACK_BOT_TOKEN`, `GMAIL_CLIENT_SECRET`).
3. Check provider status pages (e.g., status.slack.com).
4. After resolving credentials or provider outage, circuit breaker will automatically probe recovery (HALF_OPEN after 60s).

### 3. Worker Queue Backlog / Crash Recovery
**Symptoms**: `GET /api/metrics` shows rising `worker_queue.queued` or `claimed` jobs without progress.
**Remediation**:
1. Check worker logs: `docker-compose logs --tail=100 -f worker`.
2. Verify lease timeout recovery: Stale jobs older than `WORKER_LEASE_TIMEOUT_SECONDS` (300s) are automatically reset to `QUEUED` upon worker restart.
3. Scale worker concurrency: `docker-compose up --scale worker=3 -d`.

### 4. Rate Limiting Spikes (HTTP 429)
**Symptoms**: Clients receiving HTTP 429 `RATE_LIMIT_EXCEEDED`.
**Remediation**:
1. Verify client IP and workspace in access logs.
2. If traffic is legitimate bulk import, configure `RATE_LIMIT_CSV_IMPORT_PER_MINUTE` or `RATE_LIMIT_DEFAULT_PER_MINUTE`.
