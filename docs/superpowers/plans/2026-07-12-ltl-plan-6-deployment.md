# LTL Plan 6: Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the logistics module deploy cleanly in the existing docker-compose stack: an idempotent `admin_user.role` migration, a persistent uploads volume, documented env/secrets, and a rollout runbook — verified with a real `docker compose` smoke.

**Architecture:** The stack is unchanged in shape (mysql + single backend + nginx that builds both SPAs). Logistics tables auto-create via `create_all` and config defaults come from the seed, so this plan adds only: `app/migrate.py::ensure_schema` (run from the seed the entrypoint already invokes), a `uploads-data` docker volume mounted at the backend's `UPLOAD_DIR`, an enriched repo-root `.env.example`, and `deploy/README.md`.

**Tech Stack:** Docker Compose, MySQL 8, FastAPI (SQLAlchemy 2.0), nginx, pytest. No new dependencies.

**Testing note:** the migration gets real pytest TDD (Task 1). Config/compose/doc tasks are verified by `docker compose config` (syntax) and inspection; the whole thing is proven by the live `docker compose` smoke in Task 6, which has a documented non-docker fallback if Docker isn't available in the environment.

**Plan sequence:** LTL Plans 1–5 (done) → **LTL Plan 6 (this, final)**.

**Working directory:** repo root `D:\GHANA\claude\daily.zokomart.africa` unless a command says `backend/`.
**Spec:** `docs/superpowers/specs/2026-07-12-ltl-plan-6-deployment-design.md`.

**Verified current state (do not re-derive):**
- `backend/docker-entrypoint.sh` runs `uv run python -m app.seed` (with a 5-attempt retry) then uvicorn.
- `backend/app/seed.py` `__main__` does: `import app.models` → `Base.metadata.create_all(engine)` → `seed_all(session)` → `print("Seed complete.")`. `CONFIG_DEFAULTS` already seeds `lg_sms_provider`, `lg_sms_api_key`, `lg_sms_sender_id`, `lg_commission_rate`, `lg_payment_instructions`.
- `docker-compose.yml` has services `mysql` (volume `mysql-data`), `backend` (`build ./backend`, env `DATABASE_URL`/`JWT_SECRET`/`SCHEDULER_ENABLED`, `shm_size: 1g`, healthcheck), `nginx` (builds h5+admin, ports `${HTTP_PORT:-80}:80`); top-level `volumes: mysql-data`.
- `backend/app/config.py` `Settings.upload_dir` defaults to `"uploads"`; `backend/.env.example` lists `UPLOAD_DIR=uploads` (kept for local non-docker runs).
- Repo-root `.env.example` exists with `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD`, `JWT_SECRET`, `HTTP_PORT`.
- `deploy/nginx/nginx.conf` proxies `/api/` → backend and has `client_max_body_size 10m` (≥ the 8 MB upload cap). **No nginx change in this plan.**

---

## File structure created/modified by this plan

```
backend/app/migrate.py         # NEW: ensure_schema(engine) idempotent additive migration
backend/app/seed.py            # MODIFIED: call ensure_schema between create_all and seed_all
backend/tests/test_migrate.py  # NEW: migration tests
docker-compose.yml             # MODIFIED: uploads-data volume + mount + UPLOAD_DIR env
.env.example                   # MODIFIED: comments + JWT_SECRET/secret guidance
deploy/README.md               # NEW: fresh-install + upgrade runbook
```

---

### Task 1: Idempotent schema migration (`ensure_schema`)

**Files:**
- Create: `backend/app/migrate.py`, `backend/tests/test_migrate.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_migrate.py`:

```python
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app.migrate import ensure_schema


def _engine_without_role():
    """A SQLite engine (single shared connection) whose admin_user lacks `role`,
    emulating a news-only production MySQL before the Plan 5 column was added."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE admin_user "
                "(id INTEGER PRIMARY KEY, username VARCHAR(50), password_hash VARCHAR(100))"
            )
        )
    return engine


def test_adds_missing_role_column():
    engine = _engine_without_role()
    applied = ensure_schema(engine)
    assert applied == ["admin_user.role"]
    cols = {c["name"] for c in inspect(engine).get_columns("admin_user")}
    assert "role" in cols


def test_role_defaults_to_admin():
    engine = _engine_without_role()
    ensure_schema(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO admin_user (username, password_hash) VALUES ('u', 'h')"))
        role = conn.execute(text("SELECT role FROM admin_user WHERE username='u'")).scalar()
    assert role == "admin"


def test_idempotent_when_column_present():
    engine = _engine_without_role()
    ensure_schema(engine)          # first run adds it
    assert ensure_schema(engine) == []  # second run is a no-op


def test_noop_when_table_absent():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    assert ensure_schema(engine) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `uv run pytest tests/test_migrate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.migrate'`

