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

# Health check — hit the root endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

EXPOSE 8000

# The start script runs Alembic migrations then launches Uvicorn.
CMD ["bash", "scripts/prod_start.sh"]
