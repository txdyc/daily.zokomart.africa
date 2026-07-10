# ZokoDaily Plan 2 — Crawler & Translation Pipeline Design

**Date:** 2026-07-10
**Status:** Draft — pending user review
**Parent spec:** [2026-07-10-zokodaily-news-aggregation-design.md](2026-07-10-zokodaily-news-aggregation-design.md) §4
**Builds on:** Plan 1 backend (implemented and verified 2026-07-10)

## 1. Scope

Everything that turns a configured `site` row into `published` articles:

- URL discovery (RSS + listing pages)
- Fetching and article extraction (Crawl4AI, per-site overrides, LLM fallback)
- AI translation + categorization (OpenAI-compatible API, config from `app_config`)
- Scheduling (APScheduler in-process) and manual triggers
- Pipeline-monitoring admin endpoints (`crawl-runs`, crawl-now, test-translation)

Out of scope: any frontend (Plans 3–4), deployment (Plan 5).

### Plan 1 carry-over fixes (from end-to-end verification)

These ship as the first task of Plan 2 since the crawler depends on clean integrity behavior:

1. `DELETE /api/admin/countries/{id}` and `DELETE /api/admin/sites/{id}` must return `409`
   when child sites/articles exist (currently orphans rows on SQLite; would 500 on MySQL).
2. Duplicate `country.code` / duplicate `site.base_url` on create must return `409`
   (currently a raw 500 IntegrityError).
3. `POST /api/admin/sites` must validate `country_id` exists → `422` (currently accepts silently).
4. All datetimes stored by the pipeline are normalized to UTC and stored naive
   (verification showed tz-aware values are silently flattened by the `DateTime` column).
5. Add `*.db` to the repo `.gitignore`.

## 2. New modules

```
backend/app/crawler/
├── __init__.py
├── discovery.py      # site → list[CandidateArticle] (url, title?, published_at?)
├── fetcher.py        # url → FetchedPage (html, final_url) via Crawl4AI
├── extractor.py      # FetchedPage + Site → ExtractedArticle | ExtractionFailed
├── llm_extractor.py  # fallback: html → ExtractedArticle via LLM
└── pipeline.py       # orchestrates one site crawl; writes Article + CrawlRun rows
backend/app/translate/
├── __init__.py
├── client.py         # OpenAI-compatible chat call, config read from app_config
└── translator.py     # article → title_zh, paragraphs_zh, category; status transitions
backend/app/scheduler.py   # APScheduler jobs: tier crawls + translation sweep
backend/app/api/admin/crawl.py  # crawl-runs list, crawl-now trigger
```

New dependencies: `crawl4ai` (brings Playwright — run `uv run playwright install chromium`
once per environment), `feedparser`, `beautifulsoup4`, `httpx`.

## 3. Data contracts

```python
@dataclass
class CandidateArticle:
    url: str
    title: str | None = None
    published_at: datetime | None = None   # UTC-normalized, naive

@dataclass
class ExtractedArticle:
    title: str
    paragraphs: list[str]        # ≥1 non-empty strings, source order
    main_image_url: str | None
    published_at: datetime | None  # UTC-normalized, naive
```

## 4. Pipeline stages

### 4.1 Discovery (`discovery.py`)

- `discovery_method == "rss"`: parse `site.feed_url` with `feedparser`. Map entries →
  `CandidateArticle(url=entry.link, title=entry.title, published_at=entry.published_parsed → UTC)`.
- `discovery_method == "listing"`: fetch `site.listing_url` via the fetcher, select links with
  `site.listing_selector` (CSS, BeautifulSoup). Selector empty → site-relative `<a>` heuristic:
  same-domain links with path depth ≥ 2, deduplicated, document order.
- Both paths: normalize URLs (strip fragments and tracking params `utm_*`, `fbclid`),
  make absolute against `site.base_url`, drop non-HTTP(S), cap at the **20 newest** candidates.
- Failure (network error, unparseable feed) raises `DiscoveryError` → crawl run fails with
  the message stored in `crawl_run.error` and `site.last_crawl_status`.

### 4.2 Dedupe

Candidates whose normalized URL already exists in `article.source_url` are skipped before
any fetch. `crawl_run.articles_found` = candidate count, `articles_new` = actually stored.

### 4.3 Fetch (`fetcher.py`)

- Crawl4AI `AsyncWebCrawler` (headless Chromium), realistic browser profile, page timeout 30s.
- Politeness: 3s sleep between article fetches within one site; one site crawled at a time.
- One retry on timeout/HTTP 5xx with 10s backoff; then per-article failure (logged, skipped —
  never aborts the whole run).
- The crawler is async; sync callers (APScheduler jobs, admin trigger) wrap it in
  `asyncio.run()` inside a worker thread.

### 4.4 Extraction (`extractor.py`)

Order of attempts:

1. **Per-site overrides** — if `site.body_selector` is set, extract with BeautifulSoup:
   title from `title_selector` (fallback `<h1>`, then `og:title`), body paragraphs from
   `body_selector` descendants (`<p>` texts, in order), image from `image_selector`
   (fallback `og:image`), date from `date_selector` (fallback `<meta property="article:published_time">`).
2. **Generic** — no overrides: title `og:title` → `<h1>`; body = Crawl4AI's cleaned/fit
   markdown split into paragraphs on blank lines, filtered (≥40 chars, no link-only lines);
   image `og:image`; date `article:published_time` meta.
3. **Quality gate** — result must have a title and either ≥2 paragraphs or ≥300 total chars.
   Failing that → LLM fallback (4.5). If the fallback also fails → per-article failure.

