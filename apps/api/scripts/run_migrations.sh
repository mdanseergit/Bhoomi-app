#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# BHOOMI API — one-off database migration step
#
# Run this exactly once per deployment, before any new revision serves
# traffic. Never from the container entrypoint, because an autoscaling
# platform can start several instances from the same image at once and they
# would race each other on the same schema.
#
#   local:  bash scripts/run_migrations.sh
#   Cloud Run Job:
#     gcloud run jobs create bhoomi-migrate --image <img> \
#       --region us-central1 --set-env-vars-file=env.yaml \
#       --command bash --args scripts/run_migrations.sh
#     gcloud run jobs execute bhoomi-migrate --region us-central1 --wait
# ---------------------------------------------------------------------------
set -euo pipefail

echo "==> Waiting for the database to accept connections …"
python - <<'PY'
import os, sys, time
from urllib.parse import urlparse

url = os.environ.get("DATABASE_URL", "")
if not url:
    sys.exit("DATABASE_URL is not set.")

# A serverless Postgres can be resuming from zero, so the first connection
# can be refused for a short while. Retry rather than fail the deployment.
host = urlparse(url).hostname or ""
deadline = time.time() + 120
attempt = 0
while True:
    attempt += 1
    try:
        import psycopg
        with psycopg.connect(url, connect_timeout=10):
            print(f"connected to {host} on attempt {attempt}")
            break
    except Exception as exc:
        if time.time() > deadline:
            sys.exit(f"database unreachable after {attempt} attempts: {exc}")
        wait = min(2 ** attempt, 15)
        print(f"attempt {attempt} failed ({exc}); retrying in {wait}s")
        time.sleep(wait)
PY

echo "==> Applying migrations …"
alembic upgrade head

echo "==> Migrations complete"
