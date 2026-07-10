# ZokoDaily — West Africa News Aggregation System — Design

**Date:** 2026-07-10
**Status:** Approved
**Source requirements:** [goal.md](../../../goal.md)

## 1. Purpose

Collect news daily from major West African news sites, translate it into Chinese with an AI
translation API, and serve it through a mobile H5 website ("ZokoDaily") with an admin backend
for managing sources, articles, and pipeline health.

Primary audience: Chinese readers following West African news. Secondary: English readers.

## 2. Decisions made

| Decision | Choice |
| -------- | ------ |
| Tech stack | All-Python monorepo: FastAPI backend + Crawl4AI crawler + two Vue3 frontends |
| Database | MySQL (matches existing zokomart ecosystem) |
| V1 crawl scope | Tier 1 only — all 9 sites across Nigeria, Ghana, Senegal, Côte d'Ivoire |
| H5 UI languages | Chinese + English (UI strings); article content EN/FR + ZH |
| Crawler strategy | Config-driven generic crawler (Approach A) with LLM extraction fallback |
| Category taxonomy | Assigned by LLM during translation (single combined translate+classify prompt) |
| Deployment | Docker Compose: backend + MySQL + nginx serving built frontends |
| Admin auth | Simple username/password login issuing JWT |

## 3. Repository layout

```
daily.zokomart.africa/
├── backend/                  # Python (uv), FastAPI
│   ├── app/
│   │   ├── api/              # routers: /api/public/* (H5), /api/admin/* (JWT required)
│   │   ├── crawler/          # discovery, fetching (Crawl4AI), extraction
│   │   ├── translate/        # OpenAI-compatible client; translate + classify
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # business logic between api and models
│   │   └── scheduler.py      # APScheduler job definitions
│   ├── tests/
│   └── pyproject.toml
├── h5/                       # Vue3 + Vite mobile SPA "ZokoDaily"
├── admin/                    # Vue3 + Vite + Element Plus admin SPA
├── docker-compose.yml
└── docs/
```

## 4. Crawler design (config-driven, Approach A)

Sites are **data, not code**. Each `site` row holds everything the generic pipeline needs;
adding a Tier 2 site later is an admin form submission, not a code deploy.

### Pipeline stages

1. **Discover** — produce candidate article URLs for a site:
   - `rss`: parse the configured feed URL with `feedparser` (preferred; most Tier 1 sites have RSS)
   - `listing`: fetch the configured listing page, extract links via a CSS selector
2. **Dedupe** — skip URLs already present in `article.source_url`.
3. **Fetch + extract** — Crawl4AI (headless browser, anti-blocking) fetches the article page and
   extracts: title, main image URL, published date, ordered body paragraphs.
   Per-site CSS-selector overrides (stored on the `site` row) take precedence when set.
   If generic extraction yields poor results (empty/short body), fall back to LLM extraction
   of the fetched HTML.
4. **Store** — save article with status `pending_translation`; record per-stage outcome in
   `crawl_run` and on the article.
5. **Translate + classify** — a worker picks up `pending_translation` articles, sends title +
   paragraphs to the configured OpenAI-compatible API in one prompt that returns:
   ZH title, per-paragraph ZH translations (aligned 1:1 with source paragraphs), and a category
   from a fixed taxonomy (e.g. politics, business, sports, entertainment, society, technology, health).
   On success → status `published`; on failure → `translation_failed` with error recorded.

### Scheduling

APScheduler inside the backend process:

- Tier 1 sites: crawl every hour
- Tier 2 sites: every 6 hours
- Low-frequency sites: daily

Tier is a field on `site`; jobs query sites by tier. A translation-retry sweep runs periodically.

### V1 seed sites (Tier 1)

| Country | Sites | Language |
| ------- | ----- | -------- |
| Nigeria | Premium Times, Punch, Channels TV | EN |
| Ghana | GhanaWeb, MyJoyOnline, Graphic | EN |
| Senegal | Seneweb, Dakaractu | FR |
| Côte d'Ivoire | Abidjan.net, Koaci | FR |

Seeded via a data migration/seed script; editable in admin afterwards.

## 5. Data model (MySQL, SQLAlchemy)

- **country** — code (ISO 3166-1 alpha-2), name_en, name_zh, flag_emoji, tier, enabled
- **site** — country_id, name, base_url, language (`en`/`fr`), discovery_method (`rss`/`listing`),
  feed_url, listing_url, listing_selector, extraction overrides (title/body/image/date selectors,
  nullable), tier, enabled, last_crawl_at, last_crawl_status
- **article** — site_id, country_id, source_url (unique), source_language, title, title_zh,
  category, main_image_url, published_at, paragraphs (JSON: ordered list of source-language
  strings), paragraphs_zh (JSON: aligned list of ZH strings), status
  (`pending_translation` / `published` / `translation_failed` / `hidden`), translation_error,
  is_banner (bool — featured in homepage banner), created_at, updated_at
