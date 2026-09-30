# Deploying BHOOMI

The API runs on **Render**, the frontend on **Vercel**. This guide covers both
and the ordering that matters between them.

| Component | Platform | Entry point |
| --- | --- | --- |
| API | Render | `apps/api/Dockerfile`, declared in `render.yaml` |
| Web | Vercel | `apps/web`, configured by `vercel.json` |

## Prerequisites

You will need:

- The repository pushed to GitHub
- A Render account
- A Vercel account
- A PostgreSQL database with the `postgis` and `vector` extensions available
- A generated `JWT_SECRET_KEY`

Generate the secret once and keep it in a password manager:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

You will paste it into Render, and it cannot be recovered from the repository
afterwards. If a secret has appeared in a chat window, a screenshot, or a commit,
treat it as compromised and generate a new one. Secrets do not belong in this
repository; it is public.

Enable the database extensions before the first migration runs:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
```

The initial migration (`e9219b1cbd09`) requires both. That failure is
intentional: a clear error at migration time is better than a service that starts
with a partially shaped schema.

## 1. API on Render

`render.yaml` at the repository root declares two services, `bhoomi-api`
(FastAPI on Docker) and `bhoomi-redis`. Render reads the blueprint, so you do not
configure these by hand.

1. Open <https://dashboard.render.com/blueprints> and choose **New Blueprint
   Instance**.
2. Select `mdanseergit/Bhoomi-app`.
3. Click **Apply**.
4. Render prompts for the two values marked `sync: false`:

   `DATABASE_URL` — the PostgreSQL connection string, using the `psycopg`
   driver so the URL scheme matches the installed driver:

   ```
   postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
   ```

   Use a direct or session-mode connection. Transaction-mode poolers reuse a
   backend connection between clients, which breaks the session state Alembic
   needs to run migrations. Add `?sslmode=require` if your provider requires
   TLS.

   `JWT_SECRET_KEY` — the value you generated.

Render builds the image, runs `alembic upgrade head` via
`apps/api/scripts/prod_start.sh`, and starts Uvicorn. The API is then reachable
at `https://bhoomi-api.onrender.com`.

Verify it:

```bash
curl https://bhoomi-api.onrender.com/api/v1/health
```

A new deployment reports the optional sources as unconfigured, which is the
expected and correct result:

```json
{
  "status": "ok",
  "database": "healthy",
  "redis": "healthy",
  "ai_provider": "deterministic_fallback_only",
  "weather_provider": "not_configured",
  "satellite_provider": "not_configured",
  "disease_model": "not_configured"
}
```

`not_configured` means the feature declines to answer rather than returning a
value it cannot support. It is not a deployment failure.

`/api/docs` returns 404 in production because interactive documentation is
disabled outside development. Render's health check uses `/api/v1/live`.

### Migrations

`scripts/prod_start.sh` runs `alembic upgrade head` before starting Uvicorn, and
the blueprint sets `WEB_CONCURRENCY=1` so two workers cannot attempt the same
migration concurrently. If you scale to multiple instances, move migrations to a
Render pre-deploy command.

## 2. Frontend on Vercel

1. Import the project at <https://vercel.com/new>.
2. Set **Root Directory** to `apps/web`.
3. Add the environment variable `BHOOMI_API_URL` set to
   `https://bhoomi-api.onrender.com`.

`vercel.json` sets the build command and security headers. The `/api/*` proxy is
defined in `apps/web/next.config.mjs` rather than in `vercel.json`, because
Vercel applies `vercel.json` rewrites before Next.js and does not expand
environment variables in rewrite destinations. Defining it in
`next.config.mjs` means the browser only ever calls same-origin paths, the
backend address stays out of the client bundle, and no CORS preflight is
involved.

## 3. Match CORS_ORIGINS to the Vercel domain

`CORS_ORIGINS` is set in `render.yaml` to the origin that serves the frontend,
currently `https://bhoomi-app-in.vercel.app`. List every origin that serves it,
comma-separated, since a Vercel project and its preview deployments are
different origins. A browser request from an origin that is missing from this
list is blocked before it reaches a handler, which presents as a sign-in that
never completes.

The API refuses to start if `CORS_ORIGINS` contains `localhost` while
`APP_ENV=production`, since that would indicate development configuration
reaching a public deployment.

## Keeping the API running

A suspended service answers every request with `503` and the header
`x-render-routing: suspend-by-user`, which the Vercel proxy surfaces to the
browser as `502 Bad Gateway`. The frontend then reports the backend as
unreachable. This is a service state, not a configuration error, and it does not
resolve on its own: resume `bhoomi-api` in the Render dashboard.

On the free plan, Render also suspends a service after a period of inactivity.
The first request after that takes roughly a minute while the instance starts,
and it is not warm enough to serve a page load, which issues several requests at
once. The frontend bounds a single request at 60 seconds for this reason and
reports a timeout distinctly from a refused connection.

## Configuration reference

### Required

Startup fails without these.

| Variable | Notes |
| --- | --- |
| `JWT_SECRET_KEY` | At least 32 characters in production. |
| `DATABASE_URL` | Must use the `+psycopg` driver. |
| `REDIS_URL` | Injected by the blueprint from `bhoomi-redis`. |
| `CORS_ORIGINS` | Comma-separated. No `localhost` in production. |

### Optional

Anything unconfigured reports itself unavailable instead of guessing.

| Variable | Default | Notes |
| --- | --- | --- |
| `NVIDIA_API_KEY` | unset | Unset means deterministic explanations only. |
| `SATELLITE_PROVIDER` | `none` | Simulated sources are refused in production. |
| `DISEASE_MODEL_PROVIDER` | `none` | Must resolve to a validated model. |
| `WEATHER_FALLBACK_PROVIDER` | `none` | `nasa_power` needs no key. |
| `STORAGE_BACKEND` | `local` | Use `s3` for upload durability. |
| `MAX_UPLOAD_SIZE_MB` | `8` | Applies to Crop Doctor image uploads. |

Render's filesystem is ephemeral, so `STORAGE_BACKEND=local` loses uploaded
images on each redeploy. Switch to `s3` if the files need to persist.

## Startup validation

`Settings.validate_for_startup` runs before the app binds its port and refuses to
start on a missing or short `JWT_SECRET_KEY`, `DEBUG=true` in production, a
`localhost` entry in `CORS_ORIGINS`, a simulated satellite source, or a disease
provider that does not report itself as validated. A deployment that cannot
produce honest results should fail at deploy time rather than during a
consultation.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Sign-in sits on "Signing in", then fails | The API is suspended or unreachable. Check `bhoomi-api` in Render. |
| `503` with `x-render-routing: suspend-by-user` | The Render service is suspended and must be resumed. |
| Browser console shows a CORS error | The origin is missing from `CORS_ORIGINS`. |
| Build fails during `e9219b1cbd09` | `postgis` or `vector` not enabled on the database. |
| `RuntimeError` at startup | The message names each configuration problem. |
| `CORS_ORIGINS must not contain localhost` | A development origin reached production settings. |
| Migrations fail on a pooled connection | Use a direct or session-mode connection string. |
| First request after an idle period is slow | The free plan was suspended and is starting up. |
| Crop Doctor returns 503 | Expected while `DISEASE_MODEL_PROVIDER=none`. |