- [ ] **Step 3: Implement**

Create `backend/app/migrate.py`:

```python
"""Idempotent additive migrations that `create_all` cannot perform.

`Base.metadata.create_all` creates missing tables but never alters existing ones, so a
column added to a model after its table already exists in production (e.g. admin_user.role,
added in LTL Plan 5) must be applied here. Run from the seed after create_all. Each change is
guarded by an inspector check, so fresh databases and repeated runs are safe no-ops.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# (table, column, DDL) — additive columns only. Add future one-liners here.
_ADDITIVE_COLUMNS: list[tuple[str, str, str]] = [
    (
        "admin_user",
        "role",
        "ALTER TABLE admin_user ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'admin'",
    ),
]


def ensure_schema(engine: Engine) -> list[str]:
    """Apply any missing additive columns. Returns the list of `table.column` changes made."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    applied: list[str] = []
    with engine.begin() as conn:
        for table, column, ddl in _ADDITIVE_COLUMNS:
            if table not in tables:
                continue  # create_all will build it fresh, already including the column
            columns = {c["name"] for c in inspector.get_columns(table)}
            if column in columns:
                continue
            conn.execute(text(ddl))
            applied.append(f"{table}.{column}")
    return applied
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_migrate.py -v` → 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/migrate.py backend/tests/test_migrate.py
git commit -m "feat(backend): idempotent ensure_schema migration for admin_user.role"
```

---

### Task 2: Wire `ensure_schema` into the seed

**Files:**
- Modify: `backend/app/seed.py`

- [ ] **Step 1: Update the `__main__` block**

Replace the `if __name__ == "__main__":` block at the bottom of `backend/app/seed.py` with:

```python
if __name__ == "__main__":
    import app.models  # noqa: F401

    from app.db import Base, SessionLocal, engine
    from app.migrate import ensure_schema

    Base.metadata.create_all(engine)
    applied = ensure_schema(engine)
    if applied:
        print(f"Applied schema migrations: {applied}")
    with SessionLocal() as session:
        seed_all(session)
    print("Seed complete.")
```

- [ ] **Step 2: Verify the seed still runs against a fresh SQLite DB**

Run (from `backend/`):
```bash
rm -f verify.db
DATABASE_URL="sqlite:///./verify.db" uv run python -m app.seed
rm -f verify.db
```
Expected: prints `Seed complete.` with no `Applied schema migrations:` line (fresh DB already
has `role` from `create_all`), exit 0.

- [ ] **Step 3: Verify the full backend suite still passes**

Run: `uv run pytest` → all pass (Plan-5 count 178 + 4 new migrate tests = 182).

- [ ] **Step 4: Commit**

```bash
git add backend/app/seed.py
git commit -m "feat(backend): run ensure_schema during seed/startup"
```

---

### Task 3: Persistent uploads volume in docker-compose

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add the `UPLOAD_DIR` env and volume mount to the backend service**

In `docker-compose.yml`, in the `backend:` service, extend the `environment:` map to include
`UPLOAD_DIR` and add a `volumes:` list. The `environment` block becomes:

```yaml
    environment:
      DATABASE_URL: mysql+pymysql://zokodaily:${MYSQL_PASSWORD}@mysql:3306/zokodaily?charset=utf8mb4
      JWT_SECRET: ${JWT_SECRET}
      SCHEDULER_ENABLED: "true"
      UPLOAD_DIR: /app/uploads
    volumes:
      - uploads-data:/app/uploads
```

(Insert the `volumes:` block at the same indentation as `environment:`, e.g. directly after the
`environment:` map and before `depends_on:`.)

- [ ] **Step 2: Declare the named volume**

At the bottom of `docker-compose.yml`, extend the top-level `volumes:` section:

```yaml
volumes:
  mysql-data:
  uploads-data:
```

- [ ] **Step 3: Validate compose syntax**

Run: `docker compose config >/dev/null && echo OK`
Expected: `OK` (compose file parses; the backend shows `UPLOAD_DIR=/app/uploads`, a
`uploads-data` mount, and the top-level `uploads-data` volume).

If Docker is unavailable, visually confirm the three edits (env line, mount, volume decl) are
present and correctly indented.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(deploy): persist uploads in a named volume"
```