- **crawl_run** — site_id, started_at, finished_at, status, articles_found, articles_new, error
- **app_config** — key/value store: AI base_url, api_key, model name, prompt options
- **admin_user** — username, password_hash

Paragraph-aligned storage (`paragraphs` / `paragraphs_zh`) directly powers the bilingual
interleaved view on the H5 detail page.

## 6. API design (FastAPI)

### Public (`/api/public/*`, no auth — consumed by H5)

- `GET /articles` — paginated list (published only): id, title, title_zh, image, date, country
  (code + flag + names), category. Filters: country, category, search keyword.
- `GET /articles/banner` — 5 most recent banner-flagged (fallback: latest) articles.
- `GET /articles/{id}` — full detail incl. paragraphs + paragraphs_zh, source site name/url.

### Admin (`/api/admin/*`, JWT bearer required)

- `POST /auth/login` — issue JWT.
- CRUD: `/countries`, `/sites`.
- `/articles` — list with status filters, edit (title/paragraphs/translations/category/banner
  flag/hidden), delete, `POST /articles/{id}/retranslate`.
- `/crawl` — list crawl_runs, `POST /sites/{id}/crawl` (trigger now).
- `/config` — get/update AI translation config (api_key write-only, masked on read).
- `POST /config/test-translation` — round-trip test of the configured AI endpoint.

## 7. H5 site (Vue3 + Vite mobile SPA)

UI languages: 中文 / English (vue-i18n, toggle persisted in localStorage).

> **Visual design:** approved colors, typography, and component treatments are specified in
> [2026-07-10-h5-ui-design.md](2026-07-10-h5-ui-design.md) — Plan 3 must follow it.

### Homepage

- Header: logo top-left + "ZokoDaily" text; top-right: UI language switch + search button
  (search opens keyword input, queries `GET /articles?search=`).
- Banner: 5 auto-rotating news images (swipeable), each navigates to its detail page.
- News list: two columns, each card = image, headline, date, country flag + name.
  Headline shown in current UI language (ZH title when UI is 中文, source title when EN).
- Pull-to-refresh on the list; infinite scroll for pagination.

### Detail page

- Header: back button top-left, then country + category; top-right: share button —
  share sheet with Facebook, WhatsApp, WeChat (copy link + QR guidance, since WeChat has no
  web share URL), and copy-link.
- Main image + content-language toggle top-right of this section: `EN｜ZH｜BL` for English
  sources, `FR｜ZH｜BL` for French sources (source-only / Chinese-only / bilingual).
- Below image: country, category, date; then bold headline; then source website name (links
  to source_url).
- Body: source language by default. Bilingual mode interleaves each source paragraph with its
  Chinese translation.

## 8. Admin SPA (Vue3 + Element Plus)

- Login page → JWT stored, attached via axios interceptor.
- **Countries & Sites**: tables with create/edit/enable-disable; site form exposes discovery
  method, URLs, selectors, tier; "Crawl now" button per site.
- **Articles**: filterable table (status, country, site, date); edit dialog for title,
  translations, category, banner flag, hidden; re-translate button.
- **Pipeline monitor**: crawl_run history per site with status/error; translation failure list
  with retry.
- **Settings**: AI translation base URL / API key / model, with "test translation" button.

## 9. Error handling

- Every pipeline stage records failures where admins can see them: crawl errors on
  `crawl_run` + `site.last_crawl_status`; extraction/translation errors on the article row.
- Crawler continues past per-article failures; a site-level failure marks the run failed but
  never blocks other sites.
- Translation failures leave the article in `translation_failed` (visible in admin, retryable);
  such articles are not served to the H5 site.
- HTTP fetching uses realistic browser headers via Crawl4AI, per-site rate limiting
  (small delay between article fetches), and retries with backoff.

## 10. Testing

- **Backend (pytest)**: unit tests for extraction (fixture HTML pages per Tier 1 site),
  translation prompt/response parsing (mocked LLM), dedupe logic, and API endpoints
  (httpx test client + SQLite-compatible test config or transactional MySQL test DB).
- **Frontends (vitest)**: component tests for the content-language toggle logic
  (EN/FR|ZH|BL rendering, bilingual interleaving) and API stores.
- Crawler runs against live sites are verified manually / via admin "crawl now" during
  development, not in CI.

## 11. Deployment

Docker Compose services:

- `backend` — FastAPI (uvicorn) + APScheduler in-process
- `mysql` — MySQL 8 with persistent volume
- `nginx` — serves built `h5/` (at `/`) and `admin/` (at `/admin/`) static bundles,
  proxies `/api/*` to backend

Configuration via `.env` (DB credentials, JWT secret). AI translation credentials live in the
database (`app_config`), managed through the admin UI.

## 12. Out of scope for V1

- Tier 2 and low-frequency country sites (added later via admin — no code change expected)
- User accounts / comments / push notifications on the H5 site
- Full-text search engine (V1 search = SQL LIKE on titles)
- Analytics dashboards
