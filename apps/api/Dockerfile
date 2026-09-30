# ---------------------------------------------------------------------------
# BHOOMI API — production Dockerfile
#
# Build:  docker build -t bhoomi-api .
# Run:    docker run --env-file .env -p 8000:8000 bhoomi-api
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS base

# System packages needed by psycopg (libpq) and GeoAlchemy2 (GEOS/GDAL/PROJ)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libpq5 libgeos-c1v5 libproj25 gdal-bin curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root application user
RUN useradd --create-home --shell /bin/bash bhoomi
WORKDIR /home/bhoomi/app

# ---------------------------------------------------------------------------
# Dependencies stage — cache pip downloads across rebuilds
# ---------------------------------------------------------------------------
FROM base AS deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Final image
# ---------------------------------------------------------------------------
FROM deps AS final

COPY . .

# Writable directories the app uses at runtime
RUN mkdir -p var/uploads && chown -R bhoomi:bhoomi /home/bhoomi/app

USER bhoomi

# Health check — hit the root endpoint.
#
# The port comes from $PORT rather than a literal: Cloud Run injects 8080,
# Render injects 10000, and a hardcoded port silently reports unhealthy
# everywhere except the one platform it was written on.
#
# The start period must outlast a cold start. With the previous 10s the
# container was declared unhealthy while imports and the database pool
# were still warming. Migrations no longer run here (see
# scripts/run_migrations.sh), so this is startup time, not schema time.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f "http://localhost:${PORT:-8000}/" || exit 1

# Cloud Run expects the app on 8080. EXPOSE is documentation only and does
# not change the listening port, which uvicorn takes from $PORT.
EXPOSE 8080

# The start script runs Alembic migrations then launches Uvicorn.
CMD ["bash", "scripts/prod_start.sh"]