---

### Task 4: Enrich the repo-root `.env.example`

**Files:**
- Modify: `.env.example` (repo root)

- [ ] **Step 1: Replace the repo-root `.env.example` with a documented version**

Overwrite `.env.example` (repo root, not `backend/.env.example`) with:

```dotenv
# ── ZokoDaily docker-compose environment ──────────────────────────────────────
# Copy to .env (docker compose auto-loads it) and fill in real values.

# MySQL credentials (used by the mysql and backend services).
MYSQL_ROOT_PASSWORD=change-me
MYSQL_PASSWORD=change-me

# Secret for signing admin and H5 (logistics) JWTs.
# MUST be a random string of at least 32 characters — shorter keys weaken HS256
# and the backend logs an InsecureKeyLengthWarning. Generate e.g. with:
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
JWT_SECRET=change-me-long-random-at-least-32-chars

# Public HTTP port exposed by nginx.
HTTP_PORT=80

# Note: logistics runtime settings are NOT env vars. The SMS provider/key/sender,
# commission rate, and payment instructions are stored in the database (seeded with
# safe defaults: mock SMS, 8% commission) and configured after deploy via the admin
# UI (物流设置) or PUT /api/admin/lg/config.
```

- [ ] **Step 2: Confirm the example is not the live `.env`**

Run: `git status --short .env` → expect no output (the real `.env` is gitignored/untracked and
untouched; only `.env.example` changed).

- [ ] **Step 3: Commit**

```bash
git add .env.example
git commit -m "docs(deploy): document compose env and JWT secret guidance"
```

---

### Task 5: Deployment runbook

**Files:**
- Create: `deploy/README.md`

- [ ] **Step 1: Write the runbook**

Create `deploy/README.md`:

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add deploy/README.md
git commit -m "docs(deploy): fresh-install and upgrade runbook"
```

---

### Task 6: Live docker-compose deployment smoke

**Files:** none (verification only)

This task runs the real stack. If Docker is unavailable in the environment, do the **Fallback**
at the end instead and note it in the PR.

- [ ] **Step 1: Build and start a throwaway stack**

**Do NOT touch the repo-root `.env`** — it holds the user's real secrets. Use an isolated env
file and pass it to every compose command with `--env-file .env.smoke`.

```bash
printf 'MYSQL_ROOT_PASSWORD=rootpw\nMYSQL_PASSWORD=zokopw\nJWT_SECRET=%s\nHTTP_PORT=8081\n' \
  "$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" > .env.smoke
