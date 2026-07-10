# ZokoDaily Plan 5 — Deployment Design (Docker Compose)

**Date:** 2026-07-10 (updated after the Plans 2–4 verification pass and fixes)
**Status:** Draft — pending user review
**Parent spec:** [2026-07-10-zokodaily-news-aggregation-design.md](2026-07-10-zokodaily-news-aggregation-design.md) §11
**Deploys:** the Plan 1–2 backend (`backend/`), Plan 3 H5 site (`h5/`), Plan 4 admin (`admin/`).

## 1. Scope

One `docker compose up -d` brings up the complete system on a single host:

- `mysql` — MySQL 8, persistent volume
- `backend` — FastAPI + APScheduler + Crawl4AI (Chromium inside the image)
- `nginx` — serves the built H5 at `/`, admin at `/admin/`, proxies `/api/` to the backend

Out of scope: HTTPS/TLS (terminate at the host level — e.g. a host nginx/caddy with
certbot for `daily.zokomart.africa` — documented but not built), container orchestration
beyond compose, CI/CD, backups, log shipping, monitoring/alerting.

## 2. Files added

```
docker-compose.yml          # the three services
.env.example                # deploy-time secrets/ports template (.env is gitignored)
backend/Dockerfile
backend/docker-entrypoint.sh
deploy/nginx/Dockerfile     # multi-stage: builds h5 + admin, copies into nginx
deploy/nginx/nginx.conf
docs/DEPLOY.md              # runbook: first deploy, update, seed, backup hint
```

## 3. Service design

### 3.1 `mysql`

- Image `mysql:8`, `command` flags force `utf8mb4` / `utf8mb4_unicode_ci`.
- Env from `.env`: `MYSQL_ROOT_PASSWORD`, plus a dedicated app user
  (`MYSQL_USER=zokodaily`, `MYSQL_PASSWORD`, `MYSQL_DATABASE=zokodaily`).
- Named volume `mysql-data:/var/lib/mysql`.
- Healthcheck: `mysqladmin ping` — `backend` starts only when healthy
  (`depends_on: condition: service_healthy`).
- Not exposed to the host by default (internal network only); a commented-out
  `ports: ["3306:3306"]` line in compose for debugging.

### 3.2 `backend`

- `backend/Dockerfile`: `python:3.12-slim` base → install `uv` → `uv sync --frozen
  --no-dev` → `uv run playwright install --with-deps chromium`. Chromium in the image is
  **required**, not optional: article fetching (Crawl4AI) *and* listing-page discovery
  (`fetch_text_rendered` — added after verification showed JS-rendered listing sites like
  GhanaWeb serve zero anchors to plain HTTP) both depend on it. Image lands ~1.5 GB — accepted.
- Entrypoint (`docker-entrypoint.sh`): run `python -m app.seed` (idempotent — creates
  tables via `create_all`, seeds countries/sites/admin/config only if missing), then
  `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- Env: `DATABASE_URL=mysql+pymysql://zokodaily:${MYSQL_PASSWORD}@mysql:3306/zokodaily?charset=utf8mb4`,
  `JWT_SECRET` from `.env`, `SCHEDULER_ENABLED=true` (the scheduler runs in this single
  process — exactly one backend replica; scaling out would double-crawl).
- Healthcheck: `curl -f http://localhost:8000/api/health`.
- Not exposed to the host; nginx reaches it on the compose network.
- `restart: unless-stopped` on all services.

### 3.3 `nginx`

- `deploy/nginx/Dockerfile`, multi-stage:
  1. `node:20-alpine` stage A: `npm ci && npm run build` in `h5/`
  2. `node:20-alpine` stage B: same in `admin/` (its Vite `base: "/admin/"` matches the
     serving path)
  3. `nginx:alpine` final: copy `h5/dist` → `/usr/share/nginx/html`, `admin/dist` →
     `/usr/share/nginx/html/admin`, plus `nginx.conf`
