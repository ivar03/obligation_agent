# Production Deployment Guide

## Architecture Topology
Obligation Agent is deployed as a containerized microservices stack:
- **FastAPI API Service**: Stateless web service handling REST API, Webhooks, SSE streams.
- **Standalone Queue Worker**: Durable polling worker executing background ingestion and message normalization.
- **PostgreSQL 16**: Primary persistent datastore with connection pooling and advisory locking.
- **Next.js Frontend**: Server-rendered React client consuming backend REST endpoints.

---

## Deployment Steps

### 1. Environment Preparation
Copy and customize `.env.production.example`:
```bash
cp .env.production.example .env.production
# Generate high entropy keys
export JWT_SECRET_KEY=$(openssl rand -hex 32)
export ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

### 2. Database Provisioning & Migrations
```bash
# Apply all Alembic schema migrations
alembic upgrade head

# Run preflight startup diagnostics
python -m app.ops.startup_checks
```

### 3. Container Orchestration
```bash
docker-compose -f docker-compose.yml up -d --build
```

### 4. Zero-Downtime Rolling Upgrades
1. Apply new migrations: `docker-compose run --rm backend alembic upgrade head`
2. Update backend services sequentially (readiness probe prevents unready containers from receiving traffic).
3. Scale workers as needed.
