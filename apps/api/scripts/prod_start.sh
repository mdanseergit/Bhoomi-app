#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# BHOOMI API — production startup
#
# 1. Run pending Alembic migrations (idempotent).
# 2. Start Uvicorn with production settings.
# ---------------------------------------------------------------------------
set -euo pipefail

echo "==> Running database migrations …"
alembic upgrade head

echo "==> Starting BHOOMI API …"
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --log-level info \
    --proxy-headers \
    --forwarded-allow-ips='*'