- `nginx.conf` routes:
  - `location /api/ { proxy_pass http://backend:8000; }` (+ standard proxy headers;
    `client_max_body_size 10m`)
  - `location /admin/ { try_files $uri $uri/ /admin/index.html; }` (admin SPA fallback)
  - `location / { try_files $uri $uri/ /index.html; }` (H5 SPA fallback)
  - gzip on for text/js/css/json; long-cache headers for hashed assets
    (`/assets/`), no-cache for the two `index.html`s
- Host port from `.env`: `${HTTP_PORT:-80}:80`.

Same-origin serving means no CORS configuration is needed anywhere.

## 4. Configuration contract (`.env`)

```env
MYSQL_ROOT_PASSWORD=change-me
MYSQL_PASSWORD=change-me
JWT_SECRET=change-me-long-random
HTTP_PORT=80
```

`.env` is already gitignored; `.env.example` is committed. AI translation credentials are
*not* here — they live in the database and are managed through the admin Settings page
(per parent spec). The seeded admin login is `admin`/`admin123`; **the runbook's first-deploy
checklist says to change it immediately** (until an admin-password UI exists, via a
documented one-liner: `docker compose exec backend python -c "..."` that rehashes the password).

## 5. Operational flows (documented in `docs/DEPLOY.md`)

- **First deploy:** copy `.env.example` → `.env`, fill secrets, `docker compose up -d --build`,
  wait for health, log into `/admin/`, change the admin password, set the AI key in Settings,
  run test-translation, then **crawl-now every seeded site once** and correct any broken
  feed/listing URLs in the admin sites form. Site reachability is network-dependent — the
  2026-07-10 verification (from the dev box) found Punch's feed bot-filtered empty and
  Seneweb's listing URL 404ing; results from the production host may differ, so this
  check belongs to the deploy runbook, not to code.
- **Update:** `git pull && docker compose up -d --build` (frontends rebuild inside the
  nginx image; backend restart re-runs the idempotent seed harmlessly).
- **Manual ops:** trigger seed (`docker compose exec backend python -m app.seed`),
  inspect logs (`docker compose logs -f backend`), DB shell
  (`docker compose exec mysql mysql -u zokodaily -p zokodaily`).
- **Backup hint:** `mysqldump` via `docker compose exec mysql` piped to a dated file —
  one documented command, no automation in V1.
- **TLS:** point host-level reverse proxy (or set `HTTP_PORT=8080` and front it with the
  host's existing nginx/caddy + certbot for `daily.zokomart.africa`).

## 6. Verification (Plan 5's live check)

On the dev machine (Docker Desktop) or the target server:

1. `docker compose up -d --build` → all three containers healthy.
2. `curl localhost/api/health` → ok through nginx; `/` serves the H5 app;
   `/admin/` serves the admin app; deep links (`/article/1`, `/admin/articles`)
   return the right `index.html` (SPA fallbacks).
3. Log into admin, verify seeded data arrived in **MySQL** (this is the first real-MySQL
   run — the JSON columns, utf8mb4 emoji flags, and FK behavior get their production
   smoke test here; any dialect issue found becomes a fix task).
4. Crawl-now on one site inside the container (proves Chromium works in-image),
   then translation with a real key, then the article visible on the H5 homepage.
5. `docker compose down && up -d` → data survives (volume), scheduler restarts.

## 7. Risks / notes

- **First real-MySQL exposure:** all development so far ran on SQLite. The risky spots
  are `String` length overflows (e.g. very long source URLs > 700 chars), emoji in
  `utf8mb4`, and FK enforcement (now guarded at the API level by the Plan 2 fixes).
  Verification step 3 exists precisely for this.
- **Crawl4AI in a container** needs shared-memory headroom: compose sets
  `shm_size: "1g"` on the backend service (Chromium crashes with the 64 MB default).
- **Single backend replica** is a hard constraint while APScheduler runs in-process;
  documented in compose comments.
- Windows dev note: building the backend image on Docker Desktop works but the
  Playwright layer is slow; the compose file is primarily for the Linux target host.
