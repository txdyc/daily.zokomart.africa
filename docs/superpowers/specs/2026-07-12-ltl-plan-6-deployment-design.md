# LTL Plan 6: Deployment — Design Spec

Status: Draft for review
Date: 2026-07-12
Parent product: ZokoDaily LTL Logistics module
Depends on: LTL Plans 1–5 (backend + H5 + admin), the existing docker-compose deployment
Precedes: — (final plan of the LTL series)

---

## 1. Overview

This spec covers what it takes to run the logistics module in the existing production
deployment. The stack is `docker compose`: **mysql** + **backend** (FastAPI, one replica) +
**nginx** (multi-stage build of the H5 and admin SPAs, reverse-proxying `/api` to the backend).

Most of the logistics feature deploys with no change, because the codebase already:
- creates all `lg_*` tables at startup via `Base.metadata.create_all` (run from the seed in
  `docker-entrypoint.sh`);
- seeds logistics config defaults (`lg_sms_provider`, `lg_commission_rate`, …) in `seed_all`;
- serves uploaded attachments over `/api/lg/uploads/{id}`, already proxied by the `location /api/`
  nginx block (and `client_max_body_size 10m` covers the 8 MB upload cap);
- rebuilds both SPAs from source in `deploy/nginx/Dockerfile`, so the logistics UI ships on the
  next image build with no Dockerfile edit.

Three real gaps remain, which this plan closes:
1. **The `admin_user.role` column** (added to the model in Plan 5) is not applied to an
   already-deployed MySQL — `create_all` never alters existing tables.
2. **Uploaded files are not persisted** — they land on the backend container's ephemeral
   filesystem and are lost on redeploy.
3. **Operational guidance** — env/secrets and a rollout runbook for a first install and for
   upgrading an existing news-only deployment.

### 1.1 Goals

1. A `docker compose build && up` brings up a working stack with logistics fully functional.
2. Upgrading an existing (news-only) deployment adds the `role` column automatically, with no
   manual SQL.
3. Uploaded driver/vehicle documents survive container restarts and redeploys.
4. An operator has a clear runbook and knows which secrets/config to set.

### 1.2 Non-goals (deferred)

- Object storage (S3) with signed URLs for uploads — V2 (V1 keeps local-disk uploads).
- A general migration framework (Alembic) — the project uses `create_all`; this plan adds one
  idempotent additive migration in the same spirit, not a framework.
- Backups, monitoring/alerting, horizontal scaling, TLS termination — out of scope here
  (the backend must stay a single replica; APScheduler runs in-process).
- Any application/UI behavior change — Plans 1–5 own that.

### 1.3 Success criteria

- Fresh install: `docker compose up` → `/api/health` is 200, admin login works, a driver
  document can be uploaded and viewed in the admin review dialog.
- Upgrade path: pointing the stack at a MySQL volume whose `admin_user` lacks `role` results in
  the column being added on startup (verified by `/api/admin/auth/me` returning a role).
- Persistence: a file uploaded via `/api/lg/uploads` is still retrievable after
  `docker compose restart backend`.

---

## 2. Change 1 — Idempotent schema migration

### 2.1 Problem

`create_all` creates missing tables (so all `lg_*` tables appear on any deployment) but does not
add columns to tables that already exist. The `admin_user` table predates Plan 5, so an existing
MySQL has no `role` column, and the admin role-gating (Plan 5) would break (`/auth/me` and
`require_roles` read `AdminUser.role`).

### 2.2 Design

A new module `backend/app/migrate.py` exposes `ensure_schema(engine)`: a short, idempotent,
dialect-agnostic routine that inspects the live database and applies additive fixes that
`create_all` cannot. For V1 it handles exactly one column:

- Use `sqlalchemy.inspect(engine)` to read `admin_user`'s columns.
- If `role` is absent, execute
  `ALTER TABLE admin_user ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'admin'`.
- Wrap the check so a fresh database (where `create_all` already made `admin_user` **with**
  `role`, and SQLite test DBs) is a clean no-op.

The function is written as a small list of `(table, column, add-column-DDL)` checks so future
additive columns are a one-line addition — extensible without pulling in Alembic.

### 2.3 Where it runs

`ensure_schema(engine)` is called from the seed entry point (`app/seed.py`'s `__main__`, which
`docker-entrypoint.sh` runs), ordered: `create_all` (tables) → `ensure_schema` (columns on
pre-existing tables) → `seed_all` (reference data + default admin + config). The entrypoint's
existing 5-attempt retry loop already covers the case where MySQL isn't ready yet.

### 2.4 Testing

A backend test (`backend/tests/test_migrate.py`) that: builds an engine with an `admin_user`
table lacking `role` (raw DDL), runs `ensure_schema`, and asserts the column now exists and
defaults to `'admin'`; and that a second `ensure_schema` call is a no-op (idempotent). Runs in
the existing pytest suite (SQLite).

---

## 3. Change 2 — Persistent upload storage

### 3.1 Design

Uploaded attachments are written by the backend to `settings.upload_dir` (default `uploads`,
i.e. `/app/uploads` in the container). Add a named docker volume so they persist:

