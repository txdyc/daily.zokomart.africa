# ZokoDaily Plan 4 — Admin Frontend Design

**Date:** 2026-07-10
**Status:** Draft — pending user review
**Parent spec:** [2026-07-10-zokodaily-news-aggregation-design.md](2026-07-10-zokodaily-news-aggregation-design.md) §8
**Consumes:** the Plan 1 admin API (auth, countries, sites, articles, config) and the
Plan 2 additions (crawl-runs, crawl-now, test-translation). Pages that depend on Plan 2
endpoints are marked below; everything else works against Plan 1 alone.

## 1. Scope

The management SPA in `admin/`: login, countries & sites management, article review/editing,
pipeline monitoring, and AI translation settings.

Out of scope: role-based permissions (single admin role in V1), admin-user management UI,
dashboards/analytics, dark mode.

## 2. Stack decisions

| Concern | Choice | Why |
| ------- | ------ | --- |
| Framework | Vue 3 + TypeScript + Vite | Same as H5; per parent spec |
| Components | **Element Plus** (+ `@element-plus/icons-vue`) | Per parent spec; tables, forms, dialogs, messages out of the box. Deliberately *not* Vben Admin — this backend has ~5 screens; Vben's permission system, mock layer, and build tooling are overhead here |
| State | Pinia (`auth` store only) | Everything else is page-local fetch state |
| Router | vue-router 4, history mode, base `/admin/` | Served under `/admin/` by nginx in Plan 5; `vite.config.ts` sets `base: "/admin/"` to match |
| HTTP | axios instance with JWT interceptors | |
| UI language | **Chinese only** | Internal tool for a Chinese operator; no i18n dependency. Element Plus locale set to `zh-cn` |
| Tests | vitest (utilities + auth logic) | UI is standard Element Plus CRUD; test the logic that can silently corrupt data instead |

## 3. Project structure

```
admin/
├── index.html  package.json  tsconfig.json  vite.config.ts  env.d.ts
├── src/
│   ├── main.ts  App.vue  router.ts
│   ├── api/
│   │   ├── client.ts        # axios: baseURL "/api/admin", request interceptor adds
│   │   │                    #   Bearer token, response interceptor: 401 → logout+/login,
│   │   │                    #   other errors → ElMessage.error(detail)
│   │   ├── types.ts         # Country, Site, ArticleAdmin, CrawlRun, AiConfig, Paginated
│   │   └── endpoints.ts     # typed functions per endpoint
│   ├── stores/auth.ts       # token (localStorage "zoko-admin-token"), username,
│   │                        #   login(), logout(); router guard reads this
│   ├── utils/paragraphs.ts  # joinParagraphs / splitParagraphs ("\n\n" convention)
│   ├── layout/AdminLayout.vue   # el-container: sidebar menu + header (username, logout)
│   └── views/
│       ├── LoginView.vue        # centered card, username/password, error message
│       ├── SitesView.vue        # countries + sites management (tabbed)
│       ├── ArticlesView.vue     # filterable table + edit dialog
│       ├── PipelineView.vue     # crawl runs + translation failures      [needs Plan 2]
│       └── SettingsView.vue     # AI config + test translation           [test btn needs Plan 2]
└── tests/
    ├── paragraphs.spec.ts   # join/split round-trip, alignment count
    └── auth.spec.ts         # guard redirects, 401 interceptor clears token
```

Routes: `/login` (public) and, behind the auth guard, `/` → redirect `/articles`,
`/articles`, `/sites`, `/pipeline`, `/settings`.

## 4. Pages

### 4.1 Login

`POST /auth/login`; on success store token + username, redirect to the originally requested
route (`?redirect=` query). Wrong credentials → inline error from the API `detail`.
Guard: any protected route without a token → `/login?redirect=<path>`; a 401 from any API
call clears the token and does the same (session expiry).

### 4.2 Countries & sites (`SitesView`)

