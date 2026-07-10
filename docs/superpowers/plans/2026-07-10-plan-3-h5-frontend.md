# ZokoDaily Plan 3: H5 Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The mobile H5 site "ZokoDaily" in `h5/`: homepage (banner, two-column list, search, pull-to-refresh, infinite scroll) and article detail (content-language toggle, bilingual view, share sheet), in Chinese/English UI.

**Architecture:** Vue 3 + TypeScript SPA. Vant 4 supplies touch behavior (swipe, pull-refresh, list, popup); all visible styling comes from our own token CSS per the approved visual spec. Pinia stores hold UI language and the paginated feed; two routes (`/`, `/article/:id`) consume the Plan 1 public API through a thin axios layer.

**Tech Stack:** Vue 3, Vite 5, TypeScript, Vant 4, Pinia, vue-router 4, vue-i18n 9, axios, qrcode, vitest + @vue/test-utils (jsdom).

**Specs:** functional/technical `docs/superpowers/specs/2026-07-10-h5-frontend-design.md`; visual (binding) `docs/superpowers/specs/2026-07-10-h5-ui-design.md`.
**Working directory:** all commands run from `h5/` unless stated otherwise.

---

## File structure created by this plan

```
h5/
├── index.html  package.json  tsconfig.json  vite.config.ts  env.d.ts
├── src/
│   ├── main.ts  App.vue  router.ts
│   ├── styles/tokens.css  styles/base.css
│   ├── i18n/index.ts  i18n/zh.ts  i18n/en.ts
│   ├── api/client.ts  api/types.ts  api/articles.ts
│   ├── stores/prefs.ts  stores/feed.ts
│   ├── views/HomeView.vue  views/ArticleView.vue
│   └── components/
│       AppHeader.vue  BannerCarousel.vue  NewsCard.vue  NewsGrid.vue
│       CountryTag.vue  ContentLangToggle.vue  ArticleBody.vue  ShareSheet.vue
└── tests/
    setup.ts  helpers.ts
    prefs.spec.ts  feedStore.spec.ts  newsCard.spec.ts
    contentLangToggle.spec.ts  articleBody.spec.ts  appHeader.spec.ts
```

---

### Task 1: Scaffold — Vite app, tokens, router shell

**Files:**
- Create: `h5/package.json`, `h5/tsconfig.json`, `h5/vite.config.ts`, `h5/env.d.ts`, `h5/index.html`
- Create: `h5/src/main.ts`, `h5/src/App.vue`, `h5/src/router.ts`
- Create: `h5/src/styles/tokens.css`, `h5/src/styles/base.css`
- Create: `h5/src/views/HomeView.vue`, `h5/src/views/ArticleView.vue` (placeholders, replaced in Tasks 6–7)
- Test: `h5/tests/setup.ts`, `h5/tests/smoke.spec.ts`

- [ ] **Step 1: Create `h5/package.json`**

```json
{
  "name": "zokodaily-h5",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "axios": "^1.7.2",
    "pinia": "^2.1.7",
    "qrcode": "^1.5.3",
    "vant": "^4.9.1",
    "vue": "^3.4.29",
    "vue-i18n": "^9.13.1",
    "vue-router": "^4.3.3"
  },
  "devDependencies": {
    "@types/qrcode": "^1.5.5",
    "@vitejs/plugin-vue": "^5.0.5",
    "@vue/test-utils": "^2.4.6",
    "jsdom": "^24.1.0",
    "typescript": "^5.4.5",
    "vite": "^5.3.1",
    "vitest": "^1.6.0",
    "vue-tsc": "^2.0.21"
  }
}
```

Run: `cd h5 && npm install`
Expected: installs cleanly (uses npm; no lockfile exists yet).

- [ ] **Step 2: Create `h5/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "jsx": "preserve",
    "sourceMap": true,
    "resolveJsonModule": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "types": ["vite/client", "vitest/globals"]
  },
  "include": ["src/**/*.ts", "src/**/*.vue", "tests/**/*.ts", "env.d.ts"]
}
```

- [ ] **Step 3: Create `h5/env.d.ts`**

```ts
/// <reference types="vite/client" />
declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<object, object, unknown>;
  export default component;
}
```

- [ ] **Step 4: Create `h5/vite.config.ts`**

```ts
/// <reference types="vitest" />
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["tests/setup.ts"],
  },
});
```

- [ ] **Step 5: Create `h5/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
    <title>ZokoDaily</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 6: Create the style files**

`h5/src/styles/tokens.css` (values are binding, from the visual spec):

```css
:root {
  --brand-50: #e1f5ee;
  --brand-200: #5dcaa5;
  --brand-500: #1d9e75;
  --brand-700: #085041;
  --brand-900: #04342c;

  --bg: #ffffff;
  --surface: #f7f6f3;
  --border: #e5e3dc;
  --text-primary: #1f1f1d;
  --text-secondary: #5f5e5a;
  --text-muted: #93918a;

  --radius-card: 10px;
  --radius-pill: 999px;

  --van-primary-color: var(--brand-500);
  --van-list-text-color: var(--text-muted);
  --van-pull-refresh-head-text-color: var(--text-muted);
}
```

`h5/src/styles/base.css`:

```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: system-ui, -apple-system, "PingFang SC", "Noto Sans SC", sans-serif;
  color: var(--text-primary);
  background: var(--surface);
  font-size: 15px;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}

a {
  color: inherit;
  text-decoration: none;
}

img {
  display: block;
  max-width: 100%;
}

.hairline {
  border-bottom: 1px solid var(--border);
}
@media (min-resolution: 2dppx) {
  .hairline {
    border-bottom-width: 0.5px;
  }
}
```

- [ ] **Step 7: Create router and app shell**

`h5/src/router.ts`:

```ts
import { createRouter, createWebHistory } from "vue-router";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: () => import("./views/HomeView.vue") },
    { path: "/article/:id", name: "article", component: () => import("./views/ArticleView.vue") },
  ],
});
```

`h5/src/App.vue`:

```vue
<template>
  <router-view />
</template>
```

`h5/src/main.ts`:

```ts
import { createPinia } from "pinia";
import { createApp } from "vue";
import "vant/lib/index.css";

import App from "./App.vue";
import { i18n } from "./i18n";
import { router } from "./router";
import "./styles/tokens.css";
import "./styles/base.css";

createApp(App).use(createPinia()).use(router).use(i18n).mount("#app");
```

Note: `./i18n` does not exist until Task 2. For this task only, create `h5/src/i18n/index.ts`
as a stub (Task 2 replaces it):

```ts
import { createI18n } from "vue-i18n";

