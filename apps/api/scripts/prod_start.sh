#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# BHOOMI API — production startup (serves traffic only)
#
# Migrations are NOT run here by default. A platform that starts several
# instances from one image (Cloud Run, or any autoscaler) would have every
# instance race to migrate the same database, which deadlocks or leaves a
# half-applied schema. Run scripts/run_migrations.sh once, as a separate
# one-off step, before traffic reaches a new revision.
#
# Set RUN_MIGRATIONS=true only where exactly one instance can ever start at a
# time, such as a single-instance Render service.
# ---------------------------------------------------------------------------
set -euo pipefail

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "==> RUN_MIGRATIONS=true — applying migrations from this instance"
    echo "==> Only safe when a single instance can start at a time"
    alembic upgrade head
else
    echo "==> Skipping migrations (RUN_MIGRATIONS not set). Apply them separately."
fi

echo "==> Starting BHOOMI API …"
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --log-level info \
    --proxy-headers \
    --forwarded-allow-ips='*'