Two tabs on one page (they're managed together):

- **Sites tab (default):** el-table — name, country (flag+name), language, discovery method,
  tier, enabled switch, `last_crawl_at` / `last_crawl_status` (health column, red text when
  it starts with `failed:`), actions: edit, crawl-now [Plan 2], delete.
  - Create/edit dialog: country select, name, base_url, language (en/fr), tier (1/2/3),
    discovery method radio — `rss` shows feed_url field, `listing` shows listing_url +
    listing_selector; a collapsed "高级：提取选择器" section holds the four extraction
    override selectors. Client-side required checks; server 409/422 messages surface as-is.
  - Crawl-now button → `POST /sites/{id}/crawl`; 202 → success toast with run id and a
    link to Pipeline; 409 → warning toast ("已在抓取中").
  - Delete → confirm dialog; server 409 (has articles) shown as warning.
- **Countries tab:** el-table — code, flag, names, tier, enabled switch, delete (409-aware);
  create/edit dialog with the five fields.

### 4.3 Articles (`ArticlesView`)

- Filter bar: status select (全部/待翻译/已发布/翻译失败/已隐藏), country select, site select,
  keyword-free (API has no admin search in V1 — filters only). Server-side pagination
  (el-pagination bound to page/page_size/total).
- Table: id, thumbnail (40px), title (2-line clamp, shows title_zh under it, muted),
  site, country flag, category, status tag (color per status), published_at, is_banner
  star toggle, actions: edit / retranslate / delete.
  - Banner star toggles via `PATCH {is_banner}` immediately (no dialog).
  - Retranslate → confirm → `POST /{id}/retranslate` → status flips to 待翻译.
  - Delete → confirm dialog.
- **Edit dialog** (the risky part — paragraph alignment):
  - title, title_zh, category select (7 fixed), status select, main_image_url with preview.
  - Source paragraphs and 中文 paragraphs as two side-by-side textareas using the
    `"\n\n"` join/split convention from `utils/paragraphs.ts`.
  - A live counter under each textarea ("段落数: N"); when counts differ the dialog shows
    a warning banner and the save button stays enabled but requires a confirm ("段落数不一致，
    双语对照将错位，确定保存？") — admins may legitimately fix counts in stages.
  - Save sends only changed fields via PATCH.
- `translation_error` (when present) shows in an expandable row under the article.

### 4.4 Pipeline monitor (`PipelineView`) — needs Plan 2 endpoints

Two sections on one page:

- **抓取记录 (crawl runs):** el-table over `GET /crawl-runs` — site name, started/finished,
  status tag, found/new counts, error (expandable when long); site filter; paginated;
  refresh button plus auto-refresh toggle (10s polling while the page is open, off by default).
- **翻译失败 (translation failures):** the articles table pre-filtered to
  `status=translation_failed` — id, title, site, error, retranslate button, "全部重试" bulk
  button (sequential retranslate calls with a progress count).

### 4.5 Settings (`SettingsView`)

- Form: ai_base_url, ai_model, ai_api_key — the key field is a password input whose
  placeholder shows the masked value from GET (`****1234`); leaving it empty on save omits
  the field from the PUT (keeps the stored key — matches verified API behavior).
- 测试翻译 button [Plan 2] → `POST /config/test-translation`; renders `ok` result
  (title_zh + latency) in a success alert or the error string in a red alert.

## 5. Error handling

- axios response interceptor: 401 → logout + redirect (as §4.1); 409/422 → `ElMessage.warning`
  with the API `detail`; network/5xx → `ElMessage.error("请求失败，请重试")` and the raw detail
  in console. Views additionally handle their inline cases (login error, test-translation result).
- All destructive actions (delete, retranslate, bulk retry) use `ElMessageBox.confirm`.
- Table loading states via `v-loading`; failed table loads show an inline retry button.

## 6. Testing

- `paragraphs.spec.ts`: `splitParagraphs("a\n\nb\n\nc") → ["a","b","c"]`; blank/whitespace
  segments dropped; `joinParagraphs` round-trips; CRLF input normalized.
- `auth.spec.ts`: guard redirects unauthenticated navigation to `/login?redirect=...`;
  401 interceptor clears localStorage token (login's token storage is covered by the
  live walkthrough — mocking axios for it isn't worth the brittleness).
- Everything else is Element Plus plumbing verified live (Task-level manual verification
  against the running backend, same approach as Plans 1–3).

Run: `npm run test`; type gate `vue-tsc --noEmit` inside `npm run build`.

## 7. Dev workflow

- `npm run dev` on port **5174** (H5 uses 5173), proxy `/api` → `http://localhost:8000`.
- With `base: "/admin/"`, dev URLs are `http://localhost:5174/admin/`.
- `npm run build` emits `admin/dist/` for nginx (`/admin/` path + SPA fallback), Plan 5.