export const i18n = createI18n({ legacy: false, locale: "zh", messages: { zh: {}, en: {} } });
```

Create the placeholder views:

`h5/src/views/HomeView.vue` (placeholder):

```vue
<template>
  <div>ZokoDaily home placeholder</div>
</template>
```

`h5/src/views/ArticleView.vue` (placeholder):

```vue
<template>
  <div>article placeholder</div>
</template>
```

- [ ] **Step 8: Write the smoke test**

`h5/tests/setup.ts`:

```ts
import { config } from "@vue/test-utils";

config.global.stubs = {};
```

`h5/tests/smoke.spec.ts`:

```ts
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import HomeView from "../src/views/HomeView.vue";

describe("scaffold", () => {
  it("mounts the home view", () => {
    const wrapper = mount(HomeView);
    expect(wrapper.text()).toContain("ZokoDaily");
  });
});
```

- [ ] **Step 9: Run the test and the dev build**

Run: `cd h5 && npm run test`
Expected: 1 passed

Run: `cd h5 && npx vite build`
Expected: builds `dist/` without errors (skip vue-tsc here; the full `npm run build` gate runs in Task 8).

- [ ] **Step 10: Commit**

```bash
git add h5/
git commit -m "feat(h5): scaffold Vite app with router, tokens, and smoke test"
```

---

### Task 2: i18n + prefs store

**Files:**
- Create: `h5/src/i18n/zh.ts`, `h5/src/i18n/en.ts`
- Replace: `h5/src/i18n/index.ts`
- Create: `h5/src/stores/prefs.ts`
- Test: `h5/tests/prefs.spec.ts`, `h5/tests/helpers.ts`

- [ ] **Step 1: Write the failing test**

`h5/tests/helpers.ts` (shared mounting helper used by all component tests):

```ts
import { createPinia, setActivePinia } from "pinia";
import { createI18n } from "vue-i18n";

import en from "../src/i18n/en";
import zh from "../src/i18n/zh";

export function freshPinia() {
  const pinia = createPinia();
  setActivePinia(pinia);
  return pinia;
}

export function testI18n(locale: "zh" | "en" = "zh") {
  return createI18n({ legacy: false, locale, fallbackLocale: "zh", messages: { zh, en } });
}
```

`h5/tests/prefs.spec.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";

import { i18n } from "../src/i18n";
import { usePrefsStore } from "../src/stores/prefs";
import { freshPinia } from "./helpers";