Paragraph hygiene: strip whitespace, collapse internal runs, drop boilerplate matches
("Share this", "Read more", copyright lines), preserve source order.

### 4.5 LLM extraction fallback (`llm_extractor.py`)

Send trimmed HTML (scripts/styles/nav removed, capped at ~30k chars) with a prompt requesting
strict JSON: `{"title": str, "paragraphs": [str], "image_url": str|null, "published_at": str|null}`.
Uses the same client/config as translation. Malformed JSON → one retry → per-article failure.

### 4.6 Store

New `Article` row: `status="pending_translation"`, `source_language=site.language`,
`published_at` from extraction, else discovery, else `None` (H5 falls back to `created_at`
for display ordering — already the API's sort tiebreak).

### 4.7 Translation + categorization (`translate/`)

- `client.py`: single function `chat_json(messages) -> dict` — POSTs to
  `{ai_base_url}/chat/completions` with `ai_api_key`/`ai_model` read fresh from `app_config`
  per call (so admin config changes apply without restart), `temperature=0.2`,
  `response_format={"type": "json_object"}`, 120s timeout, httpx.
- `translator.py`: picks up `pending_translation` articles (oldest first, batch of 10 per
  sweep). One prompt per article:
  - **System:** professional news translator; translate to Simplified Chinese; return JSON
    `{"title_zh": str, "paragraphs_zh": [str], "category": str}`; `paragraphs_zh` MUST have
    exactly the same number of elements as the input, aligned one-to-one; category MUST be
    one of the 7 values in `app.models.CATEGORIES`.
  - **User:** JSON `{"title": ..., "paragraphs": [...]}`.
- Validation: paragraph count matches, category in taxonomy (unknown → `"society"`), title
  non-empty. Count mismatch → one retry with an explicit correction line → else failure.
- Success → set `title_zh`, `paragraphs_zh`, `category`, `status="published"`,
  `translation_error=None`. Failure → `status="translation_failed"`,
  `translation_error=<message>` (truncated to 2000 chars).
- Missing/empty `ai_api_key` → articles stay `pending_translation`; the sweep logs once and
  skips (no failure spam while the key is unconfigured).

## 5. Scheduling (`scheduler.py`)

APScheduler `BackgroundScheduler` started in the FastAPI lifespan (env
`SCHEDULER_ENABLED=true` default; set `false` in tests and one-off scripts):

| Job | Interval | Behavior |
| --- | -------- | -------- |
| Crawl tier 1 | hourly | all enabled tier-1 sites, sequential |
| Crawl tier 2 | every 6h | all enabled tier-2 sites, sequential |
| Crawl tier 3 | daily | all enabled tier-3 sites, sequential |
| Translation sweep | every 5 min | batch of 10 pending articles |

`max_instances=1`, `coalesce=True` per job — a slow crawl never stacks. Each site crawl
opens its own DB session and its own `crawl_run` row; one site failing never blocks the next.

## 6. Admin API additions

- `GET /api/admin/crawl-runs?site_id=&page=&page_size=` — newest first, embeds site name.
- `POST /api/admin/sites/{id}/crawl` — starts a crawl for one site in a background thread,
  returns `202 {"crawl_run_id": ...}` immediately; `409` if that site already has a run
  with `status="running"`.
- `POST /api/admin/config/test-translation` — translates a fixed one-paragraph sample through
  the live config; returns `{"ok": true, "title_zh": ..., "latency_ms": ...}` or
  `{"ok": false, "error": ...}` with status 200 (the admin UI shows the result either way).

`site.last_crawl_at` / `site.last_crawl_status` are updated at the end of every run
(`"success: 5 new"` / `"failed: <reason>"`), giving the sites table its health column.

## 7. Error handling summary

| Failure | Recorded where | Effect |
| ------- | -------------- | ------ |
| Discovery error | `crawl_run.status="failed"`, `.error`; `site.last_crawl_status` | run ends, next site continues |
| Per-article fetch/extract failure | run continues; counts in `crawl_run.error` summary (`"3 articles failed: url1..."`) | article skipped, retried naturally next run (still not in DB) |
| Translation failure | `article.status="translation_failed"`, `.translation_error` | visible in admin, manual or sweep retry via retranslate |
| LLM config missing | log once per sweep | articles wait as `pending_translation` |

## 8. Testing

- **No live network in pytest.** Fixture files under `tests/fixtures/`: one RSS XML, one
  listing HTML, three article HTML pages (English WordPress-style, French, and a
  selector-override case). Discovery/extraction tested against these.
- Fetcher is mocked at the `fetch_page()` boundary in pipeline tests; Crawl4AI itself is
  exercised only in live runs.
- Translator tested with a mocked `chat_json` (happy path, count mismatch + retry,
  bad category coercion, API error).
- Status transitions and crawl-run bookkeeping tested through the pipeline with mocks.
- **Live verification** (manual, per the project verify skill): trigger crawl-now on one
  English and one French Tier-1 site, confirm articles reach `pending_translation`, run
  test-translation, confirm articles publish and render correctly via the public API.
  Seeded feed/listing URLs get corrected here if any 404 (they are admin-editable data).

## 9. Windows dev note

Crawl4AI + Playwright must work on the Windows dev box: `asyncio.run()` inside worker
threads requires `WindowsProactorEventLoopPolicy` (default on 3.12 — do not override).
If Chromium install is blocked, the pipeline still functions for RSS discovery + LLM
extraction using plain httpx fetch as a degraded mode (`fetcher.py` falls back to httpx
when Crawl4AI is unavailable, with a warning in the crawl run).
