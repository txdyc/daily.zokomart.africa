# ZokoDaily Plan 3 — H5 Frontend Design

**Date:** 2026-07-10
**Status:** Draft — pending user review
**Parent spec:** [2026-07-10-zokodaily-news-aggregation-design.md](2026-07-10-zokodaily-news-aggregation-design.md) §7
**Visual spec:** [2026-07-10-h5-ui-design.md](2026-07-10-h5-ui-design.md) (binding — colors, typography, component treatments)
**Consumes:** the Plan 1 public API (`/api/public/*`), unchanged; Plan 3 requires no backend work.

## 1. Scope

The mobile H5 website "ZokoDaily" in `h5/`: homepage (header, banner, two-column list,
search, pull-to-refresh, infinite scroll) and article detail page (share, content-language
toggle, bilingual view). Chinese + English UI.

Out of scope: admin frontend (Plan 4), deployment/nginx (Plan 5), user accounts, comments,
push notifications, SSR/SEO.

## 2. Stack decisions

| Concern | Choice | Why |
| ------- | ------ | --- |
| Framework | Vue 3 + TypeScript + Vite | Matches the ecosystem (Vben admin is Vue3+TS) |
| Touch components | **Vant 4** (`van-swipe`, `van-pull-refresh`, `van-list`, `van-popup`) | Battle-tested mobile touch behavior (banner swipe, pull-to-refresh, infinite scroll, share sheet) is the hardest part to hand-roll; Vant is themeable via CSS variables so the approved visual spec still applies |
| State | Pinia | Ecosystem standard |
| Router | vue-router 4, history mode | Two routes only |
| HTTP | axios, thin wrapper | Ecosystem standard |
| i18n | vue-i18n 9, `zh` default, `en` secondary | Per parent spec |
| QR code (WeChat share) | `qrcode` (npm) | Renders share-link QR client-side |
| Tests | vitest + @vue/test-utils | Per parent spec §10 |

Vant theming: override Vant's CSS variables (`--van-primary-color` etc.) from our token file
so its components inherit the visual spec; anything Vant can't match visually is built custom
(cards, toggles, and headers are custom components regardless).

## 3. Project structure

```
h5/
├── index.html                 # viewport meta, lang, app mount point
├── vite.config.ts             # @vitejs/plugin-vue, dev proxy /api → http://localhost:8000
├── package.json  tsconfig.json
├── src/
│   ├── main.ts                # app + pinia + router + i18n + vant setup
│   ├── App.vue                # <router-view>, global styles import
│   ├── router.ts              # "/" → HomeView, "/article/:id" → ArticleView
│   ├── styles/
│   │   ├── tokens.css         # design tokens from the visual spec + Vant overrides
│   │   └── base.css           # reset, font stack, hairline helpers
│   ├── i18n/
│   │   ├── index.ts           # createI18n, locale persisted in localStorage("zoko-lang")
│   │   ├── zh.ts  en.ts       # UI strings (~30 keys)
│   ├── api/
│   │   ├── client.ts          # axios instance, baseURL "/api/public", error normalizing
│   │   ├── types.ts           # ArticleCard, ArticleDetail, CountryInfo, Paginated<T>
│   │   └── articles.ts        # listArticles(params), getBanner(), getArticle(id)
│   ├── stores/
│   │   ├── prefs.ts           # uiLang ("zh"|"en"), setLang syncs vue-i18n + localStorage
│   │   └── feed.ts            # list state: items, page, total, loading, finished,
│   │                          #   search keyword; actions: refresh(), loadMore(), search()
│   ├── views/
│   │   ├── HomeView.vue       # header + banner + pull-refresh list wrapper
│   │   └── ArticleView.vue    # detail page, owns contentMode state
│   └── components/
│       ├── AppHeader.vue      # logo + wordmark, lang pill, search icon/expanding input
│       ├── BannerCarousel.vue # van-swipe, scrim overlay, dash indicator (custom)
│       ├── NewsCard.vue       # image, headline (ui-lang aware), meta row
│       ├── NewsGrid.vue       # 2-col grid + van-list infinite scroll
│       ├── CountryTag.vue     # flag emoji + name; code-badge fallback
│       ├── ContentLangToggle.vue  # EN|中|双语 / FR|中|双语 pill
│       ├── ArticleBody.vue    # renders paragraphs per mode (source/zh/bilingual)
│       └── ShareSheet.vue     # van-popup: FB, WhatsApp, WeChat (QR+copy), copy link
└── tests/
    ├── articleBody.spec.ts    # the 3 content modes incl. bilingual interleave
    ├── contentLangToggle.spec.ts  # EN vs FR label sets, mode switching
    ├── newsCard.spec.ts       # headline follows UI language with fallback
    └── feedStore.spec.ts      # refresh/loadMore/search against mocked api
```