- In `docker-compose.yml`, declare a `uploads-data` volume (alongside `mysql-data`).
- Mount it on the **backend** service at `/app/uploads`.
- Set `UPLOAD_DIR: /app/uploads` explicitly in the backend service environment (so the mount
  path and the app's configured path are unambiguously the same).

No nginx change: attachments are served by the backend via `/api/lg/uploads/{id}`
(`FileResponse`), already proxied by `location /api/`. The `client_max_body_size 10m` limit
comfortably exceeds the backend's 8 MB per-file cap.

### 3.2 Testing

Covered by the deployment smoke (§6): upload a file, `docker compose restart backend`, confirm
it is still retrievable — proving the volume persists across container recreation.

---

## 4. Change 3 — Environment and secrets

The compose file already reads `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD`, `JWT_SECRET`, and
`HTTP_PORT` from the environment (a root `.env` file that docker compose auto-loads). Plan 6:

- Adds a repo-root `.env.example` documenting every variable the stack needs: MySQL passwords,
  a strong `JWT_SECRET` (**≥ 32 characters** — the app logs an `InsecureKeyLengthWarning` below
  that, and short secrets weaken HS256 admin/H5 tokens), and `HTTP_PORT`.
- Notes that logistics runtime config is **not** env-based: the SMS provider/key/sender,
  commission rate, and payment instructions are stored in `app_config` (seeded with safe
  defaults: `mock` SMS, 8% commission, empty payment text) and set post-deploy through the admin
  UI (物流设置) or `PUT /api/admin/lg/config`.

The existing `backend/.env.example` (used for local non-docker runs) already lists `UPLOAD_DIR`;
it stays as-is. The new file is the **repo-root** `.env.example` for the compose stack.

---

## 5. Change 4 — Deployment runbook

A new doc `deploy/README.md` (or a section appended to an existing deploy doc) with two flows:

**Fresh install**
1. Copy `.env.example` → `.env`; set MySQL passwords, a ≥32-char `JWT_SECRET`, `HTTP_PORT`.
2. `docker compose build && docker compose up -d`.
3. The backend entrypoint creates tables, runs `ensure_schema`, and seeds the default admin
   (`admin` / `admin123`) + config defaults.
4. Log into `/admin/`, change the admin password path (create real staff via 员工管理 and stop
   using the default), set SMS provider + key, commission rate, and payment instructions.

**Upgrade from a news-only deployment**
1. Pull the new code; `docker compose build`.
2. `docker compose up -d` — on backend start, `create_all` adds the `lg_*` tables and
   `ensure_schema` adds `admin_user.role`; existing news data and the `mysql-data` volume are
   untouched.
3. The first deploy with logistics has empty upload storage; the `uploads-data` volume is created
   automatically. Create logistics staff and set config as above.

The runbook also records the operational invariants already true of the stack: **exactly one
backend replica** (in-process scheduler), and MySQL/uploads live in named volumes that must be
included in whatever host backup process exists.

---

## 6. Verification (local docker compose smoke)

The plan's final task runs a real build-and-run on the dev machine (requires Docker):

1. Create a throwaway `.env` with test secrets; `docker compose build`.
2. `docker compose up -d`; wait for the backend healthcheck to pass.
3. `curl http://localhost:${HTTP_PORT}/api/health` → `{"status":"ok"}`.
4. Log in as `admin` via `/api/admin/auth/login`; `GET /api/admin/auth/me` → includes
   `"role":"admin"` (proves `ensure_schema` ran against MySQL).
5. Hit a logistics admin endpoint (e.g. `GET /api/admin/lg/stats/overview`) → 200.
6. Upload a file through `/api/lg/uploads` (as an OTP-logged-in H5 user, or assert the endpoint
   exists); `docker compose restart backend`; re-fetch the attachment → still 200 (volume
   persists).
7. **Upgrade rehearsal:** drop the `role` column from `admin_user` in the running MySQL
   (`ALTER TABLE admin_user DROP COLUMN role`), `docker compose restart backend`, and confirm
   `ensure_schema` re-adds it (`/api/admin/auth/me` returns a role again).
8. Load `/admin/` and `/` in a browser to confirm both SPAs (with logistics) are served.
9. `docker compose down -v` to clean up the throwaway stack.

If Docker is unavailable in the environment, fall back to `docker compose config` (syntax
validation) + the `ensure_schema` pytest, and run steps 3–8 against the non-docker dev stack
documented for Plans 1–5; the plan will note this fallback explicitly.

---

## 7. Files touched

| File | Change |
| --- | --- |
| `backend/app/migrate.py` | **new** — `ensure_schema(engine)` idempotent additive migration |
| `backend/app/seed.py` | call `ensure_schema(engine)` between `create_all` and `seed_all` |
| `backend/tests/test_migrate.py` | **new** — column added + idempotent |
| `docker-compose.yml` | `uploads-data` volume; mount on backend; `UPLOAD_DIR` env |
| `.env.example` (repo root) | **new** — documented compose env/secrets |
| `deploy/README.md` | **new** — fresh-install + upgrade runbook |

Not touched: `deploy/nginx/nginx.conf`, `deploy/nginx/Dockerfile`, `backend/Dockerfile`,
`backend/docker-entrypoint.sh` (the seed it already runs picks up `ensure_schema` via `seed.py`).

---

## 8. Risks and mitigations

- **Migration on a busy table**: `ADD COLUMN ... DEFAULT` on `admin_user` is tiny (a handful of
  staff rows) — effectively instant; no lock concern at this scale.
- **Wrong upload path**: setting `UPLOAD_DIR` explicitly to the mount point removes ambiguity
  between the app default (`uploads`) and the volume mount (`/app/uploads`).
- **Idempotency**: `ensure_schema` guards every change behind an inspector check, so repeated
  container restarts (and fresh DBs) are safe no-ops.
- **Default admin left in place**: the runbook calls out replacing `admin/admin123` with real
  staff accounts and a strong `JWT_SECRET` before going live.
- **Docker availability for verification**: the plan provides a non-docker fallback (§6) so it
  can still be completed if the environment lacks Docker.

---

## 9. Out of scope (recap)

Object storage / signed URLs, Alembic, backups, monitoring, TLS, multi-replica scaling — all
deferred. This plan is strictly: persist uploads, migrate the one new column, wire env, and
document the rollout.
