# ZokoDaily Plan 1: Backend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Working FastAPI backend with the full data model, seed data (4 countries, 10 Tier-1 sites, admin user), JWT admin auth, the public API consumed by the H5 site, and admin CRUD APIs.

**Architecture:** Single FastAPI app (sync SQLAlchemy 2.0, MySQL in prod / SQLite in tests). Routers split into `/api/public/*` (no auth) and `/api/admin/*` (JWT bearer). Tables created via `Base.metadata.create_all` at startup (no Alembic in V1); a seed script populates reference data. Crawler/translation/scheduler are **Plan 2** — this plan only creates the tables and statuses they will use.

**Tech Stack:** Python 3.12 + uv, FastAPI, SQLAlchemy 2.0, Pydantic v2 + pydantic-settings, PyMySQL, bcrypt, PyJWT, pytest + httpx TestClient.

**Plan sequence:** Plan 1 (this) → Plan 2 crawler+translation pipeline → Plan 3 H5 frontend → Plan 4 admin frontend → Plan 5 Docker deployment.

**Working directory:** all commands run from `backend/` unless stated otherwise. Spec: `docs/superpowers/specs/2026-07-10-zokodaily-news-aggregation-design.md`.

---

## File structure created by this plan

```
backend/
├── pyproject.toml
├── .env.example
├── app/
│   ├── __init__.py
│   ├── config.py            # pydantic-settings Settings
│   ├── db.py                # engine, SessionLocal, Base, get_db
│   ├── main.py              # FastAPI app, router wiring, startup create_all
│   ├── security.py          # bcrypt + JWT + get_current_admin dependency
│   ├── schemas.py           # all Pydantic request/response schemas
│   ├── seed.py              # idempotent seed: countries, sites, admin, config
│   ├── models/
│   │   ├── __init__.py      # re-exports every model
│   │   ├── country.py
│   │   ├── site.py
│   │   ├── article.py
│   │   ├── crawl_run.py
│   │   ├── app_config.py
│   │   └── admin_user.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── config_service.py  # app_config get/set + API-key masking
│   └── api/
│       ├── __init__.py
│       ├── public.py        # /api/public/articles*
│       └── admin/
│           ├── __init__.py
│           ├── auth.py      # login, me
│           ├── countries.py
│           ├── sites.py
│           ├── articles.py
│           └── config.py
└── tests/
    ├── conftest.py
    ├── test_health.py
    ├── test_models.py
    ├── test_seed.py
    ├── test_auth.py
    ├── test_public_api.py
    ├── test_admin_countries_sites.py
    ├── test_admin_articles.py
    └── test_admin_config.py
```

---

### Task 1: Project scaffold + health endpoint

**Files:**
- Create: `.gitignore` (repo root)
- Create: `backend/pyproject.toml`, `backend/.env.example`
- Create: `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/main.py`
- Test: `backend/tests/conftest.py`, `backend/tests/test_health.py`

- [ ] **Step 1: Create repo-root `.gitignore`**

```gitignore
__pycache__/
*.pyc
.venv/
.env
.pytest_cache/
node_modules/
dist/
*.log
```

- [ ] **Step 2: Create `backend/pyproject.toml`**

```toml
[project]
name = "zokodaily-backend"
version = "0.1.0"
description = "ZokoDaily West Africa news aggregation backend"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy>=2.0",
    "pymysql>=1.1",
    "cryptography>=43",
    "pydantic-settings>=2.4",
    "bcrypt>=4.2",
    "pyjwt>=2.9",
]

[dependency-groups]
dev = [
    "pytest>=8",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Run: `cd backend && uv sync`
Expected: creates `.venv` and `uv.lock`, resolves all packages.

- [ ] **Step 3: Create `backend/.env.example`**

```env
DATABASE_URL=mysql+pymysql://root:root@localhost:3306/zokodaily?charset=utf8mb4
JWT_SECRET=change-me-in-production
JWT_EXPIRE_MINUTES=1440
```

- [ ] **Step 4: Create `backend/app/__init__.py`** (empty file)

- [ ] **Step 5: Create `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "mysql+pymysql://root:root@localhost:3306/zokodaily?charset=utf8mb4"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 1440


settings = Settings()
```

- [ ] **Step 6: Create `backend/app/db.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 7: Write the failing test — `backend/tests/conftest.py` and `backend/tests/test_health.py`**

`backend/tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import app.models  # noqa: F401  (register all tables on Base)

    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestingSession()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

Note: `import app.models` will fail until Task 2 creates the package. For this task only, create `backend/app/models/__init__.py` as an empty file now — Task 2 fills it in.

`backend/tests/test_health.py`:

```python
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 8: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_health.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 9: Create `backend/app/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="ZokoDaily API")


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 10: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_health.py -v`
Expected: 1 passed

- [ ] **Step 11: Commit**

```bash
git add .gitignore backend/
git commit -m "feat(backend): scaffold FastAPI project with health endpoint"
```

---

### Task 2: Data models

**Files:**
- Create: `backend/app/models/country.py`, `site.py`, `article.py`, `crawl_run.py`, `app_config.py`, `admin_user.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test — `backend/tests/test_models.py`**

```python
from datetime import datetime, timezone

from app.models import AdminUser, AppConfig, Article, Country, CrawlRun, Site


def test_article_roundtrip_with_relationships(db_session):
    country = Country(code="GH", name_en="Ghana", name_zh="加纳", flag_emoji="🇬🇭")
    site = Site(
        country=country,
        name="MyJoyOnline",
        base_url="https://www.myjoyonline.com",
        language="en",
        discovery_method="rss",
        feed_url="https://www.myjoyonline.com/feed/",
        tier=1,
    )
    article = Article(
        site=site,
        country=country,
        source_url="https://www.myjoyonline.com/some-story/",
        source_language="en",
        title="Hello Ghana",
        paragraphs=["First paragraph.", "Second paragraph."],
        published_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )
    db_session.add(article)
    db_session.commit()

    got = db_session.get(Article, article.id)
    assert got.paragraphs == ["First paragraph.", "Second paragraph."]
    assert got.paragraphs_zh is None
    assert got.status == "pending_translation"
    assert got.is_banner is False
    assert got.site.country.code == "GH"


