# ---------------------------------------------------------------------------
# BHOOMI API — Google Cloud Run deployment
#
# Cloud Run free tier: 2M requests/month, 240k vCPU-seconds, 450k
# GiB-seconds. Scales to zero when idle and wakes on the next request, so
# there is no 15-minute sleep penalty of the kind a Render free service
# incurs.
#
# Prerequisites:
#   1. A GCP project with billing enabled. The free tier never charges, but
#      Cloud Run requires a billing account to be linked to the project.
#   2. gcloud authenticated:  gcloud auth login && gcloud config set project <id>
#   3. A Postgres with PostGIS and pgvector. Neon free provides both.
#      Enable them once per database:
#        CREATE EXTENSION IF NOT EXISTS postgis;
#        CREATE EXTENSION IF NOT EXISTS vector;
#   4. A Redis instance. Upstash free works over TLS.
#
# Build and deploy, from the repository root:
#   gcloud builds submit --tag gcr.io/<project>/bhoomi-api apps/api
#   gcloud run deploy bhoomi-api \
#     --image gcr.io/<project>/bhoomi-api \
#     --region us-central1 \
#     --port 8080 \
#     --min-instances 0 \
#     --max-instances 2 \
#     --cpu 1 --memory 512Mi \
#     --set-env-vars-file=apps/api/env.cloudrun.yaml \
#     --set-secrets=BHOOMI_JWT_SECRET=jwt-secret:latest \
#     --no-allow-unauthenticated
#
# Apply migrations BEFORE the new revision serves traffic. The container no
# longer migrates on startup, because Cloud Run can start several instances
# from one image and they would race each other on the schema.
#
#   gcloud run jobs create bhoomi-migrate \
#     --image gcr.io/<project>/bhoomi-api \
#     --region us-central1 \
#     --command bash --args scripts/run_migrations.sh \
#     --set-env-vars-file=apps/api/env.cloudrun.yaml
#   gcloud run jobs execute bhoomi-migrate --region us-central1 --wait
#
# CORS: the API serves the browser directly, so CORS_ORIGINS must list the
# frontend origin. A stale value there breaks sign-in before any handler
# runs.
# ---------------------------------------------------------------------------

steps:
  - id: build
    name: gcr.io/cloud-builders/docker
    args: ["build", "-t", "${_IMAGE}", "-f", "apps/api/Dockerfile", "apps/api"]

  - id: push
    name: gcr.io/cloud-builders/docker
    args: ["push", "${_IMAGE}"]

substitutions:
  _IMAGE: gcr.io/${PROJECT_ID}/bhoomi-api
images:
  - ${_IMAGE}
options:
  logging: CLOUD_LOGGING_ONLY
