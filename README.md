<div align="center">

<img src="assets/logo.jpeg" alt="BHOOMI" width="120" height="120" />

# BHOOMI

**Agricultural intelligence that only claims what your data supports.**

BHOOMI turns a farmer's own field records into a single, explainable picture:
what the crop is likely to face, what the soil and weather records actually
support, and which actions are worth taking next.

<br />

**Try it:** [bhoomi-app-in.vercel.app/login](https://bhoomi-app-in.vercel.app/login) — deployed on Vercel

</div>

---

## What BHOOMI does

BHOOMI brings farm, soil, weather, satellite, and crop records together and
produces a **BHOOMI Intelligence Score** for each farm, together with the
evidence behind it. Every number is traceable to a recorded observation, and
every recommendation names the data it came from.

| Area | What it covers |
| --- | --- |
| **Farm Intelligence** | A per-farm health score with a component breakdown, the observations that produced it, and an explicit list of what is missing |
| **Advisories** | Prioritised, explainable actions with the source snapshot attached, and a review workflow for high-severity items |
| **Crop Doctor** | Leaf-image triage that returns a *possible* disease with confidence and severity, never a confirmed diagnosis |
| **Soil Health** | pH and organic-carbon scoring against agronomic thresholds, with nutrient readings recorded even when they do not yet affect the score |
| **Weather Risk** | Heat, cold, rainfall and warning-based risk with freshness classification so cached data is never presented as live |
| **Vegetation Health** | NDVI and EVI based stress detection with trend analysis |
| **Cooperation Network** | A federated model-sharing layer between state nodes, with explicit publication and review states before anything is shared |

## The design principle

Most agricultural software fills gaps with plausible numbers. BHOOMI does not.

- **No fabricated data.** If a source is unconfigured, unreachable, or has no
  observation for a farm, the feature reports that it is unavailable. It never
  substitutes a default, a baseline, or a simulated reading.
- **No silent scoring.** A score appears only when the inputs the score is
  actually computed from are present. Humidity and wind are recorded, but they
  do not make a climate score look measured when no temperature was observed.
- **Partial data is labelled.** When only some components have data, BHOOMI
  reports the coverage alongside the score and names the missing inputs.
- **No unvalidated model as a diagnosis.** Crop Doctor runs a development
  heuristic. Production deployments refuse it, and this is enforced against the
  model's own validated flag rather than a configuration string, so naming a
  provider that does not exist cannot unlock the feature.
- **Fail loudly at startup.** Production configuration is validated on boot.
  Simulated data sources and unvalidated models stop the process rather than
  serving quietly incorrect results.

## Honest empty states

This principle shows up in the interface. A farm with no weather observation
shows *"Not connected"* rather than a plausible temperature. An intelligence
score of `null` renders as *"Not enough data"* rather than `0`. Crop Doctor
returns `503` with a plain explanation when no validated model is available,
instead of a guess.

## Architecture

```
.
├── apps/
│   ├── api/        FastAPI service
│   └── web/        Next.js application
└── docs/           Data provider references
```

**Backend — FastAPI**

- FastAPI with a versioned REST surface under `/api/v1`
- SQLAlchemy 2.0 over PostgreSQL, with PostGIS and pgvector
- Alembic for schema migrations
- Redis for caching and rate limiting
- Celery for background notification delivery
- A deterministic rule engine for agriculture scoring, so results are
  reproducible and explainable
- Pluggable provider integrations for AI explanations, weather, satellite,
  embeddings, and storage

**Frontend — Next.js**

- Next.js 14 App Router with TypeScript
- Tailwind CSS for styling
- TanStack Query for server state
- React Hook Form with Zod validation
- Recharts and Leaflet for visualisation
- Vitest and Testing Library for tests

### The intelligence engine

Scoring is deterministic and rule-based rather than model-generated, which is
what makes a result reproducible and defensible. Weather, water, vegetation,
soil, and crop-history components each report a score, a severity, the factors
that moved it, and whether the inputs needed to compute it were actually
observed. The overall score is assembled only from components that have data,
and the result carries its coverage and its missing inputs.

Explanations are a separate layer. When an AI provider is configured, BHOOMI
asks it to explain a result that the rule engine already produced, and the
response records which provider answered and whether that provider was a model
or the deterministic fallback. When no provider is configured, the
deterministic explanation is used and says only what the recorded data supports.

## Roles

| Role | Purpose |
| --- | --- |
| `farmer` | Manages own farms and receives advisories |
| `agronomist` | Reviews and acts on advisories |
| `state_admin` | Administers a state node and its shared models |
| `platform_admin` | Platform-wide administration and data-source oversight |

## Data sources

BHOOMI integrates with official and open agricultural data providers. Provider
references, field mappings, units, and freshness rules are documented under
[`docs/data-providers/`](docs/data-providers/).

| Source | Data | Auth |
| --- | --- | --- |
| India Meteorological Department | Weather observations and forecasts | API key |
| ISRO Bhoonidhi | Satellite imagery | API key |
| Copernicus Data Space | Satellite imagery | API key |
| NASA POWER | Global weather and climate | None |
| Soil Health Card | Soil test results | API key |
| FAOSTAT | Agricultural statistics | None |

A registry entry declares that a source exists. It is not evidence that a
deployment reached it, so entries are reported as *unverified* until they are
proven reachable, and the admin dashboard separates **Connected** from
**Not Verified** rather than presenting a total as if all were live.

## Getting started

### Prerequisites

- Python 3.13+
- Node.js 20+
- PostgreSQL 15+ with the `postgis` and `vector` extensions
- Redis 7+

### Backend

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
```

Create your environment file. It contains no credentials:

```bash
cp .env.example .env
```

The API refuses to start with an incomplete configuration, so set at minimum
`JWT_SECRET_KEY`, `DATABASE_URL` and `REDIS_URL`.

Apply the schema and start the service:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Interactive API documentation is available at `/api/docs` outside production.

### Frontend

```bash
cd apps/web
npm install
cp .env.example .env.local
npm run dev
```

The app is served at `http://localhost:3000`. The browser only ever calls
same-origin `/api/*` paths, which the Next.js server proxies to the backend, so
backend addresses and secrets stay out of the client bundle.

## Testing

```bash
# Backend
cd apps/api
.venv\Scripts\python -m pytest -q

# Frontend
cd apps/web
npm run typecheck
npm run lint
npm run test
```

The backend suite runs against a dedicated test database and disables live
providers by default, so it is hermetic and does not depend on network access
or third-party model endpoints. Set `BHOOMI_TEST_LIVE_AI=1` to exercise a real
provider chain locally.

## Project layout

```
.
├── apps/
│   ├── api/
│   │   ├── alembic/        Schema migrations
│   │   ├── app/
│   │   │   ├── api/v1/     REST endpoints
│   │   │   ├── core/       Config, database, security, logging
│   │   │   ├── integrations/  Weather, satellite, AI, disease, storage
│   │   │   ├── ml/         Disease model inference
│   │   │   ├── models/     Database models
│   │   │   ├── services/   Business logic and the intelligence engine
│   │   │   └── workers/    Background tasks
│   │   ├── scripts/        Development utilities
│   │   └── tests/
│   └── web/
│       ├── app/            App Router pages
│       ├── components/     UI components
│       └── lib/            API client, types, i18n, contexts
├── assets/                 Logo and imagery
└── docs/                   Deployment and data provider references
```

## Deployment

Live instance: **[bhoomi-app-in.vercel.app](https://bhoomi-app-in.vercel.app/login)**

| Component | Platform | Config |
| --- | --- | --- |
| **API** | Render (Docker) | [`render.yaml`](render.yaml) |
| **Web** | Vercel | [`apps/web/vercel.json`](apps/web/vercel.json) |
| **Database** | PostgreSQL | Requires the `postgis` and `vector` extensions |
| **Redis** | Render Redis | Provisioned by the blueprint |

Render reads `render.yaml` and provisions the API and Redis together, so the
only values you supply are `DATABASE_URL` and `JWT_SECRET_KEY`. The startup
script runs `alembic upgrade head` before the server begins serving.

Reference templates:
[`apps/api/.env.production.example`](apps/api/.env.production.example) and
[`apps/web/.env.production.example`](apps/web/.env.production.example).

Full instructions, database prerequisites, and troubleshooting are in
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Documentation

- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — deploying the API to Render and
  the frontend to Vercel, including database prerequisites, required
  environment variables, and troubleshooting
- [`docs/data-providers/`](docs/data-providers/) — provider coverage, field
  mappings, units, and freshness classification for India-specific and global
  sources

## License

Released under the [MIT License](LICENSE).

## Acknowledgements

BHOOMI is built on the work of India's public agricultural data infrastructure
and open satellite programmes. The providers integrated here are documented in
[`docs/data-providers/`](docs/data-providers/) with their respective
authentication requirements and terms of use.