def test_other_tables_roundtrip(db_session):
    country = Country(code="NG", name_en="Nigeria", name_zh="尼日利亚", flag_emoji="🇳🇬")
    site = Site(
        country=country,
        name="Punch",
        base_url="https://punchng.com",
        language="en",
        discovery_method="rss",
        feed_url="https://punchng.com/feed/",
    )
    run = CrawlRun(site=site, status="running")
    user = AdminUser(username="admin", password_hash="x")
    cfg = AppConfig(key="ai_model", value="gpt-4o-mini")
    db_session.add_all([run, user, cfg])
    db_session.commit()

    assert db_session.get(CrawlRun, run.id).site.name == "Punch"
    assert db_session.get(AppConfig, "ai_model").value == "gpt-4o-mini"
    assert db_session.get(AdminUser, user.id).username == "admin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'AdminUser' from 'app.models'`

- [ ] **Step 3: Create the model files**

`backend/app/models/country.py`:

```python
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Country(Base):
    __tablename__ = "country"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(2), unique=True)  # ISO 3166-1 alpha-2
    name_en: Mapped[str] = mapped_column(String(100))
    name_zh: Mapped[str] = mapped_column(String(100))
    flag_emoji: Mapped[str] = mapped_column(String(8))
    tier: Mapped[int] = mapped_column(Integer, default=1)  # 1 / 2 / 3 (low-frequency)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
```

`backend/app/models/site.py`:

```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Site(Base):
    __tablename__ = "site"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("country.id"))
    name: Mapped[str] = mapped_column(String(100))
    base_url: Mapped[str] = mapped_column(String(500))
    language: Mapped[str] = mapped_column(String(2))  # "en" | "fr"
    discovery_method: Mapped[str] = mapped_column(String(10))  # "rss" | "listing"
    feed_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    listing_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    listing_selector: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # optional per-site extraction overrides (CSS selectors)
    title_selector: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body_selector: Mapped[str | None] = mapped_column(String(200), nullable=True)
    image_selector: Mapped[str | None] = mapped_column(String(200), nullable=True)
    date_selector: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tier: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_crawl_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_crawl_status: Mapped[str | None] = mapped_column(String(500), nullable=True)

    country: Mapped["Country"] = relationship()  # noqa: F821
```

`backend/app/models/article.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

STATUS_PENDING_TRANSLATION = "pending_translation"
STATUS_PUBLISHED = "published"
STATUS_TRANSLATION_FAILED = "translation_failed"
STATUS_HIDDEN = "hidden"
ARTICLE_STATUSES = (
    STATUS_PENDING_TRANSLATION,
    STATUS_PUBLISHED,
    STATUS_TRANSLATION_FAILED,
    STATUS_HIDDEN,
)

CATEGORIES = (
    "politics",
    "business",
    "sports",
    "entertainment",
    "society",
    "technology",
    "health",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Article(Base):
    __tablename__ = "article"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"))
    country_id: Mapped[int] = mapped_column(ForeignKey("country.id"))
    source_url: Mapped[str] = mapped_column(String(700), unique=True)
    source_language: Mapped[str] = mapped_column(String(2))  # "en" | "fr"
    title: Mapped[str] = mapped_column(String(500))
    title_zh: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    main_image_url: Mapped[str | None] = mapped_column(String(700), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paragraphs: Mapped[list] = mapped_column(JSON)  # ordered source-language paragraphs
    paragraphs_zh: Mapped[list | None] = mapped_column(JSON, nullable=True)  # aligned ZH
    status: Mapped[str] = mapped_column(String(30), default=STATUS_PENDING_TRANSLATION)
    translation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_banner: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    site: Mapped["Site"] = relationship()  # noqa: F821
    country: Mapped["Country"] = relationship()  # noqa: F821
```

`backend/app/models/crawl_run.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class CrawlRun(Base):
    __tablename__ = "crawl_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"))
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|success|failed
    articles_found: Mapped[int] = mapped_column(Integer, default=0)
    articles_new: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped["Site"] = relationship()  # noqa: F821
```

`backend/app/models/app_config.py`:

```python
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
```

`backend/app/models/admin_user.py`:

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AdminUser(Base):
    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
```

`backend/app/models/__init__.py`:

```python
from app.models.admin_user import AdminUser
from app.models.app_config import AppConfig
from app.models.article import (
    ARTICLE_STATUSES,
    CATEGORIES,
    STATUS_HIDDEN,
    STATUS_PENDING_TRANSLATION,
    STATUS_PUBLISHED,
    STATUS_TRANSLATION_FAILED,
    Article,
)
from app.models.country import Country
from app.models.crawl_run import CrawlRun
from app.models.site import Site

