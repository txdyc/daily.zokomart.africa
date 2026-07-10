# ZokoDaily Plan 5: Docker Compose Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docker compose up -d --build` brings up the complete ZokoDaily system: MySQL 8, the FastAPI backend (with Chromium for crawling), and nginx serving the H5 site at `/`, admin at `/admin/`, and proxying `/api/`.

**Architecture:** Three services on one compose network. MySQL gates backend startup via healthcheck; the backend entrypoint runs the idempotent seed then uvicorn; a multi-stage nginx image builds both frontends from source. Secrets live in a gitignored `.env`; AI credentials stay in the database. This deployment is also the system's first run against real MySQL — Task 3 includes the dialect smoke checks.

**Tech Stack:** Docker Compose, MySQL 8, python:3.12-slim + uv + Playwright Chromium, node:20-alpine build stages, nginx:alpine.

**Spec:** `docs/superpowers/specs/2026-07-10-deployment-design.md`
**Working directory:** repo root (`D:\GHANA\claude\daily.zokomart.africa`) unless stated otherwise. Requires Docker Desktop running locally (the compose file targets the eventual Linux host unchanged).

---

## File structure created by this plan

```
docker-compose.yml
.env.example                 # committed template (.env itself is gitignored)
.dockerignore                # root context (nginx image build)
backend/Dockerfile
backend/.dockerignore
backend/docker-entrypoint.sh
deploy/nginx/Dockerfile
deploy/nginx/nginx.conf
docs/DEPLOY.md
```

---

### Task 1: Commit the application code

The Docker builds must run against committed state. `backend/`, `h5/`, and `admin/` are
currently untracked.

- [ ] **Step 1: Check state and commit**

```bash
git status --short
```

If `backend/`, `h5/`, or `admin/` appear as untracked (`??`), commit them (three commits,
one per component):

```bash
git add backend/ && git commit -m "feat(backend): Plans 1-2 implementation - API, crawler, translation pipeline"
git add h5/ && git commit -m "feat(h5): Plan 3 implementation - ZokoDaily mobile site"
git add admin/ && git commit -m "feat(admin): Plan 4 implementation - management SPA"
git add .gitignore .claude/ && git commit -m "chore: gitignore and project tooling updates"
```

If they are already committed, skip this task.

---

### Task 2: Env template + MySQL service

**Files:**
- Create: `.env.example`, `docker-compose.yml` (mysql service only; backend/nginx added in Tasks 3–4)

- [ ] **Step 1: Create `.env.example`**

```env
MYSQL_ROOT_PASSWORD=change-me
MYSQL_PASSWORD=change-me
JWT_SECRET=change-me-long-random
HTTP_PORT=80
```

- [ ] **Step 2: Create your local `.env`** (gitignored) — copy `.env.example`, set real values.
For local verification any non-trivial values work, e.g. `HTTP_PORT=8088` if 80 is taken.

- [ ] **Step 3: Create `docker-compose.yml`** (mysql only for now)

```yaml
services:
  mysql:
    image: mysql:8
    command: --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: zokodaily
      MYSQL_USER: zokodaily
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    volumes:
      - mysql-data:/var/lib/mysql
    healthcheck:
      test: ["CMD-SHELL", "mysqladmin ping -h localhost -u root -p$$MYSQL_ROOT_PASSWORD"]
      interval: 5s
      timeout: 5s
      retries: 20
    restart: unless-stopped
    # Uncomment to reach MySQL from the host for debugging:
    # ports:
    #   - "3306:3306"

volumes:
  mysql-data:
```

- [ ] **Step 4: Verify MySQL comes up healthy with utf8mb4**

```bash
docker compose up -d mysql
docker compose ps            # wait until mysql shows "healthy"
docker compose exec mysql mysql -u zokodaily -p"$(grep MYSQL_PASSWORD .env | head -1 | cut -d= -f2)" zokodaily \
  -e "SHOW VARIABLES LIKE 'character_set_server'; SELECT 1;"
```

