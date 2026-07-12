# ZokoDaily Deployment

The stack is docker-compose: **mysql** + **backend** (FastAPI, single replica) + **nginx**
(builds the H5 site and the admin SPA and reverse-proxies `/api` to the backend). It serves the
public H5 at `/` and the admin at `/admin/`.

## Prerequisites

- Docker + Docker Compose on the host.
- A copy of `.env.example` → `.env` at the repo root with real values:
  - `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD`
  - `JWT_SECRET` — random, **≥ 32 characters** (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
  - `HTTP_PORT` — public port for nginx (default 80)

## Fresh install

1. `cp .env.example .env` and edit the values.
2. `docker compose build`
3. `docker compose up -d`
4. On backend startup the entrypoint seed runs: it creates all tables (`create_all`), applies
   idempotent column migrations (`ensure_schema`), and seeds reference data, the default admin
   (`admin` / `admin123`), and config defaults (mock SMS, 8% commission).
5. Verify: `curl http://localhost:${HTTP_PORT}/api/health` → `{"status":"ok"}`.
6. Log into `/admin/` as `admin` / `admin123`, then:
   - Create real staff accounts under **员工管理** (roles: admin / auditor / cs) and stop using
     the default admin.
   - Set the SMS provider + API key, commission rate, and driver payment instructions under
     **物流设置**.

## Upgrade an existing (news-only) deployment

1. Pull the new code.
2. `docker compose build`
3. `docker compose up -d`
4. On startup: `create_all` adds the new `lg_*` tables, and `ensure_schema` adds the
   `admin_user.role` column to the existing table (no manual SQL). Existing news data and the
   `mysql-data` volume are untouched; the `uploads-data` volume is created empty.
5. Configure logistics staff and settings as in the fresh-install step 6.

## Operational invariants

- **Exactly one backend replica.** APScheduler runs in-process; a second replica would
  double-run crawls and the daily logistics job. Do not scale the backend service.
- **Persistent state lives in named volumes:** `mysql-data` (database) and `uploads-data`
  (driver/vehicle document images). Include both in the host's backup process.
- Logistics runtime config lives in the database (`app_config`), not in env — reconfigure it via
  the admin UI, not by editing compose.

## Common operations

- Rebuild only the frontends after UI changes: `docker compose build nginx && docker compose up -d nginx`.
- Tail logs: `docker compose logs -f backend`.
- Full teardown **including data**: `docker compose down -v` (drops the volumes — irreversible).