describe("prefs store", () => {
  beforeEach(() => {
    localStorage.clear();
    freshPinia();
  });

  it("defaults to zh", () => {
    expect(usePrefsStore().uiLang).toBe("zh");
  });

  it("toggle switches language, persists, and updates i18n locale", () => {
    const prefs = usePrefsStore();
    prefs.toggle();
    expect(prefs.uiLang).toBe("en");
    expect(localStorage.getItem("zoko-lang")).toBe("en");
    expect(i18n.global.locale.value).toBe("en");
    prefs.toggle();
    expect(prefs.uiLang).toBe("zh");
  });

  it("reads persisted language on init", () => {
    localStorage.setItem("zoko-lang", "en");
    freshPinia();
    expect(usePrefsStore().uiLang).toBe("en");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd h5 && npm run test -- prefs`
Expected: FAIL — cannot resolve `../src/stores/prefs` / `../src/i18n/zh`

- [ ] **Step 3: Create the i18n message files**

`h5/src/i18n/zh.ts`:

```ts
export default {
  appName: "ZokoDaily",
  searchPlaceholder: "搜索新闻",
  cancel: "取消",
  loading: "加载中…",
  noMore: "没有更多了",
  loadError: "加载失败，点击重试",
  retry: "重试",
  empty: "暂无新闻",
  notFound: "内容不存在",
  back: "返回",
  source: "来源",
  share: "分享",
  copyLink: "复制链接",
  copied: "已复制",
  systemShare: "更多",
  wechat: "微信",
  wechatHint: "用微信扫一扫，或复制链接分享",
  categories: {
    politics: "政治",
    business: "商业",
    sports: "体育",
    entertainment: "娱乐",
    society: "社会",
    technology: "科技",
    health: "健康",
  },
};
```

`h5/src/i18n/en.ts`:

```ts
export default {
  appName: "ZokoDaily",
  searchPlaceholder: "Search news",
  cancel: "Cancel",
  loading: "Loading…",
  noMore: "No more articles",
  loadError: "Load failed, tap to retry",
  retry: "Retry",
  empty: "No news yet",
  notFound: "Article not found",
  back: "Back",
  source: "Source",
  share: "Share",
  copyLink: "Copy link",
  copied: "Copied",
  systemShare: "More",
  wechat: "WeChat",
  wechatHint: "Scan with WeChat, or copy the link to share",
  categories: {
    politics: "Politics",
    business: "Business",
    sports: "Sports",
    entertainment: "Entertainment",
    society: "Society",
    technology: "Technology",
    health: "Health",
  },
};
```

- [ ] **Step 4: Replace `h5/src/i18n/index.ts`**

```ts
import { createI18n } from "vue-i18n";

import en from "./en";
import zh from "./zh";

export type UiLang = "zh" | "en";

export function initialLang(): UiLang {
  const stored = localStorage.getItem("zoko-lang");
  return stored === "en" ? "en" : "zh";
}

export const i18n = createI18n({
  legacy: false,
  locale: initialLang(),
  fallbackLocale: "zh",
  messages: { zh, en },
});
```

- [ ] **Step 5: Create `h5/src/stores/prefs.ts`**

```ts
import { defineStore } from "pinia";

import { i18n, initialLang, type UiLang } from "../i18n";

export const usePrefsStore = defineStore("prefs", {
  state: () => ({ uiLang: initialLang() }),
  actions: {
    setLang(lang: UiLang) {
      this.uiLang = lang;
      localStorage.setItem("zoko-lang", lang);
      i18n.global.locale.value = lang;
    },
    toggle() {
      this.setLang(this.uiLang === "zh" ? "en" : "zh");
    },
  },
});
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd h5 && npm run test`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add h5/src/i18n/ h5/src/stores/prefs.ts h5/tests/
git commit -m "feat(h5): i18n messages and persisted UI-language store"
```

---

### Task 3: API layer + feed store

**Files:**
- Create: `h5/src/api/types.ts`, `h5/src/api/client.ts`, `h5/src/api/articles.ts`
- Create: `h5/src/stores/feed.ts`
- Test: `h5/tests/feedStore.spec.ts`

- [ ] **Step 1: Write the failing test — `h5/tests/feedStore.spec.ts`**

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ArticleCard, Paginated } from "../src/api/types";
import { useFeedStore } from "../src/stores/feed";
import { freshPinia } from "./helpers";

vi.mock("../src/api/articles", () => ({ listArticles: vi.fn() }));
import { listArticles } from "../src/api/articles";

const mockList = vi.mocked(listArticles);

function card(id: number): ArticleCard {
  return {
    id,
    title: `Story ${id}`,
    title_zh: `新闻 ${id}`,
    main_image_url: null,
    published_at: "2026-07-10T08:00:00",
    category: "business",
    country: { code: "GH", name_en: "Ghana", name_zh: "加纳", flag_emoji: "🇬🇭" },
  };
}

function page(items: ArticleCard[], pageNo: number, total: number): Paginated<ArticleCard> {
  return { items, total, page: pageNo, page_size: 2 };
}

describe("feed store", () => {
  beforeEach(() => {
    freshPinia();
    mockList.mockReset();
  });

  it("refresh loads page 1", async () => {
    mockList.mockResolvedValueOnce(page([card(1), card(2)], 1, 3));
    const feed = useFeedStore();
    await feed.refresh();
    expect(mockList).toHaveBeenCalledWith({ page: 1, page_size: 20, search: undefined });
    expect(feed.items).toHaveLength(2);
    expect(feed.finished).toBe(false);
  });

  it("loadMore appends and finishes at total", async () => {
    mockList
      .mockResolvedValueOnce(page([card(1), card(2)], 1, 3))
      .mockResolvedValueOnce(page([card(3)], 2, 3));
    const feed = useFeedStore();
    await feed.refresh();
    await feed.loadMore();
    expect(feed.items.map((a) => a.id)).toEqual([1, 2, 3]);
    expect(feed.finished).toBe(true);
  });

  it("search resets and passes the keyword", async () => {
    mockList.mockResolvedValue(page([card(9)], 1, 1));
    const feed = useFeedStore();
    await feed.search("  外汇  ");
    expect(mockList).toHaveBeenCalledWith({ page: 1, page_size: 20, search: "外汇" });
    expect(feed.items.map((a) => a.id)).toEqual([9]);
  });

  it("records error message on failure", async () => {
    mockList.mockRejectedValueOnce(new Error("Network error"));
    const feed = useFeedStore();
    await feed.refresh();
    expect(feed.error).toBe("Network error");
    expect(feed.loading).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd h5 && npm run test -- feedStore`
Expected: FAIL — cannot resolve `../src/stores/feed` / `../src/api/types`

- [ ] **Step 3: Create the API layer**

`h5/src/api/types.ts`:

```ts
export interface CountryInfo {
  code: string;
  name_en: string;
  name_zh: string;
  flag_emoji: string;
}

export interface ArticleCard {
  id: number;
  title: string;
  title_zh: string | null;
  main_image_url: string | null;
  published_at: string | null;
  category: string | null;
  country: CountryInfo;
}

export interface ArticleDetail extends ArticleCard {
  source_language: "en" | "fr";
  paragraphs: string[];
  paragraphs_zh: string[] | null;
  site: { name: string; url: string };
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export type ContentMode = "source" | "zh" | "bilingual";
```

`h5/src/api/client.ts`:

```ts
import axios from "axios";

export const api = axios.create({ baseURL: "/api/public", timeout: 15000 });

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const message =
      error?.response?.data?.detail ?? error?.message ?? "Network error";
    return Promise.reject(new Error(String(message)));
  },
);
```

`h5/src/api/articles.ts`:

```ts
import { api } from "./client";
import type { ArticleCard, ArticleDetail, Paginated } from "./types";

export interface ListParams {
  page?: number;
  page_size?: number;
  search?: string;
  country?: string;
  category?: string;
}

export async function listArticles(params: ListParams): Promise<Paginated<ArticleCard>> {
  const { data } = await api.get<Paginated<ArticleCard>>("/articles", { params });
  return data;
}

export async function getBanner(): Promise<ArticleCard[]> {
  const { data } = await api.get<ArticleCard[]>("/articles/banner");
  return data;
}

export async function getArticle(id: number | string): Promise<ArticleDetail> {
  const { data } = await api.get<ArticleDetail>(`/articles/${id}`);
  return data;
}
```

- [ ] **Step 4: Create `h5/src/stores/feed.ts`**

```ts
import { defineStore } from "pinia";

import { listArticles } from "../api/articles";
import type { ArticleCard } from "../api/types";

const PAGE_SIZE = 20;

export const useFeedStore = defineStore("feed", {
  state: () => ({
    items: [] as ArticleCard[],
    page: 0,
    total: 0,
    keyword: "",
    loading: false,
    error: "",
  }),
  getters: {
    finished: (s) => s.page > 0 && s.items.length >= s.total,
  },
  actions: {
    async refresh() {
      this.page = 0;
      this.total = 0;
      this.items = [];
      await this.loadMore();
    },
    async loadMore() {
      if (this.loading) return;
      this.loading = true;
      this.error = "";
      try {
        const data = await listArticles({
          page: this.page + 1,
          page_size: PAGE_SIZE,
          search: this.keyword || undefined,
        });
        this.page = data.page;
        this.total = data.total;
        this.items.push(...data.items);
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e);
      } finally {
        this.loading = false;
      }
    },
    async search(keyword: string) {
      this.keyword = keyword.trim();
      await this.refresh();
    },
  },
});
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd h5 && npm run test`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add h5/src/api/ h5/src/stores/feed.ts h5/tests/feedStore.spec.ts
git commit -m "feat(h5): typed API layer and paginated feed store"
```

---

### Task 4: CountryTag + NewsCard

**Files:**
- Create: `h5/src/components/CountryTag.vue`, `h5/src/components/NewsCard.vue`
- Test: `h5/tests/newsCard.spec.ts`

- [ ] **Step 1: Write the failing test — `h5/tests/newsCard.spec.ts`**

```ts
import { RouterLinkStub, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { ArticleCard } from "../src/api/types";
import NewsCard from "../src/components/NewsCard.vue";
import { usePrefsStore } from "../src/stores/prefs";
import { freshPinia, testI18n } from "./helpers";

const article: ArticleCard = {
  id: 7,
  title: "Bank of Ghana unveils policy",
  title_zh: "加纳央行宣布政策",
  main_image_url: null,
  published_at: "2026-07-09T10:30:00",
  category: "business",
  country: { code: "GH", name_en: "Ghana", name_zh: "加纳", flag_emoji: "🇬🇭" },
};

function mountCard(a: ArticleCard, lang: "zh" | "en") {
  const pinia = freshPinia();
  usePrefsStore().setLang(lang);
  return mount(NewsCard, {
    props: { article: a },
    global: { plugins: [pinia, testI18n(lang)], stubs: { RouterLink: RouterLinkStub } },
  });
}

describe("NewsCard", () => {
  it("shows zh headline and zh country name in zh mode", () => {
    const w = mountCard(article, "zh");
    expect(w.text()).toContain("加纳央行宣布政策");
    expect(w.text()).toContain("加纳");
    expect(w.text()).toContain("07-09");
  });

  it("shows source headline and en country name in en mode", () => {
    const w = mountCard(article, "en");
    expect(w.text()).toContain("Bank of Ghana unveils policy");
    expect(w.text()).toContain("Ghana");
  });

  it("falls back to source title when title_zh is null", () => {
    const w = mountCard({ ...article, title_zh: null }, "zh");
    expect(w.text()).toContain("Bank of Ghana unveils policy");
  });

  it("links to the article detail route", () => {
    const w = mountCard(article, "zh");
    expect(w.findComponent(RouterLinkStub).props("to")).toBe("/article/7");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd h5 && npm run test -- newsCard`
Expected: FAIL — cannot resolve `../src/components/NewsCard.vue`

- [ ] **Step 3: Create `h5/src/components/CountryTag.vue`**

```vue
<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import type { CountryInfo } from "../api/types";

const props = defineProps<{ country: CountryInfo }>();
const { locale } = useI18n();
const name = computed(() =>
  locale.value === "zh" ? props.country.name_zh : props.country.name_en,
);
</script>

<template>
  <span class="country-tag">
    <span class="flag">{{ country.flag_emoji }}</span>
    <span>{{ name }}</span>
  </span>
</template>

<style scoped>
.country-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: var(--text-muted);
}
.flag {
  font-size: 12px;
  line-height: 1;
}
</style>
```

- [ ] **Step 4: Create `h5/src/components/NewsCard.vue`**

```vue
<script setup lang="ts">
import { computed, ref } from "vue";

import type { ArticleCard } from "../api/types";
import { usePrefsStore } from "../stores/prefs";
import CountryTag from "./CountryTag.vue";

const props = defineProps<{ article: ArticleCard }>();
const prefs = usePrefsStore();
const imgFailed = ref(false);

const headline = computed(() =>
  prefs.uiLang === "zh"
    ? props.article.title_zh || props.article.title
    : props.article.title,
);
const dateLabel = computed(() =>
  props.article.published_at ? props.article.published_at.slice(5, 10) : "",
);
</script>

<template>
  <router-link :to="`/article/${article.id}`" class="card">
    <div class="thumb">
      <img
        v-if="article.main_image_url && !imgFailed"
        :src="article.main_image_url"
        alt=""
        loading="lazy"
        @error="imgFailed = true"
      />
      <div v-else class="thumb-placeholder" />
    </div>
    <div class="body">
      <h3 class="headline">{{ headline }}</h3>
      <p class="meta">
        <CountryTag :country="article.country" />
        <span class="date">{{ dateLabel }}</span>
      </p>
    </div>
  </router-link>
</template>

<style scoped>
.card {
  display: block;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  overflow: hidden;
}
.thumb {
  aspect-ratio: 16 / 10;
  background: var(--surface);
}
.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.thumb-placeholder {
  width: 100%;
  height: 100%;
  background: var(--surface);
}
.body {
  padding: 8px;
}
.headline {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 6px;
}
.meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-muted);
}
</style>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd h5 && npm run test`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add h5/src/components/CountryTag.vue h5/src/components/NewsCard.vue h5/tests/newsCard.spec.ts
git commit -m "feat(h5): country tag and news card with UI-language headline"
```

---

### Task 5: ContentLangToggle + ArticleBody

**Files:**
- Create: `h5/src/components/ContentLangToggle.vue`, `h5/src/components/ArticleBody.vue`
- Test: `h5/tests/contentLangToggle.spec.ts`, `h5/tests/articleBody.spec.ts`

- [ ] **Step 1: Write the failing tests**

`h5/tests/contentLangToggle.spec.ts`:

```ts
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ContentLangToggle from "../src/components/ContentLangToggle.vue";

describe("ContentLangToggle", () => {
  it("shows EN labels for English sources", () => {
    const w = mount(ContentLangToggle, {
      props: { sourceLang: "en", modelValue: "source", hasTranslation: true },
    });
    expect(w.findAll(".seg").map((s) => s.text())).toEqual(["EN", "中", "双语"]);
  });

  it("shows FR labels for French sources", () => {
    const w = mount(ContentLangToggle, {
      props: { sourceLang: "fr", modelValue: "source", hasTranslation: true },
    });
    expect(w.findAll(".seg")[0].text()).toBe("FR");
  });

  it("hides zh segments when there is no translation", () => {
    const w = mount(ContentLangToggle, {
      props: { sourceLang: "en", modelValue: "source", hasTranslation: false },
    });
    expect(w.findAll(".seg")).toHaveLength(1);
  });

  it("emits the selected mode and marks it active", async () => {
    const w = mount(ContentLangToggle, {
      props: { sourceLang: "en", modelValue: "source", hasTranslation: true },
    });
    await w.findAll(".seg")[2].trigger("click");
    expect(w.emitted("update:modelValue")![0]).toEqual(["bilingual"]);
    await w.setProps({ modelValue: "bilingual" });
    expect(w.findAll(".seg")[2].classes()).toContain("active");
  });
});
```

`h5/tests/articleBody.spec.ts`:

```ts
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ArticleBody from "../src/components/ArticleBody.vue";

const paragraphs = ["First source para.", "Second source para."];
const paragraphsZh = ["第一段。", "第二段。"];

describe("ArticleBody", () => {
  it("renders source paragraphs in source mode", () => {
    const w = mount(ArticleBody, {
      props: { paragraphs, paragraphsZh, mode: "source" },
    });
    expect(w.findAll("p").map((p) => p.text())).toEqual(paragraphs);
  });

  it("renders zh paragraphs in zh mode", () => {
    const w = mount(ArticleBody, {
      props: { paragraphs, paragraphsZh, mode: "zh" },
    });
    expect(w.findAll("p").map((p) => p.text())).toEqual(paragraphsZh);
  });

  it("interleaves source and zh in bilingual mode, zh styled as translation", () => {
    const w = mount(ArticleBody, {
      props: { paragraphs, paragraphsZh, mode: "bilingual" },
    });
    const texts = w.findAll("p").map((p) => p.text());
    expect(texts).toEqual(["First source para.", "第一段。", "Second source para.", "第二段。"]);
    expect(w.findAll("p")[1].classes()).toContain("zh-trans");
    expect(w.findAll("p")[0].classes()).not.toContain("zh-trans");
  });

  it("falls back to source when zh requested but missing", () => {
    const w = mount(ArticleBody, {
      props: { paragraphs, paragraphsZh: null, mode: "zh" },
    });
    expect(w.findAll("p").map((p) => p.text())).toEqual(paragraphs);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd h5 && npm run test`
Expected: FAIL — cannot resolve the two new components

- [ ] **Step 3: Create `h5/src/components/ContentLangToggle.vue`**

```vue
<script setup lang="ts">
import { computed } from "vue";

import type { ContentMode } from "../api/types";

const props = defineProps<{
  sourceLang: "en" | "fr";
  modelValue: ContentMode;
  hasTranslation: boolean;
}>();
const emit = defineEmits<{ "update:modelValue": [ContentMode] }>();

const segments = computed(() => {
  const base: { key: ContentMode; label: string }[] = [
    { key: "source", label: props.sourceLang.toUpperCase() },
  ];
  if (props.hasTranslation) {
    base.push({ key: "zh", label: "中" }, { key: "bilingual", label: "双语" });
  }
  return base;
});
</script>

<template>
  <div class="toggle">
    <button
      v-for="seg in segments"
      :key="seg.key"
      type="button"
      class="seg"
      :class="{ active: seg.key === modelValue }"
      @click="emit('update:modelValue', seg.key)"
    >
      {{ seg.label }}
    </button>
  </div>
</template>

<style scoped>
.toggle {
  display: inline-flex;
  background: var(--brand-900);
  border-radius: var(--radius-pill);
  padding: 2px;
}
.seg {
  border: 0;
  background: transparent;
  color: var(--brand-200);
  font-size: 11px;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  min-height: 24px;
}
.seg.active {
  background: var(--brand-50);
  color: var(--brand-900);
  font-weight: 500;
}
</style>
```

- [ ] **Step 4: Create `h5/src/components/ArticleBody.vue`**

```vue
<script setup lang="ts">
import type { ContentMode } from "../api/types";

defineProps<{
  paragraphs: string[];
  paragraphsZh: string[] | null;
  mode: ContentMode;
}>();
</script>

<template>
  <div class="article-body">
    <template v-if="mode === 'zh' && paragraphsZh">
      <p v-for="(p, i) in paragraphsZh" :key="`zh-${i}`" class="para">{{ p }}</p>
    </template>
    <template v-else-if="mode === 'bilingual' && paragraphsZh">
      <template v-for="(p, i) in paragraphs" :key="`bl-${i}`">
        <p class="para">{{ p }}</p>
        <p class="para zh-trans">{{ paragraphsZh[i] }}</p>
      </template>
    </template>
    <template v-else>
      <p v-for="(p, i) in paragraphs" :key="`src-${i}`" class="para">{{ p }}</p>
    </template>
  </div>
</template>

<style scoped>
.para {
  font-size: 15px;
  line-height: 1.65;
  margin-bottom: 12px;
}
.zh-trans {
  color: var(--text-secondary);
  border-left: 2px solid var(--border);
  border-radius: 0;
  padding-left: 8px;
}
</style>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd h5 && npm run test`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add h5/src/components/ContentLangToggle.vue h5/src/components/ArticleBody.vue h5/tests/
git commit -m "feat(h5): content-language toggle and bilingual article body"
```

---

### Task 6: AppHeader + BannerCarousel + NewsGrid + HomeView

**Files:**
- Create: `h5/src/components/AppHeader.vue`, `h5/src/components/BannerCarousel.vue`, `h5/src/components/NewsGrid.vue`
- Replace: `h5/src/views/HomeView.vue`
- Test: `h5/tests/appHeader.spec.ts`

- [ ] **Step 1: Write the failing test — `h5/tests/appHeader.spec.ts`**

```ts
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AppHeader from "../src/components/AppHeader.vue";
import { usePrefsStore } from "../src/stores/prefs";
import { freshPinia, testI18n } from "./helpers";

function mountHeader() {
  const pinia = freshPinia();
  return {
    w: mount(AppHeader, { global: { plugins: [pinia, testI18n("zh")] } }),
    prefs: usePrefsStore(),
  };
}

describe("AppHeader", () => {
  it("shows the wordmark and lang pill", () => {
    const { w } = mountHeader();
    expect(w.text()).toContain("ZokoDaily");
    expect(w.find(".lang-pill").exists()).toBe(true);
  });

  it("lang pill toggles the UI language", async () => {
    const { w, prefs } = mountHeader();
    await w.find(".lang-pill").trigger("click");
    expect(prefs.uiLang).toBe("en");
  });

  it("search expands, submits keyword, and cancel clears", async () => {
    const { w } = mountHeader();
    await w.find(".search-btn").trigger("click");
    const input = w.find("input");
    expect(input.exists()).toBe(true);
    await input.setValue("外汇");
    await input.trigger("keyup.enter");
    expect(w.emitted("search")![0]).toEqual(["外汇"]);
    await w.find(".cancel-btn").trigger("click");
    expect(w.find("input").exists()).toBe(false);
    expect(w.emitted("search")![1]).toEqual([""]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd h5 && npm run test -- appHeader`
Expected: FAIL — cannot resolve `../src/components/AppHeader.vue`

- [ ] **Step 3: Create `h5/src/components/AppHeader.vue`**

```vue
<script setup lang="ts">
import { nextTick, ref } from "vue";
import { useI18n } from "vue-i18n";

import { usePrefsStore } from "../stores/prefs";

const emit = defineEmits<{ search: [string] }>();
const { t } = useI18n();
const prefs = usePrefsStore();

const searching = ref(false);
const keyword = ref("");
const inputEl = ref<HTMLInputElement | null>(null);

async function openSearch() {
  searching.value = true;
  await nextTick();
  inputEl.value?.focus();
}

function submit() {
  emit("search", keyword.value.trim());
}

function cancel() {
  searching.value = false;
  keyword.value = "";
  emit("search", "");
}
</script>

<template>
  <header class="header hairline">
    <template v-if="!searching">
      <span class="logo" aria-hidden="true"></span>
      <span class="wordmark">{{ t("appName") }}</span>
      <span class="spacer" />
      <button type="button" class="lang-pill" @click="prefs.toggle()">中 / EN</button>
      <button type="button" class="search-btn" :aria-label="t('searchPlaceholder')" @click="openSearch">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
      </button>
    </template>
    <template v-else>
      <input
        ref="inputEl"
        v-model="keyword"
        class="search-input"
        type="search"
        :placeholder="t('searchPlaceholder')"
        @keyup.enter="submit"
      />
      <button type="button" class="cancel-btn" @click="cancel">{{ t("cancel") }}</button>
    </template>
  </header>
</template>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  background: var(--bg);
}
.logo {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  background: var(--brand-500);
}
.wordmark {
  font-size: 15px;
  font-weight: 500;
}
.spacer {
  flex: 1;
}
.lang-pill {
  font-size: 11px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  padding: 4px 10px;
  background: transparent;
  color: var(--text-secondary);
  min-height: 24px;
}
.search-btn,
.cancel-btn {
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  min-width: 40px;
  min-height: 24px;
  justify-content: center;
}
.cancel-btn {
  font-size: 13px;
}
.search-input {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  padding: 6px 12px;
  font-size: 14px;
  background: var(--surface);
  outline: none;
}
</style>
```

- [ ] **Step 4: Create `h5/src/components/BannerCarousel.vue`**

```vue
<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import type { ArticleCard } from "../api/types";
import { usePrefsStore } from "../stores/prefs";

const props = defineProps<{ items: ArticleCard[] }>();
const router = useRouter();
const prefs = usePrefsStore();
const current = ref(0);

const headlines = computed(() =>
  props.items.map((a) =>
    prefs.uiLang === "zh" ? a.title_zh || a.title : a.title,
  ),
);

function open(a: ArticleCard) {
  router.push(`/article/${a.id}`);
}
</script>

<template>
  <van-swipe
    v-if="items.length"
    class="banner"
    :autoplay="5000"
    :show-indicators="false"
    @change="(i: number) => (current = i)"
  >
    <van-swipe-item v-for="(a, i) in items" :key="a.id" @click="open(a)">
      <div class="slide">
        <img v-if="a.main_image_url" :src="a.main_image_url" alt="" />
        <div class="scrim">
          <p class="headline">{{ headlines[i] }}</p>
          <div class="dashes">
            <span
              v-for="(_, d) in items"
              :key="d"
              class="dash"
              :class="{ active: d === current }"
            />
          </div>
        </div>
      </div>
    </van-swipe-item>
  </van-swipe>
</template>

<style scoped>
.banner {
  height: 40vw;
  max-height: 220px;
}
.slide {
  position: relative;
  width: 100%;
  height: 100%;
  background: var(--brand-700);
  overflow: hidden;
}
.slide img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.scrim {
  position: absolute;
  inset: auto 0 0 0;
  padding: 24px 12px 10px;
  background: linear-gradient(transparent, rgba(8, 80, 65, 0.85));
}
.headline {
  color: var(--brand-50);
  font-size: 14px;
  font-weight: 500;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.dashes {
  display: flex;
  gap: 4px;
  margin-top: 8px;
}
.dash {
  width: 6px;
  height: 3px;
  border-radius: 2px;
  background: var(--brand-700);
  transition: width 0.2s;
}
.dash.active {
  width: 14px;
  background: var(--brand-200);
}
</style>
```

- [ ] **Step 5: Create `h5/src/components/NewsGrid.vue`**

```vue
<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import { useFeedStore } from "../stores/feed";
import NewsCard from "./NewsCard.vue";

const { t } = useI18n();
const feed = useFeedStore();

const listLoading = computed({
  get: () => feed.loading,
  set: (v: boolean) => {
    feed.loading = v;
  },
});
</script>

<template>
  <van-list
    v-model:loading="listLoading"
    :finished="feed.finished"
    :error="!!feed.error"
    :finished-text="feed.items.length ? t('noMore') : ''"
    :error-text="t('loadError')"
    @load="feed.loadMore()"
    @update:error="feed.error = ''"
  >
    <div class="grid">
      <NewsCard v-for="a in feed.items" :key="a.id" :article="a" />
    </div>
    <p v-if="feed.finished && !feed.items.length" class="empty">{{ t("empty") }}</p>
  </van-list>
</template>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding: 12px;
}
.empty {
  text-align: center;
  color: var(--text-muted);
  padding: 40px 0;
  font-size: 13px;
}
</style>
```

- [ ] **Step 6: Replace `h5/src/views/HomeView.vue`**

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";

import { getBanner } from "../api/articles";
import type { ArticleCard } from "../api/types";
import AppHeader from "../components/AppHeader.vue";
import BannerCarousel from "../components/BannerCarousel.vue";
import NewsGrid from "../components/NewsGrid.vue";
import { useFeedStore } from "../stores/feed";

const feed = useFeedStore();
const banner = ref<ArticleCard[]>([]);
const refreshing = ref(false);

async function loadBanner() {
  try {
    banner.value = await getBanner();
  } catch {
    banner.value = [];
  }
}

async function onRefresh() {
  await Promise.all([loadBanner(), feed.refresh()]);
  refreshing.value = false;
}

function onSearch(keyword: string) {
  feed.search(keyword);
}

onMounted(() => {
  loadBanner();
  if (!feed.items.length) feed.refresh();
});
</script>

<template>
  <div class="home">
    <AppHeader @search="onSearch" />
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <BannerCarousel v-if="!feed.keyword" :items="banner" />
      <NewsGrid />
    </van-pull-refresh>
  </div>
</template>

<style scoped>
.home {
  min-height: 100vh;
  background: var(--surface);
}
</style>
```

- [ ] **Step 7: Register Vant components — modify `h5/src/main.ts`** (full file after edit)

```ts
import { createPinia } from "pinia";
import { List, Popup, PullRefresh, Swipe, SwipeItem } from "vant";
import { createApp } from "vue";
import "vant/lib/index.css";

import App from "./App.vue";
import { i18n } from "./i18n";
import { router } from "./router";
import "./styles/tokens.css";
import "./styles/base.css";

createApp(App)
  .use(createPinia())
  .use(router)
  .use(i18n)
  .use(Swipe)
  .use(SwipeItem)
  .use(PullRefresh)
  .use(List)
  .use(Popup)
  .mount("#app");
```

- [ ] **Step 8: Delete the scaffold smoke test**

The real `HomeView` now requires pinia, i18n, and Vant plugins, so Task 1's bare-mount
smoke test no longer applies — `h5/tests/appHeader.spec.ts` supersedes it:

```bash
rm h5/tests/smoke.spec.ts
```

- [ ] **Step 9: Run tests, then eyeball in the dev server**

Run: `cd h5 && npm run test`
Expected: all pass

Run: `cd h5 && npm run dev` with the backend running on `:8000` (see Task 8 Step 1 for backend startup) — homepage shows header, banner, and the two-column grid.

- [ ] **Step 10: Commit**

```bash
git add h5/src/ h5/tests/appHeader.spec.ts
git commit -m "feat(h5): homepage with header, banner carousel, and infinite news grid"
```

---

### Task 7: ShareSheet + ArticleView

**Files:**
- Create: `h5/src/components/ShareSheet.vue`
- Replace: `h5/src/views/ArticleView.vue`

- [ ] **Step 1: Create `h5/src/components/ShareSheet.vue`**

```vue
<script setup lang="ts">
import QRCode from "qrcode";
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps<{ show: boolean; title: string }>();
const emit = defineEmits<{ "update:show": [boolean] }>();
const { t } = useI18n();

const wechatPane = ref(false);
const qrDataUrl = ref("");
const copied = ref(false);

const pageUrl = () => window.location.href;

function openFacebook() {
  window.open(
    `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(pageUrl())}`,
    "_blank",
  );
}

function openWhatsApp() {
  window.open(
    `https://wa.me/?text=${encodeURIComponent(`${props.title} ${pageUrl()}`)}`,
    "_blank",
  );
}

async function openWeChat() {
  qrDataUrl.value = await QRCode.toDataURL(pageUrl(), { margin: 1, width: 180 });
  wechatPane.value = true;
}

async function copyLink() {
  try {
    await navigator.clipboard.writeText(pageUrl());
  } catch {
    const ta = document.createElement("textarea");
    ta.value = pageUrl();
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  copied.value = true;
  setTimeout(() => (copied.value = false), 1500);
}

function systemShare() {
  navigator.share?.({ title: props.title, url: pageUrl() });
}

watch(
  () => props.show,
  (open) => {
    if (!open) wechatPane.value = false;
  },
);
</script>

<template>
  <van-popup
    :show="show"
    position="bottom"
    round
    @update:show="(v: boolean) => emit('update:show', v)"
  >
    <div class="sheet">
      <template v-if="!wechatPane">
        <p class="sheet-title">{{ t("share") }}</p>
        <div class="row">
          <button type="button" class="item" @click="openFacebook">Facebook</button>
          <button type="button" class="item" @click="openWhatsApp">WhatsApp</button>
          <button type="button" class="item" @click="openWeChat">{{ t("wechat") }}</button>
          <button type="button" class="item" @click="copyLink">
            {{ copied ? t("copied") : t("copyLink") }}
          </button>
          <button v-if="'share' in navigator" type="button" class="item" @click="systemShare">
            {{ t("systemShare") }}
          </button>
        </div>
      </template>
      <template v-else>
        <p class="sheet-title">{{ t("wechatHint") }}</p>
        <img v-if="qrDataUrl" :src="qrDataUrl" alt="QR" class="qr" />
        <button type="button" class="item wide" @click="copyLink">
          {{ copied ? t("copied") : t("copyLink") }}
        </button>
      </template>
    </div>
  </van-popup>
</template>

<style scoped>
.sheet {
  padding: 16px 16px 28px;
  text-align: center;
}
.sheet-title {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 14px;
}
.row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}
.item {
  border: 1px solid var(--border);
  background: var(--bg);
  border-radius: var(--radius-card);
  padding: 10px 14px;
  font-size: 13px;
  min-height: 40px;
}
.item.wide {
  margin-top: 12px;
}
.qr {
  margin: 0 auto 4px;
  width: 180px;
  height: 180px;
}
</style>
```

- [ ] **Step 2: Replace `h5/src/views/ArticleView.vue`**

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { getArticle } from "../api/articles";
import type { ArticleDetail, ContentMode } from "../api/types";
import ArticleBody from "../components/ArticleBody.vue";
import ContentLangToggle from "../components/ContentLangToggle.vue";
import CountryTag from "../components/CountryTag.vue";
import ShareSheet from "../components/ShareSheet.vue";

const route = useRoute();
const router = useRouter();
const { t } = useI18n();

const article = ref<ArticleDetail | null>(null);
const error = ref("");
const mode = ref<ContentMode>("source");
const showShare = ref(false);
const imgFailed = ref(false);

const hasTranslation = computed(
  () => !!article.value?.paragraphs_zh && !!article.value?.title_zh,
);
const categoryLabel = computed(() => {
  const c = article.value?.category;
  return c ? t(`categories.${c}`) : "";
});
const dateLabel = computed(() =>
  article.value?.published_at ? article.value.published_at.slice(0, 10) : "",
);
const showSourceTitle = computed(() => mode.value !== "zh");
const showZhTitle = computed(
  () => hasTranslation.value && mode.value !== "source",
);

function goBack() {
  if (window.history.length > 1) router.back();
  else router.push("/");
}

onMounted(async () => {
  try {
    article.value = await getArticle(String(route.params.id));
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  }
});
</script>

<template>
  <div class="detail">
    <header class="bar hairline">
      <button type="button" class="back" :aria-label="t('back')" @click="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </button>
      <span v-if="article" class="crumb">
        <CountryTag :country="article.country" />
        <span v-if="categoryLabel"> · {{ categoryLabel }}</span>
      </span>
      <span class="spacer" />
      <button type="button" class="share" :aria-label="t('share')" @click="showShare = true">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="6" cy="12" r="2.5" /><circle cx="17" cy="6" r="2.5" /><circle cx="17" cy="18" r="2.5" />
          <path d="M8.2 10.8l6.6-3.6M8.2 13.2l6.6 3.6" />
        </svg>
      </button>
    </header>

    <div v-if="error" class="state">
      <p>{{ t("notFound") }}</p>
      <button type="button" class="retry" @click="goBack">{{ t("back") }}</button>
    </div>

    <template v-else-if="article">
      <div class="hero">
        <img
          v-if="article.main_image_url && !imgFailed"
          :src="article.main_image_url"
          alt=""
          @error="imgFailed = true"
        />
        <ContentLangToggle
          v-model="mode"
          class="toggle"
          :source-lang="article.source_language"
          :has-translation="hasTranslation"
        />
      </div>

      <div class="content">
        <p class="meta">
          <CountryTag :country="article.country" />
          <span v-if="categoryLabel"> · {{ categoryLabel }}</span>
          <span v-if="dateLabel"> · {{ dateLabel }}</span>
        </p>
        <h1 v-if="showSourceTitle" class="title">{{ article.title }}</h1>
        <h2 v-if="showZhTitle" class="title-zh">{{ article.title_zh }}</h2>
        <p class="source-line">
          {{ t("source") }}
          <a :href="article.site.url" target="_blank" rel="noopener">{{ article.site.name }}</a>
        </p>
        <ArticleBody
          :paragraphs="article.paragraphs"
          :paragraphs-zh="article.paragraphs_zh"
          :mode="mode"
        />
      </div>

      <ShareSheet v-model:show="showShare" :title="article.title" />
    </template>
  </div>
</template>

<style scoped>
.detail {
  min-height: 100vh;
  background: var(--bg);
}
.bar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  background: var(--bg);
}
.back,
.share {
  border: 0;
  background: transparent;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  min-width: 40px;
  min-height: 24px;
}
.crumb {
  font-size: 12.5px;
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
}
.spacer {
  flex: 1;
}
.hero {
  position: relative;
  background: var(--brand-700);
  min-height: 120px;
}
.hero img {
  width: 100%;
  max-height: 240px;
  object-fit: cover;
}
.toggle {
  position: absolute;
  top: 8px;
  right: 8px;
}
.content {
  padding: 12px 14px 24px;
}
.meta {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
  display: flex;
  align-items: center;
}
.title {
  font-size: 17px;
  font-weight: 500;
  line-height: 1.45;
  margin-bottom: 4px;
}
.title-zh {
  font-size: 15px;
  font-weight: 500;
  line-height: 1.45;
  color: var(--text-secondary);
  margin-bottom: 4px;
}
.source-line {
  font-size: 12px;
  margin: 6px 0 14px;
}
.source-line a {
  color: var(--brand-500);
}
.state {
  padding: 80px 20px;
  text-align: center;
  color: var(--text-muted);
}
.retry {
  margin-top: 12px;
  border: 1px solid var(--border);
  background: var(--bg);
  border-radius: var(--radius-pill);
  padding: 6px 20px;
  font-size: 13px;
}
</style>
```

- [ ] **Step 3: Run the full test suite**

Run: `cd h5 && npm run test`
Expected: all pass (no new unit tests — this task's routing/share flows are covered by Task 8's live verification)

- [ ] **Step 4: Commit**

```bash
git add h5/src/
git commit -m "feat(h5): article detail with bilingual toggle and share sheet"
```

---

### Task 8: Type gate, build, live verification

**Files:** none created.

- [ ] **Step 1: Start the backend with fixture data**

```bash
cd backend
rm -f live.db
DATABASE_URL="sqlite:///./live.db" uv run python -m app.seed
DATABASE_URL="sqlite:///./live.db" uv run python -c "
from datetime import datetime, timezone
from app.db import SessionLocal, Base, engine
import app.models
Base.metadata.create_all(engine)
from app.models import Article, Country, Site
db = SessionLocal()
gh = db.query(Country).filter_by(code='GH').one()
sn = db.query(Country).filter_by(code='SN').one()
joy = db.query(Site).filter_by(name='MyJoyOnline').one()
sene = db.query(Site).filter_by(name='Seneweb').one()
for i in range(8):
    db.add(Article(site_id=joy.id, country_id=gh.id,
        source_url=f'https://gh.example/{i}', source_language='en',
        title=f'Ghana economy story number {i}', title_zh=f'加纳经济新闻 {i}',
        category='business', paragraphs=['First paragraph of the story.', 'Second paragraph.'],
        paragraphs_zh=['新闻第一段。', '第二段。'], status='published', is_banner=(i < 3),
        published_at=datetime(2026, 7, 1 + i, tzinfo=timezone.utc)))
db.add(Article(site_id=sene.id, country_id=sn.id,
    source_url='https://sn.example/1', source_language='fr',
    title='Le Sénégal accueille un salon agricole', title_zh='塞内加尔举办农业博览会',
    category='society', paragraphs=['Le salon ouvre ses portes.', 'Deuxième paragraphe.'],
    paragraphs_zh=['博览会开幕。', '第二段。'], status='published',
    published_at=datetime(2026, 7, 9, tzinfo=timezone.utc)))
db.commit(); print('fixtures ready')
"
DATABASE_URL="sqlite:///./live.db" SCHEDULER_ENABLED=false uv run uvicorn app.main:app --port 8000
```

(If Plan 2 is not yet implemented, `SCHEDULER_ENABLED` is simply ignored — that's fine.)

- [ ] **Step 2: Run the dev server and walk the flows**

Run: `cd h5 && npm run dev`, open `http://localhost:5173` in a mobile-emulated browser (390px wide):

1. Homepage: header (logo, ZokoDaily, 中/EN pill, search icon), banner auto-rotating with dash indicator, two-column grid with headlines/flags/dates.
2. Tap 中/EN → UI strings, card headlines, and country names switch; reload → language persisted.
3. Search 外汇 or 加纳 → grid filters; cancel → full feed returns; banner hides while searching.
4. Pull down → refresh spinner, feed reloads. Scroll to bottom → next page loads; end shows 没有更多了.
5. Tap the French article → detail shows FR｜中｜双语 toggle; each mode renders correctly (双语 interleaves with the muted left-rule style); headline follows mode; source line links out.
6. Tap an English article → EN｜中｜双语.
7. Share → sheet shows Facebook / WhatsApp / 微信 / 复制链接 (+ 更多 if supported); WeChat pane shows a QR code; copy shows 已复制.
8. Back button returns to the list (state preserved). Visit `/article/99999` → 内容不存在 with a back button.

- [ ] **Step 3: Full build gate**

Run: `cd h5 && npm run build`
Expected: `vue-tsc --noEmit` passes with zero errors; `dist/` produced.

- [ ] **Step 4: Clean up and commit**

```bash
rm -f backend/live.db
git add h5/
git commit -m "chore(h5): pass type gate and live verification fixes" 
```

(Skip the commit if verification required no code changes.)
