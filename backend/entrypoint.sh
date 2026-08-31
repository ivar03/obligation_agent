#!/bin/sh
set -e

echo "[ENTRYPOINT] Running database migrations (alembic upgrade head)..."
alembic upgrade head

echo "[ENTRYPOINT] Running startup preflight checks..."
python -m app.ops.startup_checks

echo "[ENTRYPOINT] Starting FastAPI application server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-4}