Expected: `character_set_server | utf8mb4` and `1`.

- [ ] **Step 5: Commit**

```bash
git add .env.example docker-compose.yml
git commit -m "feat(deploy): compose skeleton with MySQL 8 (utf8mb4, healthcheck, volume)"
```

---

### Task 3: Backend image + first real-MySQL run

**Files:**
- Create: `backend/Dockerfile`, `backend/.dockerignore`, `backend/docker-entrypoint.sh`
- Modify: `docker-compose.yml` (add backend service)

- [ ] **Step 1: Create `backend/.dockerignore`**

```
.venv
__pycache__
**/__pycache__
*.db
.pytest_cache
tests
.env
```

- [ ] **Step 2: Create `backend/docker-entrypoint.sh`** (LF line endings — critical on a
Windows checkout; if the repo converts to CRLF the container fails with `sh: not found`.
Verify with `file backend/docker-entrypoint.sh` → must not say CRLF; fix via
`git add --renormalize` + a `.gitattributes` line `*.sh text eol=lf` if needed.)

```sh
#!/bin/sh
set -e

echo "Running idempotent seed (creates tables, seeds reference data)..."
i=1
until uv run python -m app.seed; do
  if [ "$i" -ge 5 ]; then
    echo "Seed failed after $i attempts, giving up." >&2
    exit 1
  fi
  echo "Seed attempt $i failed; retrying in 5s..."
  i=$((i + 1))
  sleep 5
done

echo "Starting uvicorn..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- [ ] **Step 3: Create `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
# --no-install-project: app/ is not copied yet; only third-party deps go in this layer
RUN uv sync --frozen --no-dev --no-install-project

# Chromium is required: article fetching (Crawl4AI) and listing-page discovery
# (fetch_text_rendered) both depend on it.
RUN uv run playwright install --with-deps chromium

COPY app ./app
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
```

- [ ] **Step 4: Add the backend service to `docker-compose.yml`** (insert under `services:`)

```yaml
  backend:
    build: ./backend
    environment:
      DATABASE_URL: mysql+pymysql://zokodaily:${MYSQL_PASSWORD}@mysql:3306/zokodaily?charset=utf8mb4
      JWT_SECRET: ${JWT_SECRET}
      SCHEDULER_ENABLED: "true"
    depends_on:
      mysql:
        condition: service_healthy
    # Chromium needs shared-memory headroom; the 64 MB default crashes it.
    shm_size: "1g"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 10s
      timeout: 5s
      retries: 12
      start_period: 30s
    restart: unless-stopped
    # Exactly ONE replica: APScheduler runs in-process; a second replica double-crawls.
```

- [ ] **Step 5: Build and start** (the Playwright layer downloads ~150 MB — first build is slow)

```bash
docker compose up -d --build backend
docker compose logs -f backend   # until "Seed complete." and "Uvicorn running"
docker compose ps                # backend healthy
```

- [ ] **Step 6: First real-MySQL smoke checks** (this is the system's first non-SQLite run)

```bash
PW=$(grep '^MYSQL_PASSWORD' .env | cut -d= -f2)
# 1. Seeded reference data with emoji + Chinese survived utf8mb4:
docker compose exec mysql mysql -u zokodaily -p"$PW" zokodaily \
  -e "SELECT code, flag_emoji, name_zh FROM country; SELECT COUNT(*) FROM site;"
# Expected: 4 rows with intact 🇳🇬/🇬🇭/🇸🇳/🇨🇮 and 尼日利亚/加纳/... ; site count 10.

# 2. API round-trip incl. JSON columns — login, then check articles endpoint shape:
docker compose exec backend curl -s -X POST http://localhost:8000/api/admin/auth/login \
  -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}'
# Expected: access_token JSON.