__all__ = [
    "AdminUser",
    "AppConfig",
    "Article",
    "Country",
    "CrawlRun",
    "Site",
    "ARTICLE_STATUSES",
    "CATEGORIES",
    "STATUS_HIDDEN",
    "STATUS_PENDING_TRANSLATION",
    "STATUS_PUBLISHED",
    "STATUS_TRANSLATION_FAILED",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/ -v`
Expected: all tests pass (health + 2 model tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/ backend/tests/test_models.py
git commit -m "feat(backend): add SQLAlchemy models for all six tables"
```

---

### Task 3: Seed script (countries, Tier-1 sites, admin user, AI config)

**Files:**
- Create: `backend/app/seed.py`
- Test: `backend/tests/test_seed.py`

Feed/listing URLs below are best-known values; Plan 2 includes a live verification task, and every value is editable in admin.

- [ ] **Step 1: Write the failing test — `backend/tests/test_seed.py`**

```python
from app.models import AdminUser, AppConfig, Country, Site
from app.seed import seed_all
from app.security import verify_password


def test_seed_creates_reference_data(db_session):
    seed_all(db_session)

    assert db_session.query(Country).count() == 4
    assert db_session.query(Site).count() == 10
    ghana = db_session.query(Country).filter_by(code="GH").one()
    assert ghana.name_zh == "加纳"
    assert db_session.query(Site).filter_by(country_id=ghana.id).count() == 3

    admin = db_session.query(AdminUser).filter_by(username="admin").one()
    assert verify_password("admin123", admin.password_hash)

    assert db_session.get(AppConfig, "ai_base_url").value == "https://api.openai.com/v1"
    assert db_session.get(AppConfig, "ai_api_key").value == ""
    assert db_session.get(AppConfig, "ai_model").value == "gpt-4o-mini"


def test_seed_is_idempotent(db_session):
    seed_all(db_session)
    seed_all(db_session)
    assert db_session.query(Country).count() == 4
    assert db_session.query(Site).count() == 10
    assert db_session.query(AdminUser).count() == 1
```

Note: this test imports `app.security.verify_password`, which is written in Task 4. To keep this task self-contained, create `backend/app/security.py` now with just the two password helpers (Task 4 adds JWT on top):

`backend/app/security.py` (initial version):

```python
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_seed.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.seed'`

- [ ] **Step 3: Create `backend/app/seed.py`**

```python
"""Idempotent seed data: countries, Tier-1 sites, default admin, AI config defaults.

Run manually with:  uv run python -m app.seed
"""

from sqlalchemy.orm import Session

from app.models import AdminUser, AppConfig, Country, Site
from app.security import hash_password

COUNTRIES = [
    # (code, name_en, name_zh, flag, tier)
    ("NG", "Nigeria", "尼日利亚", "🇳🇬", 1),
    ("GH", "Ghana", "加纳", "🇬🇭", 1),
    ("SN", "Senegal", "塞内加尔", "🇸🇳", 1),
    ("CI", "Côte d'Ivoire", "科特迪瓦", "🇨🇮", 1),
]

SITES = [
    # (country_code, name, base_url, language, discovery, feed_url, listing_url)
    ("NG", "Premium Times", "https://www.premiumtimesng.com", "en", "rss",
     "https://www.premiumtimesng.com/feed", None),
    ("NG", "Punch", "https://punchng.com", "en", "rss",
     "https://punchng.com/feed/", None),
    ("NG", "Channels TV", "https://www.channelstv.com", "en", "rss",
     "https://www.channelstv.com/feed/", None),
    ("GH", "GhanaWeb", "https://www.ghanaweb.com", "en", "listing",
     None, "https://www.ghanaweb.com/GhanaHomePage/NewsArchive/"),
    ("GH", "MyJoyOnline", "https://www.myjoyonline.com", "en", "rss",
     "https://www.myjoyonline.com/feed/", None),
    ("GH", "Graphic Online", "https://www.graphic.com.gh", "en", "listing",
     None, "https://www.graphic.com.gh/news.html"),
    ("SN", "Seneweb", "https://www.seneweb.com", "fr", "listing",
     None, "https://www.seneweb.com/news/"),
    ("SN", "Dakaractu", "https://www.dakaractu.com", "fr", "rss",
     "https://www.dakaractu.com/xml/syndication.rss", None),
    ("CI", "Abidjan.net", "https://news.abidjan.net", "fr", "listing",
     None, "https://news.abidjan.net/"),
    ("CI", "Koaci", "https://www.koaci.com", "fr", "listing",
     None, "https://www.koaci.com/"),
]

CONFIG_DEFAULTS = {
    "ai_base_url": "https://api.openai.com/v1",
    "ai_api_key": "",
    "ai_model": "gpt-4o-mini",
}

DEFAULT_ADMIN = ("admin", "admin123")  # change the password after first login


def seed_all(db: Session) -> None:
    countries: dict[str, Country] = {}
    for code, name_en, name_zh, flag, tier in COUNTRIES:
        country = db.query(Country).filter_by(code=code).one_or_none()
        if country is None:
            country = Country(
                code=code, name_en=name_en, name_zh=name_zh, flag_emoji=flag, tier=tier
            )
            db.add(country)
        countries[code] = country
    db.flush()

    for code, name, base_url, language, discovery, feed_url, listing_url in SITES:
        if db.query(Site).filter_by(base_url=base_url).one_or_none() is None:
            db.add(
                Site(
                    country_id=countries[code].id,
                    name=name,
                    base_url=base_url,
                    language=language,
                    discovery_method=discovery,
                    feed_url=feed_url,
                    listing_url=listing_url,
                    tier=1,
                )
            )

    username, password = DEFAULT_ADMIN
    if db.query(AdminUser).filter_by(username=username).one_or_none() is None:
        db.add(AdminUser(username=username, password_hash=hash_password(password)))

    for key, value in CONFIG_DEFAULTS.items():
        if db.get(AppConfig, key) is None:
            db.add(AppConfig(key=key, value=value))

    db.commit()


if __name__ == "__main__":
    import app.models  # noqa: F401

    from app.db import Base, SessionLocal, engine

    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed_all(session)
    print("Seed complete.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_seed.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/seed.py backend/app/security.py backend/tests/test_seed.py
git commit -m "feat(backend): add idempotent seed for countries, Tier-1 sites, admin, AI config"
```

---

### Task 4: Auth — JWT login + protected-route dependency

**Files:**
- Modify: `backend/app/security.py` (add JWT + dependency)
- Create: `backend/app/schemas.py` (login schemas; grows in later tasks)
- Create: `backend/app/api/__init__.py`, `backend/app/api/admin/__init__.py`, `backend/app/api/admin/auth.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Write the failing test — `backend/tests/test_auth.py`**

```python
from app.models import AdminUser
from app.security import hash_password


def _create_admin(db_session, username="admin", password="secret123"):
    db_session.add(AdminUser(username=username, password_hash=hash_password(password)))
    db_session.commit()


def _login(client, username="admin", password="secret123"):
    return client.post(
        "/api/admin/auth/login", json={"username": username, "password": password}
    )


def test_login_success_returns_token(client, db_session):
    _create_admin(db_session)
    r = _login(client)
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_wrong_password_401(client, db_session):
    _create_admin(db_session)
    r = _login(client, password="wrong")
    assert r.status_code == 401


def test_me_requires_token(client, db_session):
    _create_admin(db_session)
    assert client.get("/api/admin/auth/me").status_code == 401
    assert (
        client.get(
            "/api/admin/auth/me", headers={"Authorization": "Bearer not-a-token"}
        ).status_code
        == 401
    )

    token = _login(client).json()["access_token"]
    r = client.get("/api/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"username": "admin"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_auth.py -v`
Expected: FAIL — login route returns 404 (`assert r.status_code == 200` fails)

- [ ] **Step 3: Extend `backend/app/security.py`** (full file after edit)

```python
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """FastAPI dependency: returns the authenticated admin username or raises 401."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(
            credentials.credentials, settings.jwt_secret, algorithms=[ALGORITHM]
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload["sub"]
```

- [ ] **Step 4: Create `backend/app/schemas.py`** (initial version)

```python
from pydantic import BaseModel


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

- [ ] **Step 5: Create `backend/app/api/__init__.py` and `backend/app/api/admin/__init__.py`** (both empty)

- [ ] **Step 6: Create `backend/app/api/admin/auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AdminUser
from app.schemas import LoginIn, TokenOut
from app.security import create_access_token, get_current_admin, verify_password

router = APIRouter()


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(AdminUser).filter_by(username=body.username).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return TokenOut(access_token=create_access_token(user.username))


@router.get("/me")
def me(username: str = Depends(get_current_admin)):
    return {"username": username}
```

- [ ] **Step 7: Wire router in `backend/app/main.py`** (full file after edit)

```python
from fastapi import FastAPI

from app.api.admin import auth as admin_auth

app = FastAPI(title="ZokoDaily API")

app.include_router(admin_auth.router, prefix="/api/admin/auth", tags=["admin-auth"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/ -v`
Expected: all pass

- [ ] **Step 9: Commit**

```bash
git add backend/app/ backend/tests/test_auth.py
git commit -m "feat(backend): JWT admin auth with login and protected-route dependency"
```

---

### Task 5: Public articles API (list, banner, detail)

**Files:**
- Create: `backend/app/api/public.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_public_api.py`

- [ ] **Step 1: Write the failing test — `backend/tests/test_public_api.py`**

```python
from datetime import datetime, timezone

import pytest

from app.models import Article, Country, Site


@pytest.fixture()
def sample_data(db_session):
    gh = Country(code="GH", name_en="Ghana", name_zh="加纳", flag_emoji="🇬🇭")
    sn = Country(code="SN", name_en="Senegal", name_zh="塞内加尔", flag_emoji="🇸🇳")
    site_gh = Site(country=gh, name="MyJoyOnline", base_url="https://www.myjoyonline.com",
                   language="en", discovery_method="rss")
    site_sn = Site(country=sn, name="Seneweb", base_url="https://www.seneweb.com",
                   language="fr", discovery_method="listing")
    articles = []
    for i in range(3):
        articles.append(Article(
            site=site_gh, country=gh, source_url=f"https://gh.example/{i}",
            source_language="en", title=f"Ghana story {i}", title_zh=f"加纳新闻 {i}",
            category="business", paragraphs=[f"Para {i}."], paragraphs_zh=[f"段落 {i}。"],
            status="published", is_banner=(i == 0),
            published_at=datetime(2026, 7, 1 + i, tzinfo=timezone.utc),
        ))
    articles.append(Article(
        site=site_sn, country=sn, source_url="https://sn.example/1",
        source_language="fr", title="Histoire du Sénégal", title_zh="塞内加尔新闻",
        category="politics", paragraphs=["Le paragraphe."], paragraphs_zh=["段落。"],
        status="published", published_at=datetime(2026, 7, 9, tzinfo=timezone.utc),
    ))
    articles.append(Article(
        site=site_gh, country=gh, source_url="https://gh.example/pending",
        source_language="en", title="Not translated yet", paragraphs=["x"],
        status="pending_translation",
    ))
    db_session.add_all(articles)
    db_session.commit()
    return articles


def test_list_returns_only_published_newest_first(client, sample_data):
    r = client.get("/api/public/articles")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 4
    assert [a["title"] for a in body["items"]][:2] == ["Histoire du Sénégal", "Ghana story 2"]
    assert body["items"][0]["country"]["flag_emoji"] == "🇸🇳"


def test_list_filters(client, sample_data):
    assert client.get("/api/public/articles?country=SN").json()["total"] == 1
    assert client.get("/api/public/articles?category=business").json()["total"] == 3
    assert client.get("/api/public/articles?search=加纳新闻 1").json()["total"] == 1
    assert client.get("/api/public/articles?page=1&page_size=2").json()["items"][1][
        "title"
    ] == "Ghana story 2"


def test_banner_returns_five_or_fewer_published(client, sample_data):
    r = client.get("/api/public/articles/banner")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 4  # 1 flagged + 3 fill, pending one excluded
    assert items[0]["title"] == "Ghana story 0"  # flagged first


def test_detail_full_payload_and_404s(client, sample_data):
    listing = client.get("/api/public/articles?country=SN").json()["items"]
    r = client.get(f"/api/public/articles/{listing[0]['id']}")
    assert r.status_code == 200
    d = r.json()
    assert d["paragraphs"] == ["Le paragraphe."]
    assert d["paragraphs_zh"] == ["段落。"]
    assert d["source_language"] == "fr"
    assert d["site"]["name"] == "Seneweb"

    assert client.get("/api/public/articles/999999").status_code == 404
    pending_id = sample_data[-1].id
    assert client.get(f"/api/public/articles/{pending_id}").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_public_api.py -v`
Expected: FAIL — routes return 404

- [ ] **Step 3: Create `backend/app/api/public.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import STATUS_PUBLISHED, Article, Country

router = APIRouter()


def _card(a: Article) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "title_zh": a.title_zh,
        "main_image_url": a.main_image_url,
        "published_at": a.published_at.isoformat() if a.published_at else None,
        "category": a.category,
        "country": {
            "code": a.country.code,
            "name_en": a.country.name_en,
            "name_zh": a.country.name_zh,
            "flag_emoji": a.country.flag_emoji,
        },
    }


@router.get("/articles")
def list_articles(
    country: str | None = None,
    category: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    q = select(Article).join(Country, Article.country_id == Country.id).where(
        Article.status == STATUS_PUBLISHED
    )
    if country:
        q = q.where(Country.code == country.upper())
    if category:
        q = q.where(Article.category == category)
    if search:
        like = f"%{search}%"
        q = q.where(or_(Article.title.like(like), Article.title_zh.like(like)))

    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(Article.published_at.desc(), Article.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {"items": [_card(a) for a in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/articles/banner")
def banner_articles(db: Session = Depends(get_db)):
    flagged = list(
        db.scalars(
            select(Article)
            .where(Article.status == STATUS_PUBLISHED, Article.is_banner.is_(True))
            .order_by(Article.published_at.desc(), Article.id.desc())
            .limit(5)
        )
    )
    if len(flagged) < 5:
        taken = [a.id for a in flagged] or [0]
        fill = db.scalars(
            select(Article)
            .where(Article.status == STATUS_PUBLISHED, Article.id.not_in(taken))
            .order_by(Article.published_at.desc(), Article.id.desc())
            .limit(5 - len(flagged))
        )
        flagged.extend(fill)
    return [_card(a) for a in flagged]


@router.get("/articles/{article_id}")
def article_detail(article_id: int, db: Session = Depends(get_db)):
    a = db.get(Article, article_id)
    if a is None or a.status != STATUS_PUBLISHED:
        raise HTTPException(status_code=404, detail="Article not found")
    d = _card(a)
    d.update(
        {
            "source_language": a.source_language,
            "paragraphs": a.paragraphs,
            "paragraphs_zh": a.paragraphs_zh,
            "site": {"name": a.site.name, "url": a.source_url},
        }
    )
    return d
```

Note: `/articles/banner` is declared before `/articles/{article_id}` — route order matters.

- [ ] **Step 4: Wire router in `backend/app/main.py`** (add lines)

```python
from app.api import public

app.include_router(public.router, prefix="/api/public", tags=["public"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/ -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/public.py backend/app/main.py backend/tests/test_public_api.py
git commit -m "feat(backend): public articles API - list, banner, detail"
```

---

### Task 6: Admin countries & sites CRUD

**Files:**
- Modify: `backend/app/schemas.py`
- Create: `backend/app/api/admin/countries.py`, `backend/app/api/admin/sites.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_admin_countries_sites.py`

- [ ] **Step 1: Write the failing test — `backend/tests/test_admin_countries_sites.py`**

```python
import pytest

from app.models import AdminUser
from app.security import hash_password


@pytest.fixture()
def auth_headers(client, db_session):
    db_session.add(AdminUser(username="admin", password_hash=hash_password("pw")))
    db_session.commit()
    token = client.post(
        "/api/admin/auth/login", json={"username": "admin", "password": "pw"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_endpoints_require_auth(client):
    assert client.get("/api/admin/countries").status_code == 401
    assert client.get("/api/admin/sites").status_code == 401


def test_country_crud(client, auth_headers):
    r = client.post(
        "/api/admin/countries",
        json={"code": "BJ", "name_en": "Benin", "name_zh": "贝宁", "flag_emoji": "🇧🇯", "tier": 2},
        headers=auth_headers,
    )
    assert r.status_code == 201
    cid = r.json()["id"]

    assert len(client.get("/api/admin/countries", headers=auth_headers).json()) == 1

    r = client.put(
        f"/api/admin/countries/{cid}",
        json={"code": "BJ", "name_en": "Benin", "name_zh": "贝宁", "flag_emoji": "🇧🇯",
              "tier": 2, "enabled": False},
        headers=auth_headers,
    )
    assert r.json()["enabled"] is False

    assert client.delete(f"/api/admin/countries/{cid}", headers=auth_headers).status_code == 204
    assert client.get("/api/admin/countries", headers=auth_headers).json() == []


def test_site_crud(client, auth_headers):
    cid = client.post(
        "/api/admin/countries",
        json={"code": "TG", "name_en": "Togo", "name_zh": "多哥", "flag_emoji": "🇹🇬", "tier": 2},
        headers=auth_headers,
    ).json()["id"]

    r = client.post(
        "/api/admin/sites",
        json={"country_id": cid, "name": "Togo First", "base_url": "https://www.togofirst.com",
              "language": "fr", "discovery_method": "rss",
              "feed_url": "https://www.togofirst.com/fr/rss", "tier": 2},
        headers=auth_headers,
    )
    assert r.status_code == 201
    sid = r.json()["id"]

    r = client.put(
        f"/api/admin/sites/{sid}",
        json={"country_id": cid, "name": "Togo First", "base_url": "https://www.togofirst.com",
              "language": "fr", "discovery_method": "rss",
              "feed_url": "https://www.togofirst.com/fr/rss", "tier": 2, "enabled": False},
        headers=auth_headers,
    )
    assert r.json()["enabled"] is False

    sites = client.get("/api/admin/sites", headers=auth_headers).json()
    assert len(sites) == 1 and sites[0]["country"]["code"] == "TG"

    assert client.delete(f"/api/admin/sites/{sid}", headers=auth_headers).status_code == 204
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_admin_countries_sites.py -v`
Expected: FAIL — admin routes return 404 (auth test: 401 expected but route missing → 404)

- [ ] **Step 3: Extend `backend/app/schemas.py`** (append)

```python
from pydantic import ConfigDict


class CountryIn(BaseModel):
    code: str
    name_en: str
    name_zh: str
    flag_emoji: str
    tier: int = 1
    enabled: bool = True


class CountryOut(CountryIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class SiteIn(BaseModel):
    country_id: int
    name: str
    base_url: str
    language: str
    discovery_method: str
    feed_url: str | None = None
    listing_url: str | None = None
    listing_selector: str | None = None
    title_selector: str | None = None
    body_selector: str | None = None
    image_selector: str | None = None
    date_selector: str | None = None
    tier: int = 1
    enabled: bool = True


class SiteOut(SiteIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    last_crawl_at: datetime | None = None
    last_crawl_status: str | None = None
    country: CountryOut | None = None
```

Note: keep the existing `LoginIn`/`TokenOut` at the top of the file; `from pydantic import BaseModel` is already there. Add `from datetime import datetime` at the top of the file.

- [ ] **Step 4: Create `backend/app/api/admin/countries.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Country
from app.schemas import CountryIn, CountryOut
from app.security import get_current_admin

router = APIRouter(dependencies=[Depends(get_current_admin)])


def _get_or_404(db: Session, country_id: int) -> Country:
    country = db.get(Country, country_id)
    if country is None:
        raise HTTPException(status_code=404, detail="Country not found")
    return country


@router.get("", response_model=list[CountryOut])
def list_countries(db: Session = Depends(get_db)):
    return db.query(Country).order_by(Country.tier, Country.code).all()


@router.post("", response_model=CountryOut, status_code=201)
def create_country(body: CountryIn, db: Session = Depends(get_db)):
    country = Country(**body.model_dump())
    db.add(country)
    db.commit()
    db.refresh(country)
    return country


@router.put("/{country_id}", response_model=CountryOut)
def update_country(country_id: int, body: CountryIn, db: Session = Depends(get_db)):
    country = _get_or_404(db, country_id)
    for field, value in body.model_dump().items():
        setattr(country, field, value)
    db.commit()
    db.refresh(country)
    return country


@router.delete("/{country_id}", status_code=204)
def delete_country(country_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, country_id))
    db.commit()
```

- [ ] **Step 5: Create `backend/app/api/admin/sites.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Site
from app.schemas import SiteIn, SiteOut
from app.security import get_current_admin

router = APIRouter(dependencies=[Depends(get_current_admin)])


def _get_or_404(db: Session, site_id: int) -> Site:
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.get("", response_model=list[SiteOut])
def list_sites(db: Session = Depends(get_db)):
    return db.query(Site).order_by(Site.tier, Site.name).all()


@router.post("", response_model=SiteOut, status_code=201)
def create_site(body: SiteIn, db: Session = Depends(get_db)):
    site = Site(**body.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.put("/{site_id}", response_model=SiteOut)
def update_site(site_id: int, body: SiteIn, db: Session = Depends(get_db)):
    site = _get_or_404(db, site_id)
    for field, value in body.model_dump().items():
        setattr(site, field, value)
    db.commit()
    db.refresh(site)
    return site


@router.delete("/{site_id}", status_code=204)
def delete_site(site_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, site_id))
    db.commit()
```

- [ ] **Step 6: Wire routers in `backend/app/main.py`** (add lines)

```python
from app.api.admin import countries as admin_countries
from app.api.admin import sites as admin_sites

app.include_router(admin_countries.router, prefix="/api/admin/countries", tags=["admin"])
app.include_router(admin_sites.router, prefix="/api/admin/sites", tags=["admin"])
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/ -v`
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add backend/app/ backend/tests/test_admin_countries_sites.py
git commit -m "feat(backend): admin countries and sites CRUD"
```

---

### Task 7: Admin articles API (list, edit, delete, retranslate)

**Files:**
- Modify: `backend/app/schemas.py`
- Create: `backend/app/api/admin/articles.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_admin_articles.py`

- [ ] **Step 1: Write the failing test — `backend/tests/test_admin_articles.py`**

```python
import pytest

from app.models import AdminUser, Article, Country, Site
from app.security import hash_password


@pytest.fixture()
def auth_headers(client, db_session):
    db_session.add(AdminUser(username="admin", password_hash=hash_password("pw")))
    db_session.commit()
    token = client.post(
        "/api/admin/auth/login", json={"username": "admin", "password": "pw"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def articles(db_session):
    gh = Country(code="GH", name_en="Ghana", name_zh="加纳", flag_emoji="🇬🇭")
    site = Site(country=gh, name="MyJoyOnline", base_url="https://www.myjoyonline.com",
                language="en", discovery_method="rss")
    rows = [
        Article(site=site, country=gh, source_url="https://x/1", source_language="en",
                title="Published one", paragraphs=["a"], paragraphs_zh=["甲"],
                status="published"),
        Article(site=site, country=gh, source_url="https://x/2", source_language="en",
                title="Failed one", paragraphs=["b"], status="translation_failed",
                translation_error="LLM timeout"),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return rows


def test_list_shows_all_statuses_and_filters(client, auth_headers, articles):
    r = client.get("/api/admin/articles", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["total"] == 2

    r = client.get("/api/admin/articles?status=translation_failed", headers=auth_headers)
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["translation_error"] == "LLM timeout"


def test_update_article_fields(client, auth_headers, articles):
    aid = articles[0].id
    r = client.patch(
        f"/api/admin/articles/{aid}",
        json={"title_zh": "已编辑标题", "category": "business", "is_banner": True,
              "status": "hidden"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title_zh"] == "已编辑标题"
    assert body["is_banner"] is True
    assert body["status"] == "hidden"


def test_update_rejects_bad_status(client, auth_headers, articles):
    r = client.patch(
        f"/api/admin/articles/{articles[0].id}",
        json={"status": "bogus"},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_retranslate_resets_status(client, auth_headers, articles):
    aid = articles[1].id
    r = client.post(f"/api/admin/articles/{aid}/retranslate", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "pending_translation"
    assert r.json()["translation_error"] is None


def test_delete_article(client, auth_headers, articles):
    aid = articles[0].id
    assert client.delete(f"/api/admin/articles/{aid}", headers=auth_headers).status_code == 204
    assert client.get("/api/admin/articles", headers=auth_headers).json()["total"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_admin_articles.py -v`
Expected: FAIL — routes return 404

- [ ] **Step 3: Extend `backend/app/schemas.py`** (append; `Literal` from `typing`)

```python
from typing import Literal


class ArticleUpdate(BaseModel):
    title: str | None = None
    title_zh: str | None = None
    category: str | None = None
    main_image_url: str | None = None
    paragraphs: list[str] | None = None
    paragraphs_zh: list[str] | None = None
    is_banner: bool | None = None
    status: Literal[
        "pending_translation", "published", "translation_failed", "hidden"
    ] | None = None
```

- [ ] **Step 4: Create `backend/app/api/admin/articles.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import STATUS_PENDING_TRANSLATION, Article
from app.schemas import ArticleUpdate
from app.security import get_current_admin

router = APIRouter(dependencies=[Depends(get_current_admin)])


def _admin_view(a: Article) -> dict:
    return {
        "id": a.id,
        "site_id": a.site_id,
        "site_name": a.site.name,
        "country_code": a.country.code,
        "source_url": a.source_url,
        "source_language": a.source_language,
        "title": a.title,
        "title_zh": a.title_zh,
        "category": a.category,
        "main_image_url": a.main_image_url,
        "published_at": a.published_at.isoformat() if a.published_at else None,
        "paragraphs": a.paragraphs,
        "paragraphs_zh": a.paragraphs_zh,
        "status": a.status,
        "translation_error": a.translation_error,
        "is_banner": a.is_banner,
        "created_at": a.created_at.isoformat(),
    }


def _get_or_404(db: Session, article_id: int) -> Article:
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.get("")
def list_articles(
    status: str | None = None,
    country: str | None = None,
    site_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = select(Article)
    if status:
        q = q.where(Article.status == status)
    if site_id:
        q = q.where(Article.site_id == site_id)
    if country:
        from app.models import Country

        q = q.join(Country, Article.country_id == Country.id).where(
            Country.code == country.upper()
        )
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(Article.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [_admin_view(a) for a in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/{article_id}")
def update_article(article_id: int, body: ArticleUpdate, db: Session = Depends(get_db)):
    article = _get_or_404(db, article_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(article, field, value)
    db.commit()
    db.refresh(article)
    return _admin_view(article)


@router.post("/{article_id}/retranslate")
def retranslate_article(article_id: int, db: Session = Depends(get_db)):
    article = _get_or_404(db, article_id)
    article.status = STATUS_PENDING_TRANSLATION
    article.translation_error = None
    db.commit()
    db.refresh(article)
    return _admin_view(article)


@router.delete("/{article_id}", status_code=204)
def delete_article(article_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, article_id))
    db.commit()
```

- [ ] **Step 5: Wire router in `backend/app/main.py`** (add lines)

```python
from app.api.admin import articles as admin_articles

app.include_router(admin_articles.router, prefix="/api/admin/articles", tags=["admin"])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/ -v`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/ backend/tests/test_admin_articles.py
git commit -m "feat(backend): admin articles list/edit/delete/retranslate"
```

---

### Task 8: Admin AI-translation config API

**Files:**
- Create: `backend/app/services/__init__.py` (empty), `backend/app/services/config_service.py`
- Create: `backend/app/api/admin/config.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_admin_config.py`

- [ ] **Step 1: Write the failing test — `backend/tests/test_admin_config.py`**

```python
import pytest

from app.models import AdminUser, AppConfig
from app.security import hash_password


@pytest.fixture()
def auth_headers(client, db_session):
    db_session.add(AdminUser(username="admin", password_hash=hash_password("pw")))
    db_session.add_all([
        AppConfig(key="ai_base_url", value="https://api.openai.com/v1"),
        AppConfig(key="ai_api_key", value=""),
        AppConfig(key="ai_model", value="gpt-4o-mini"),
    ])
    db_session.commit()
    token = client.post(
        "/api/admin/auth/login", json={"username": "admin", "password": "pw"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_config_masks_api_key(client, auth_headers, db_session):
    db_session.get(AppConfig, "ai_api_key").value = "sk-verysecret1234"
    db_session.commit()
    r = client.get("/api/admin/config", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["ai_base_url"] == "https://api.openai.com/v1"
    assert body["ai_model"] == "gpt-4o-mini"
    assert body["ai_api_key_masked"] == "****1234"
    assert "ai_api_key" not in body


def test_get_config_empty_key_masked_as_empty(client, auth_headers):
    r = client.get("/api/admin/config", headers=auth_headers)
    assert r.json()["ai_api_key_masked"] == ""


def test_update_config(client, auth_headers, db_session):
    r = client.put(
        "/api/admin/config",
        json={"ai_base_url": "https://my-proxy.example/v1", "ai_api_key": "sk-newkey9999",
              "ai_model": "deepseek-chat"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["ai_api_key_masked"] == "****9999"
    assert db_session.get(AppConfig, "ai_api_key").value == "sk-newkey9999"


def test_update_without_key_keeps_existing(client, auth_headers, db_session):
    db_session.get(AppConfig, "ai_api_key").value = "sk-keepme0000"
    db_session.commit()
    r = client.put(
        "/api/admin/config",
        json={"ai_model": "gpt-4o"},
        headers=auth_headers,
    )
    assert r.json()["ai_api_key_masked"] == "****0000"
    assert db_session.get(AppConfig, "ai_api_key").value == "sk-keepme0000"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_admin_config.py -v`
Expected: FAIL — routes return 404

- [ ] **Step 3: Create `backend/app/services/config_service.py`**

```python
from sqlalchemy.orm import Session

from app.models import AppConfig


def get_config(db: Session, key: str, default: str = "") -> str:
    row = db.get(AppConfig, key)
    return row.value if row is not None else default


def set_config(db: Session, key: str, value: str) -> None:
    row = db.get(AppConfig, key)
    if row is None:
        db.add(AppConfig(key=key, value=value))
    else:
        row.value = value


def mask_secret(value: str) -> str:
    if not value:
        return ""
    return "****" + value[-4:]
```

- [ ] **Step 4: Create `backend/app/api/admin/config.py`**

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import get_current_admin
from app.services.config_service import get_config, mask_secret, set_config

router = APIRouter(dependencies=[Depends(get_current_admin)])


class ConfigUpdate(BaseModel):
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    ai_model: str | None = None


def _config_view(db: Session) -> dict:
    return {
        "ai_base_url": get_config(db, "ai_base_url"),
        "ai_api_key_masked": mask_secret(get_config(db, "ai_api_key")),
        "ai_model": get_config(db, "ai_model"),
    }


@router.get("")
def read_config(db: Session = Depends(get_db)):
    return _config_view(db)


@router.put("")
def update_config(body: ConfigUpdate, db: Session = Depends(get_db)):
    for key, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        set_config(db, key, value)
    db.commit()
    return _config_view(db)
```

Note: `POST /api/admin/config/test-translation` is added in Plan 2 alongside the translation client.

- [ ] **Step 5: Wire router in `backend/app/main.py`** (add lines)

```python
from app.api.admin import config as admin_config

app.include_router(admin_config.router, prefix="/api/admin/config", tags=["admin"])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/ -v`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/ backend/tests/test_admin_config.py
git commit -m "feat(backend): admin AI translation config API with key masking"
```

---

### Task 9: Startup table creation + live verification against MySQL

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/.env` (local only, gitignored)

- [ ] **Step 1: Add startup create_all to `backend/app/main.py`**

Final full `backend/app/main.py`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.models  # noqa: F401  (register all tables on Base)
from app.api import public
from app.api.admin import articles as admin_articles
from app.api.admin import auth as admin_auth
from app.api.admin import config as admin_config
from app.api.admin import countries as admin_countries
from app.api.admin import sites as admin_sites
from app.db import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="ZokoDaily API", lifespan=lifespan)

app.include_router(public.router, prefix="/api/public", tags=["public"])
app.include_router(admin_auth.router, prefix="/api/admin/auth", tags=["admin-auth"])
app.include_router(admin_countries.router, prefix="/api/admin/countries", tags=["admin"])
app.include_router(admin_sites.router, prefix="/api/admin/sites", tags=["admin"])
app.include_router(admin_articles.router, prefix="/api/admin/articles", tags=["admin"])
app.include_router(admin_config.router, prefix="/api/admin/config", tags=["admin"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

Caution: the test-suite `client` fixture uses `with TestClient(app)`, which triggers lifespan and would call `create_all` on the **production** engine during tests. Guard against this: in `tests/conftest.py`, the `client` fixture must be changed to disable lifespan by using `TestClient(app, ...)` — simplest robust fix is to point the production engine at SQLite during tests by setting the env var before `app` import. Update `backend/tests/conftest.py` to add, at the very top (before any `app.` import):

```python
import os

os.environ["DATABASE_URL"] = "sqlite://"
```

This makes `app.db.engine` an in-memory SQLite engine in the test process, so lifespan `create_all` is harmless. The per-test `db_session` fixture still uses its own isolated engine.

- [ ] **Step 2: Run the full test suite**

Run: `cd backend && uv run pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 3: Create local MySQL database and `.env`**

Create database (adjust credentials to the local MySQL install):

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS zokodaily CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

Create `backend/.env` (gitignored) by copying `.env.example` and filling in real MySQL credentials.

- [ ] **Step 4: Seed and run the server**

Run: `cd backend && uv run python -m app.seed`
Expected: prints `Seed complete.`

Run: `cd backend && uv run uvicorn app.main:app --port 8000`
Expected: starts without errors.

- [ ] **Step 5: Verify endpoints manually**

```bash
curl -s http://localhost:8000/api/health
# {"status":"ok"}
curl -s http://localhost:8000/api/public/articles
# {"items":[],"total":0,"page":1,"page_size":20}
curl -s -X POST http://localhost:8000/api/admin/auth/login \
  -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}'
# {"access_token":"...","token_type":"bearer"}
curl -s http://localhost:8000/api/admin/sites -H "Authorization: Bearer <token>"
# 10 seeded sites
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/conftest.py
git commit -m "feat(backend): startup table creation and MySQL verification"
```