docker compose --env-file .env.smoke build
docker compose --env-file .env.smoke up -d
```

Wait for the backend healthcheck: `docker compose --env-file .env.smoke ps` until `backend`
shows `healthy` (up to ~90s; Chromium install makes the first build slow).

- [ ] **Step 2: Health + role column (proves ensure_schema ran on MySQL)**

```bash
curl -s http://localhost:8081/api/health
TOKEN=$(curl -s http://localhost:8081/api/admin/auth/login -H 'content-type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | sed -E 's/.*"access_token":"([^"]+)".*/\1/')
curl -s http://localhost:8081/api/admin/auth/me -H "Authorization: Bearer $TOKEN"
```
Expected: health `{"status":"ok"}`; `/auth/me` → `{"username":"admin","role":"admin"}` (the
`role` field proves the column exists in MySQL).

- [ ] **Step 3: A logistics admin endpoint responds**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8081/api/admin/lg/stats/overview \
  -H "Authorization: Bearer $TOKEN"
```
Expected: `200`.

- [ ] **Step 4: Upload persists across a backend restart**

```bash
# create an H5 user + upload a file
curl -s http://localhost:8081/api/lg/auth/request-otp -H 'content-type: application/json' -d '{"phone":"0241234567"}' >/dev/null
CODE=$(docker compose --env-file .env.smoke exec -T mysql mysql -uzokodaily -pzokopw zokodaily -N -e \
  "SELECT code FROM lg_otp_code WHERE phone='+233241234567' AND used=0 ORDER BY id DESC LIMIT 1")
UTOKEN=$(curl -s http://localhost:8081/api/lg/auth/login -H 'content-type: application/json' \
  -d "{\"phone\":\"0241234567\",\"code\":\"$CODE\"}" | sed -E 's/.*"access_token":"([^"]+)".*/\1/')
printf '\x89PNG\r\n\x1a\n0000000000' > /tmp/card.png
ATT=$(curl -s http://localhost:8081/api/lg/uploads -H "Authorization: Bearer $UTOKEN" \
  -F "file=@/tmp/card.png;type=image/png" | sed -E 's/.*"id":"([^"]+)".*/\1/')
echo "attachment: $ATT"
docker compose --env-file .env.smoke restart backend
sleep 20
curl -s -o /dev/null -w "after-restart: %{http_code}\n" \
  "http://localhost:8081/api/lg/uploads/$ATT" -H "Authorization: Bearer $UTOKEN"
```
Expected: `after-restart: 200` — the file survived container recreation via the `uploads-data`
volume.

- [ ] **Step 5: Upgrade rehearsal — ensure_schema re-adds a dropped column**

```bash
docker compose --env-file .env.smoke exec -T mysql mysql -uzokodaily -pzokopw zokodaily -e \
  "ALTER TABLE admin_user DROP COLUMN role"
docker compose --env-file .env.smoke restart backend
sleep 20
TOKEN=$(curl -s http://localhost:8081/api/admin/auth/login -H 'content-type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | sed -E 's/.*"access_token":"([^"]+)".*/\1/')
curl -s http://localhost:8081/api/admin/auth/me -H "Authorization: Bearer $TOKEN"
```
Expected: `/auth/me` again returns `"role":"admin"` — `ensure_schema` re-added the column on
startup, proving the upgrade path.

- [ ] **Step 6: Both SPAs are served**

```bash
curl -s -o /dev/null -w "h5: %{http_code}\n" http://localhost:8081/
curl -s -o /dev/null -w "admin: %{http_code}\n" http://localhost:8081/admin/
```
Expected: both `200`.

- [ ] **Step 7: Tear down**

```bash
docker compose --env-file .env.smoke down -v
rm -f .env.smoke /tmp/card.png
```

(The repo-root `.env` was never touched.)

- [ ] **Fallback (Docker unavailable):**

1. `docker compose config >/dev/null` if any docker exists; otherwise visually verify
   `docker-compose.yml` has the `UPLOAD_DIR` env, the `uploads-data:/app/uploads` mount, and the
   top-level `uploads-data:` volume.
2. Prove the migration against a real-ish flow with SQLite (from `backend/`):
   ```bash
   rm -f up.db
   DATABASE_URL="sqlite:///./up.db" uv run python -c "
   from sqlalchemy import create_engine, text, inspect
   e = create_engine('sqlite:///./up.db')
   with e.begin() as c:
       c.execute(text('CREATE TABLE admin_user (id INTEGER PRIMARY KEY, username VARCHAR(50), password_hash VARCHAR(100))'))
   from app.migrate import ensure_schema
   print('applied:', ensure_schema(e))
   print('cols:', [col['name'] for col in inspect(e).get_columns('admin_user')])
   "
   rm -f up.db
   ```
   Expected: `applied: ['admin_user.role']` then a column list containing `role`.
3. Record in the PR that the live docker smoke was skipped for lack of Docker and the fallback
   was used.

- [ ] **Step 8: Record the result**

No source changes in this task. Note the smoke outcome (or fallback) in the PR description.

---

## Self-review notes for the executor

- **`ensure_schema` runs inside the seed**, which the entrypoint already invokes with a retry
  loop — no `docker-entrypoint.sh` change is needed.
- **Order matters:** `create_all` (tables) → `ensure_schema` (columns on pre-existing tables) →
  `seed_all` (data). Keep it.
- **`UPLOAD_DIR` is set to the exact mount point** (`/app/uploads`) to remove ambiguity with the
  app default (`uploads`).
- **No nginx/Dockerfile change:** uploads are served by the backend via `/api/lg/uploads` and
  already proxied; `client_max_body_size 10m` ≥ the 8 MB cap; the nginx image rebuilds both SPAs
  from source, so the logistics UI ships on the next build.

## What this plan completes

This is the final LTL plan. After it: backend (1–2), H5 shipper (3), H5 driver (4), admin (5),
and deployment (6) are all done — the logistics module is fully built and deployable.

## Deferred (unchanged from the spec)

Object storage / signed URLs for uploads, Alembic, backups + monitoring, TLS, and multi-replica
scaling remain out of scope (V2+).