# 3. Seed idempotency across restarts:
docker compose restart backend && sleep 20
docker compose exec mysql mysql -u zokodaily -p"$PW" zokodaily -e "SELECT COUNT(*) FROM country;"
# Expected: still 4.
```

If any dialect error surfaces (column length, JSON, FK), fix it in `backend/app/models/`
as part of this task and note it in the commit message.

- [ ] **Step 7: Commit**

```bash
git add backend/Dockerfile backend/.dockerignore backend/docker-entrypoint.sh docker-compose.yml
git commit -m "feat(deploy): backend image with Chromium, seed entrypoint, MySQL wiring"
```

---

### Task 4: nginx image serving both frontends

**Files:**
- Create: `.dockerignore` (repo root), `deploy/nginx/Dockerfile`, `deploy/nginx/nginx.conf`
- Modify: `docker-compose.yml` (add nginx service)

- [ ] **Step 1: Create root `.dockerignore`** (the nginx build context is the repo root;
without this, host `node_modules` from Windows would be copied over the Linux installs)

```
**/node_modules
**/dist
**/.venv
**/__pycache__
*.db
.git
docs
backend/tests
.env
```

- [ ] **Step 2: Create `deploy/nginx/Dockerfile`**

```dockerfile
FROM node:20-alpine AS h5-build
WORKDIR /build
COPY h5/package*.json ./
RUN npm ci
COPY h5/ ./
RUN npm run build

FROM node:20-alpine AS admin-build
WORKDIR /build
COPY admin/package*.json ./
RUN npm ci
COPY admin/ ./
RUN npm run build