## 4. Data flow and behavior

### 4.1 API layer

Types mirror the Plan 1 responses exactly (verified 2026-07-10):

```ts
interface CountryInfo { code: string; name_en: string; name_zh: string; flag_emoji: string }
interface ArticleCard {
  id: number; title: string; title_zh: string | null;
  main_image_url: string | null; published_at: string | null;
  category: string | null; country: CountryInfo;
}
interface ArticleDetail extends ArticleCard {
  source_language: "en" | "fr";
  paragraphs: string[]; paragraphs_zh: string[] | null;
  site: { name: string; url: string };
}
interface Paginated<T> { items: T[]; total: number; page: number; page_size: number }
```

### 4.2 Homepage

- `feed` store drives the list: `refresh()` resets to page 1 (bound to `van-pull-refresh`),
  `loadMore()` increments page until `items.length >= total` (bound to `van-list`),
  `search(keyword)` resets and adds `search=` param. Page size 20.
- Banner loads once per visit via `getBanner()`; `van-swipe` autoplay 5s, custom dash
  indicator per the visual spec; tap → `router.push(/article/:id)`.
- Card headline: `uiLang === "zh" ? (title_zh ?? title) : title`. Date shown as `MM-DD`.
- Search: tapping the icon expands an input in the header (focus + clear/cancel);
  submitting calls `feed.search()`; empty submit restores the default feed.

### 4.3 Article detail

- `ArticleView` fetches on mount by route param; 404 → friendly "内容不存在 / Not found"
  state with a back link.
- `contentMode: "source" | "zh" | "bilingual"`, default `"source"` (per parent spec).
  Toggle labels derive from `source_language` (`EN` or `FR` as the first segment).
- `ArticleBody` renders:
  - `source`: `paragraphs`
  - `zh`: `paragraphs_zh` (if null — untranslated edge case — falls back to source and the
    toggle hides the 中/双语 segments)
  - `bilingual`: interleaved pairs `paragraphs[i]` then `paragraphs_zh[i]`, ZH styled per
    the visual spec (muted + left rule)
- Headline follows the mode (source / zh / both), per the visual spec §4.
- Share sheet targets:
  - Facebook: `https://www.facebook.com/sharer/sharer.php?u={url}`
  - WhatsApp: `https://wa.me/?text={title}%20{url}`
  - WeChat: popup pane showing a QR code of the page URL + copy-link button (WeChat has no
    web share URL)
  - Copy link: Clipboard API with `document.execCommand` fallback; toast on success
  - When `navigator.share` exists (mobile browsers), a "系统分享 / More" entry uses it.
- Page URL is the canonical share URL (`location.href`); no server-side OG tags in V1
  (SPA — accepted limitation, noted for a future SSR pass if link previews matter).

### 4.4 i18n and language rules

- UI language toggle (header pill): switches vue-i18n locale zh ⇄ en, persists to
  localStorage, affects UI strings, card headlines, and country names — **not** the
  per-article content mode, which is independent and per-page-visit.
- Country name: `uiLang === "zh" ? country.name_zh : country.name_en`, after `flag_emoji`.
- Categories display via i18n map (`business` → 商业/Business, etc. — 7 fixed keys).

## 5. Error handling

- axios wrapper normalizes failures into `{ message }`; views show a centered retry block
  (message + "重试 / Retry" button) for initial-load failures; `van-list` shows its built-in
  error-tap-to-retry state for pagination failures.
- Images: skeleton placeholder block (visual spec) while loading; on error swap to the
  placeholder with the photo icon.
- Empty feed (no published articles yet): friendly empty state, not an error.

## 6. Testing

Per parent spec §10 — component/store tests only, no e2e in V1:

- `ArticleBody`: exact DOM order for bilingual interleave; zh fallback when
  `paragraphs_zh` is null.
- `ContentLangToggle`: FR source shows `FR｜中｜双语`; EN source shows `EN｜中｜双语`;
  emits mode changes; hides 中/双语 when no translation exists.
- `NewsCard`: headline switches with UI language and falls back when `title_zh` is null.
- `feed` store: refresh resets page, loadMore appends and stops at total, search
  passes the keyword (axios mocked with vi.mock).

Run: `npm run test` (vitest). Type gate: `vue-tsc --noEmit` in `npm run build`.

## 7. Dev workflow

- `npm run dev` on port 5173, Vite proxy forwards `/api` to the backend on `:8000` —
  run the Plan 1 backend locally (SQLite is fine) for live data.
- Production build (`npm run build`) emits static `h5/dist/` for nginx in Plan 5;
  vue-router history mode requires the standard SPA fallback (`try_files ... /index.html`),
  recorded here for Plan 5.