FROM nginx:alpine
COPY deploy/nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=h5-build /build/dist /usr/share/nginx/html
COPY --from=admin-build /build/dist /usr/share/nginx/html/admin
```

- [ ] **Step 3: Create `deploy/nginx/nginx.conf`**

```nginx
server {
    listen 80;
    server_name _;

    gzip on;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;
    client_max_body_size 10m;

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location /admin/assets/ {
        root /usr/share/nginx/html;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /admin/ {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /admin/index.html;
        add_header Cache-Control "no-cache";
    }

    location /assets/ {
        root /usr/share/nginx/html;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache";
    }
}
```

- [ ] **Step 4: Add the nginx service to `docker-compose.yml`** (insert under `services:`)

```yaml
  nginx:
    build:
      context: .
      dockerfile: deploy/nginx/Dockerfile
    ports:
      - "${HTTP_PORT:-80}:80"
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped
```

- [ ] **Step 5: Build and verify all routes** (`$HP` = your `HTTP_PORT`)

```bash
docker compose up -d --build nginx
HP=$(grep '^HTTP_PORT' .env | cut -d= -f2)

curl -s http://localhost:$HP/api/health                     # {"status":"ok"} via proxy
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:$HP/            # 200, H5 index
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:$HP/article/1   # 200 (SPA fallback)
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:$HP/admin/      # 200, admin index
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:$HP/admin/articles  # 200 (SPA fallback)
curl -s http://localhost:$HP/ | grep -o "<title>[^<]*"      # <title>ZokoDaily
curl -s http://localhost:$HP/admin/ | grep -o "<title>[^<]*" # <title>ZokoDaily 管理后台
```

Expected: exactly as annotated. If `/admin/` serves the H5 index instead, the admin build's
`base` isn't `/admin/` — check `admin/vite.config.ts`.

- [ ] **Step 6: Commit**

```bash
git add .dockerignore deploy/ docker-compose.yml
git commit -m "feat(deploy): nginx image building and serving H5 + admin, proxying API"
```

---

### Task 5: Deploy runbook

**Files:**
- Create: `docs/DEPLOY.md`

- [ ] **Step 1: Create `docs/DEPLOY.md`**

````markdown
# ZokoDaily 部署手册 (Docker Compose)

Target: a Linux host with Docker + Compose. The stack is HTTP-only on `${HTTP_PORT}`;
terminate TLS for `daily.zokomart.africa` at a host-level reverse proxy (nginx/caddy +
certbot) pointing at this port.

## First deploy

```bash
git clone <repo-url> zokodaily && cd zokodaily
cp .env.example .env        # then edit: strong MYSQL_* passwords, long random JWT_SECRET
docker compose up -d --build
docker compose ps           # wait until all three services are healthy
```

Then, in order:

1. Open `http://<host>:${HTTP_PORT}/admin/`, log in `admin` / `admin123`.
2. **Change the admin password immediately:**

   ```bash
   docker compose exec backend uv run python -c "
   from app.db import SessionLocal
   from app.models import AdminUser
   from app.security import hash_password
   with SessionLocal() as db:
       u = db.query(AdminUser).filter_by(username='admin').one()
       u.password_hash = hash_password('YOUR-NEW-PASSWORD')
       db.commit()
   print('password updated')"
   ```

3. 系统设置: set the AI base URL / API key / model, click 测试翻译 — must show ok.
4. 国家与站点: click 抓取 on **every** site once; watch 抓取与翻译 for results.
   Site reachability differs by network — fix any failing feed/listing URL in the site
   form (known suspects from dev verification: Punch feed, Seneweb listing URL).
5. Confirm translated articles appear on `http://<host>:${HTTP_PORT}/`.

## Update to a new version

```bash
git pull
docker compose up -d --build     # rebuilds changed images; seed re-runs harmlessly
```

## Everyday operations

```bash
docker compose logs -f backend                    # pipeline + API logs
docker compose exec backend uv run python -m app.seed   # re-run seed manually
docker compose exec mysql mysql -u zokodaily -p zokodaily # DB shell
```

## Backup (manual, run before upgrades)

```bash
docker compose exec mysql sh -c 'mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" zokodaily' \
  > backup-$(date +%Y%m%d).sql
```

## Constraints

- Run exactly **one** backend container: the crawl/translation scheduler lives in-process;
  two replicas would crawl and translate everything twice.
- MySQL data lives in the `mysql-data` volume; `docker compose down` keeps it,
  `docker compose down -v` destroys it.
````

- [ ] **Step 2: Commit**

```bash
git add docs/DEPLOY.md
git commit -m "docs: deployment runbook"
```

---

### Task 6: Full-stack live verification

**Files:** none — end-to-end walkthrough of the composed stack.

- [ ] **Step 1: Cold start from nothing**

```bash
docker compose down
docker compose up -d --build
docker compose ps    # all three healthy within ~1 min
```

- [ ] **Step 2: Crawl inside the container** (proves Chromium works in-image)

```bash
HP=$(grep '^HTTP_PORT' .env | cut -d= -f2)
TOKEN=$(curl -s -X POST http://localhost:$HP/api/admin/auth/login \
  -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
# Channels TV is the reliably-reachable seed site; find its id then trigger:
curl -s http://localhost:$HP/api/admin/sites -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:$HP/api/admin/sites/<channels_tv_id>/crawl -H "Authorization: Bearer $TOKEN"
# Poll until success:
curl -s http://localhost:$HP/api/admin/crawl-runs -H "Authorization: Bearer $TOKEN"
```

Expected: run reaches `success` with `articles_new > 0` and a correct `articles_found`.

- [ ] **Step 3: Translation** — set a real AI key via `/admin/` Settings (or the API), run
test-translation (`ok:true`), then wait ≤5 min for the in-container scheduler's sweep
(it runs automatically — `SCHEDULER_ENABLED=true` here, unlike dev). Confirm articles
flip to `published`.

- [ ] **Step 4: The H5 site shows real news** — open `http://localhost:$HP/` in a browser:
banner + cards with crawled articles, detail page bilingual toggle works against the
translated content.

- [ ] **Step 5: Persistence across restart**

```bash
docker compose down && docker compose up -d
# after healthy: article count unchanged, admin password/AI key still set
```

- [ ] **Step 6: Record results** — if any step fails, fix within this task and commit the
fix; when all pass, the system is deployable. Final commit if anything changed:

```bash
git add -A && git commit -m "fix(deploy): issues found during full-stack verification"
```
