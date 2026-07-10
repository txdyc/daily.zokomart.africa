# ZokoDaily Plan 4: Admin Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The management SPA in `admin/`: login, countries & sites management (with crawl-now), article review/editing with paragraph-alignment safety, pipeline monitoring, and AI translation settings — Chinese UI.

**Architecture:** Vue 3 + TypeScript SPA on Element Plus, served under `/admin/`. One pinia store (auth); every page owns its own fetch state. A thin axios layer adds the JWT and normalizes errors (401 → login redirect, 409/422 → warning toast). Unit tests cover only the logic that can silently corrupt data or lock the user out: paragraph join/split and the auth guard/interceptor; the Element Plus CRUD screens are verified live in Task 8.

**Tech Stack:** Vue 3, Vite 5, TypeScript, Element Plus (zh-cn locale), Pinia, vue-router 4, axios, vitest + @vue/test-utils (jsdom).

**Spec:** `docs/superpowers/specs/2026-07-10-admin-frontend-design.md` (parent §8 in the main design spec).
**Working directory:** all commands run from `admin/` unless stated otherwise.
**Backend dependency:** everything works against the Plan 1 backend; the Pipeline page and the crawl-now / test-translation buttons need the Plan 2 endpoints (they 404 gracefully until then — noted in Tasks 4, 6, 7).

---

## File structure created by this plan

```
admin/
├── index.html  package.json  tsconfig.json  vite.config.ts  env.d.ts
├── src/
│   ├── main.ts  App.vue  router.ts
│   ├── api/client.ts  api/types.ts  api/endpoints.ts
│   ├── stores/auth.ts
│   ├── utils/paragraphs.ts
│   ├── layout/AdminLayout.vue
│   └── views/
│       LoginView.vue  SitesView.vue  ArticlesView.vue
│       PipelineView.vue  SettingsView.vue
└── tests/
    paragraphs.spec.ts  auth.spec.ts
```

---

### Task 1: Scaffold — Vite app, Element Plus, router shell

**Files:**
- Create: `admin/package.json`, `admin/tsconfig.json`, `admin/vite.config.ts`, `admin/env.d.ts`, `admin/index.html`
- Create: `admin/src/main.ts`, `admin/src/App.vue`, `admin/src/router.ts`
- Create: `admin/src/views/LoginView.vue` + the four other views as placeholders (replaced in Tasks 3–7)

- [ ] **Step 1: Create `admin/package.json`**

```json
{
  "name": "zokodaily-admin",
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
    "@element-plus/icons-vue": "^2.3.1",
    "axios": "^1.7.2",
    "element-plus": "^2.7.5",
    "pinia": "^2.1.7",
    "vue": "^3.4.29",
    "vue-router": "^4.3.3"
  },
  "devDependencies": {
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

Run: `cd admin && npm install`
Expected: installs cleanly.

- [ ] **Step 2: Create `admin/tsconfig.json`**

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

- [ ] **Step 3: Create `admin/env.d.ts`**

```ts
/// <reference types="vite/client" />
declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<object, object, unknown>;
  export default component;
}
```

- [ ] **Step 4: Create `admin/vite.config.ts`**

```ts
/// <reference types="vitest" />
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  base: "/admin/",
  plugins: [vue()],
  server: {
    port: 5174,
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
```

- [ ] **Step 5: Create `admin/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>ZokoDaily 管理后台</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 6: Create app shell and router**

`admin/src/main.ts`:

```ts
import ElementPlus from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import { createPinia } from "pinia";
import { createApp } from "vue";
import "element-plus/dist/index.css";

import App from "./App.vue";
import { router } from "./router";

createApp(App)
  .use(createPinia())
  .use(router)
  .use(ElementPlus, { locale: zhCn })
  .mount("#app");
```

`admin/src/App.vue`:

```vue
<template>
  <router-view />
</template>
```

`admin/src/router.ts` (auth guard is added in Task 2 — this version has no guard yet):

```ts
import { createRouter, createWebHistory } from "vue-router";

export const router = createRouter({
  history: createWebHistory("/admin/"),
  routes: [
    { path: "/login", name: "login", component: () => import("./views/LoginView.vue") },
    {
      path: "/",
      component: () => import("./layout/AdminLayout.vue"),
      children: [
        { path: "", redirect: "/articles" },
        { path: "articles", name: "articles", component: () => import("./views/ArticlesView.vue") },
        { path: "sites", name: "sites", component: () => import("./views/SitesView.vue") },
        { path: "pipeline", name: "pipeline", component: () => import("./views/PipelineView.vue") },
        { path: "settings", name: "settings", component: () => import("./views/SettingsView.vue") },
      ],
    },
  ],
});
```

- [ ] **Step 7: Create placeholder layout and views** (all replaced by later tasks)

`admin/src/layout/AdminLayout.vue`:

```vue
<template>
  <div><router-view /></div>
</template>
```

`admin/src/views/LoginView.vue`, `SitesView.vue`, `ArticlesView.vue`, `PipelineView.vue`,
`SettingsView.vue` — each with its own name in the template, e.g.:

```vue
<template>
  <div>LoginView placeholder</div>
</template>
```

- [ ] **Step 8: Verify the type gate and dev server**

Run: `cd admin && npm run build`
Expected: `vue-tsc` passes, Vite build emits `dist/`.

Run: `cd admin && npm run dev` then open `http://localhost:5174/admin/articles`
Expected: "ArticlesView placeholder" renders.

- [ ] **Step 9: Commit**

```bash
git add admin/
git commit -m "feat(admin): scaffold Vite app with Element Plus and router shell"
```

---

### Task 2: API layer, auth store, paragraph utils (TDD)

**Files:**
- Create: `admin/src/api/client.ts`, `admin/src/api/types.ts`, `admin/src/api/endpoints.ts`
- Create: `admin/src/stores/auth.ts`, `admin/src/utils/paragraphs.ts`
- Modify: `admin/src/router.ts` (add guard)
- Test: `admin/tests/paragraphs.spec.ts`, `admin/tests/auth.spec.ts`

- [ ] **Step 1: Write the failing tests**

`admin/tests/paragraphs.spec.ts`:

```ts
import { describe, expect, it } from "vitest";

import { joinParagraphs, splitParagraphs } from "../src/utils/paragraphs";

describe("splitParagraphs", () => {
  it("splits on blank lines and trims", () => {
    expect(splitParagraphs("First para.\n\nSecond para.\n\n\nThird para.")).toEqual([
      "First para.",
      "Second para.",
      "Third para.",
    ]);
  });

  it("drops whitespace-only segments", () => {
    expect(splitParagraphs("A\n\n   \n\nB")).toEqual(["A", "B"]);
  });

  it("normalizes CRLF", () => {
    expect(splitParagraphs("A\r\n\r\nB")).toEqual(["A", "B"]);
  });

  it("returns empty array for empty input", () => {
    expect(splitParagraphs("")).toEqual([]);
    expect(splitParagraphs("   ")).toEqual([]);
  });
});

describe("joinParagraphs", () => {
  it("joins with blank lines and round-trips", () => {
    const paragraphs = ["第一段。", "第二段。"];
    expect(splitParagraphs(joinParagraphs(paragraphs))).toEqual(paragraphs);
  });

  it("handles null and undefined", () => {
    expect(joinParagraphs(null)).toBe("");
    expect(joinParagraphs(undefined)).toBe("");
  });
});
```

`admin/tests/auth.spec.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("element-plus", () => ({
  // Cover every named import any view uses — the guard test lazily loads view modules.
  ElMessage: { warning: vi.fn(), error: vi.fn(), success: vi.fn() },
  ElMessageBox: { confirm: vi.fn() },
}));

import { TOKEN_KEY, USER_KEY, handleApiError } from "../src/api/client";
import { router } from "../src/router";

beforeEach(() => {
  localStorage.clear();
});

describe("router guard", () => {
  it("redirects unauthenticated users to login with redirect query", async () => {
    await router.push("/articles");
    expect(router.currentRoute.value.name).toBe("login");
    expect(router.currentRoute.value.query.redirect).toBe("/articles");
  });

  it("lets authenticated users through", async () => {
    localStorage.setItem(TOKEN_KEY, "some-token");
    await router.push("/articles");
    expect(router.currentRoute.value.name).toBe("articles");
  });
});

describe("handleApiError", () => {
  it("clears token and redirects on 401", async () => {
    localStorage.setItem(TOKEN_KEY, "t");
    localStorage.setItem(USER_KEY, "admin");
    const redirect = vi.fn();
    await expect(
      handleApiError({ response: { status: 401, data: {} } }, redirect),
    ).rejects.toBeTruthy();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(USER_KEY)).toBeNull();
    expect(redirect).toHaveBeenCalled();
  });

  it("does not clear token on 409", async () => {
    localStorage.setItem(TOKEN_KEY, "t");
    const redirect = vi.fn();
    await expect(
      handleApiError({ response: { status: 409, data: { detail: "占用" } } }, redirect),
    ).rejects.toBeTruthy();
    expect(localStorage.getItem(TOKEN_KEY)).toBe("t");
    expect(redirect).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd admin && npm run test`
Expected: FAIL — cannot resolve `../src/utils/paragraphs` and `../src/api/client`

- [ ] **Step 3: Create `admin/src/utils/paragraphs.ts`**

```ts
export function splitParagraphs(text: string): string[] {
  return text
    .replace(/\r\n/g, "\n")
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0);
}

export function joinParagraphs(paragraphs: string[] | null | undefined): string {
  return (paragraphs ?? []).join("\n\n");
}
```

- [ ] **Step 4: Create `admin/src/api/client.ts`**

```ts
import axios from "axios";
import { ElMessage } from "element-plus";

export const TOKEN_KEY = "zoko-admin-token";
export const USER_KEY = "zoko-admin-user";

export const api = axios.create({ baseURL: "/api/admin" });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function redirectToLogin(): void {
  if (window.location.pathname.startsWith("/admin/login")) return;
  const current = window.location.pathname.replace(/^\/admin/, "") + window.location.search;
  window.location.href = "/admin/login?redirect=" + encodeURIComponent(current || "/articles");
}

export function handleApiError(
  error: unknown,
  redirect: () => void = redirectToLogin,
): Promise<never> {
  const err = error as { response?: { status?: number; data?: { detail?: unknown } } };
  const status = err.response?.status;
  const detail = err.response?.data?.detail;
  if (status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    redirect();
  } else if (status === 409 || status === 422) {
    ElMessage.warning(typeof detail === "string" ? detail : "数据校验失败");
  } else if (status !== undefined) {
    ElMessage.error("请求失败，请重试");
    console.error(error);
  } else {
    ElMessage.error("网络错误，请检查后端服务");
    console.error(error);
  }
  return Promise.reject(error);
}

api.interceptors.response.use((resp) => resp, (error) => handleApiError(error));
```

Note: login failures also return 401 — the login page calls the API with a **raw axios
instance** (see `endpoints.ts` `login()`) so a wrong password shows an inline error instead
of triggering the global 401 redirect.

- [ ] **Step 5: Create `admin/src/api/types.ts`**

```ts
export interface Country {
  id: number;
  code: string;
  name_en: string;
  name_zh: string;
  flag_emoji: string;
  tier: number;
  enabled: boolean;
}

export interface Site {
  id: number;
  country_id: number;
  name: string;
  base_url: string;
  language: "en" | "fr";
  discovery_method: "rss" | "listing";
  feed_url: string | null;
  listing_url: string | null;
  listing_selector: string | null;
  title_selector: string | null;
  body_selector: string | null;
  image_selector: string | null;
  date_selector: string | null;
  tier: number;
  enabled: boolean;
  last_crawl_at: string | null;
  last_crawl_status: string | null;
  country: Country | null;
}

export type SiteIn = Omit<Site, "id" | "last_crawl_at" | "last_crawl_status" | "country">;

export interface ArticleAdmin {
  id: number;
  site_id: number;
  site_name: string;
  country_code: string;
  source_url: string;
  source_language: string;
  title: string;
  title_zh: string | null;
  category: string | null;
  main_image_url: string | null;
  published_at: string | null;
  paragraphs: string[];
  paragraphs_zh: string[] | null;
  status: string;
  translation_error: string | null;
  is_banner: boolean;
  created_at: string;
}

export interface CrawlRun {
  id: number;
  site_id: number;
  site_name: string;
  started_at: string | null;
  finished_at: string | null;
  status: string;
  articles_found: number;
  articles_new: number;
  error: string | null;
}

export interface AiConfig {
  ai_base_url: string;
  ai_api_key_masked: string;
  ai_model: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export const ARTICLE_STATUSES = [
  { value: "pending_translation", label: "待翻译", tag: "warning" },
  { value: "published", label: "已发布", tag: "success" },
  { value: "translation_failed", label: "翻译失败", tag: "danger" },
  { value: "hidden", label: "已隐藏", tag: "info" },
] as const;

export const CATEGORIES = [
  { value: "politics", label: "政治" },
  { value: "business", label: "商业" },
  { value: "sports", label: "体育" },
  { value: "entertainment", label: "娱乐" },
  { value: "society", label: "社会" },
  { value: "technology", label: "科技" },
  { value: "health", label: "健康" },
] as const;
```

- [ ] **Step 6: Create `admin/src/api/endpoints.ts`**

```ts
import axios from "axios";

import { api } from "./client";
import type {
  AiConfig,
  ArticleAdmin,
  Country,
  CrawlRun,
  Paginated,
  Site,
  SiteIn,
} from "./types";

export async function login(username: string, password: string) {
  const { data } = await axios.post<{ access_token: string }>(
    "/api/admin/auth/login",
    { username, password },
  );
  return data;
}

export async function listCountries(): Promise<Country[]> {
  return (await api.get<Country[]>("/countries")).data;
}
export async function createCountry(body: Omit<Country, "id">): Promise<Country> {
  return (await api.post<Country>("/countries", body)).data;
}
export async function updateCountry(id: number, body: Omit<Country, "id">): Promise<Country> {
  return (await api.put<Country>(`/countries/${id}`, body)).data;
}
export async function deleteCountry(id: number): Promise<void> {
  await api.delete(`/countries/${id}`);
}

export async function listSites(): Promise<Site[]> {
  return (await api.get<Site[]>("/sites")).data;
}
export async function createSite(body: SiteIn): Promise<Site> {
  return (await api.post<Site>("/sites", body)).data;
}
export async function updateSite(id: number, body: SiteIn): Promise<Site> {
  return (await api.put<Site>(`/sites/${id}`, body)).data;
}
export async function deleteSite(id: number): Promise<void> {
  await api.delete(`/sites/${id}`);
}
export async function triggerCrawl(siteId: number): Promise<{ crawl_run_id: number }> {
  return (await api.post<{ crawl_run_id: number }>(`/sites/${siteId}/crawl`)).data;
}

export interface ArticleFilters {
  status?: string;
  country?: string;
  site_id?: number;
  page?: number;
  page_size?: number;
}
export async function listArticles(filters: ArticleFilters): Promise<Paginated<ArticleAdmin>> {
  return (await api.get<Paginated<ArticleAdmin>>("/articles", { params: filters })).data;
}
export async function patchArticle(
  id: number,
  body: Partial<
    Pick<
      ArticleAdmin,
      "title" | "title_zh" | "category" | "main_image_url" | "paragraphs" | "paragraphs_zh" | "is_banner" | "status"
    >
  >,
): Promise<ArticleAdmin> {
  return (await api.patch<ArticleAdmin>(`/articles/${id}`, body)).data;
}
export async function retranslateArticle(id: number): Promise<ArticleAdmin> {
  return (await api.post<ArticleAdmin>(`/articles/${id}/retranslate`)).data;
}
export async function deleteArticle(id: number): Promise<void> {
  await api.delete(`/articles/${id}`);
}

export async function listCrawlRuns(params: {
  site_id?: number;
  page?: number;
  page_size?: number;
}): Promise<Paginated<CrawlRun>> {
  return (await api.get<Paginated<CrawlRun>>("/crawl-runs", { params })).data;
}

export async function getConfig(): Promise<AiConfig> {
  return (await api.get<AiConfig>("/config")).data;
}
export async function updateConfig(body: {
  ai_base_url?: string;
  ai_api_key?: string;
  ai_model?: string;
}): Promise<AiConfig> {
  return (await api.put<AiConfig>("/config", body)).data;
}
export interface TestTranslationResult {
  ok: boolean;
  title_zh?: string;
  paragraph_zh?: string;
  latency_ms?: number;
  error?: string;
}
export async function testTranslation(): Promise<TestTranslationResult> {
  return (await api.post<TestTranslationResult>("/config/test-translation")).data;
}
```

- [ ] **Step 7: Create `admin/src/stores/auth.ts`**

```ts
import { defineStore } from "pinia";

import { TOKEN_KEY, USER_KEY } from "../api/client";
import { login as apiLogin } from "../api/endpoints";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) ?? "",
    username: localStorage.getItem(USER_KEY) ?? "",
  }),
  getters: {
    isLoggedIn: (state) => state.token.length > 0,
  },
  actions: {
    async login(username: string, password: string) {
      const { access_token } = await apiLogin(username, password);
      this.token = access_token;
      this.username = username;
      localStorage.setItem(TOKEN_KEY, access_token);
      localStorage.setItem(USER_KEY, username);
    },
    logout() {
      this.token = "";
      this.username = "";
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    },
  },
});
```

- [ ] **Step 8: Add the guard to `admin/src/router.ts`** (append after `createRouter`)

```ts
import { TOKEN_KEY } from "./api/client";

router.beforeEach((to) => {
  if (to.name !== "login" && !localStorage.getItem(TOKEN_KEY)) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
});
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd admin && npm run test`
Expected: paragraphs (6) + auth (4) all pass

- [ ] **Step 10: Commit**

```bash
git add admin/src/ admin/tests/
git commit -m "feat(admin): API layer, auth store, guard, paragraph utils with tests"
```

---

### Task 3: Login view + admin layout

**Files:**
- Replace: `admin/src/views/LoginView.vue`, `admin/src/layout/AdminLayout.vue`

- [ ] **Step 1: Replace `admin/src/views/LoginView.vue`**

```vue
<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2>ZokoDaily 管理后台</h2>
      <el-form @submit.prevent="submit">
        <el-form-item>
          <el-input v-model="username" placeholder="用户名" autofocus />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" type="password" placeholder="密码" show-password />
        </el-form-item>
        <el-alert
          v-if="error"
          :title="error"
          type="error"
          :closable="false"
          class="login-error"
        />
        <el-button
          type="primary"
          native-type="submit"
          :loading="loading"
          class="login-btn"
        >登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";

const username = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);
const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

async function submit() {
  if (!username.value || !password.value) {
    error.value = "请输入用户名和密码";
    return;
  }
  error.value = "";
  loading.value = true;
  try {
    await auth.login(username.value, password.value);
    router.push((route.query.redirect as string) || "/articles");
  } catch (e) {
    const err = e as { response?: { data?: { detail?: string } } };
    error.value = err.response?.data?.detail ?? "登录失败，请重试";
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
}
.login-card {
  width: 360px;
}
h2 {
  text-align: center;
  margin: 0 0 24px;
  font-weight: 500;
}
.login-error {
  margin-bottom: 12px;
}
.login-btn {
  width: 100%;
}
</style>
```

- [ ] **Step 2: Replace `admin/src/layout/AdminLayout.vue`**

```vue
<template>
  <el-container class="layout">
    <el-aside width="200px" class="aside">
      <div class="logo">ZokoDaily</div>
      <el-menu :default-active="route.path" router class="menu">
        <el-menu-item index="/articles">新闻管理</el-menu-item>
        <el-menu-item index="/sites">国家与站点</el-menu-item>
        <el-menu-item index="/pipeline">抓取与翻译</el-menu-item>
        <el-menu-item index="/settings">系统设置</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="user">{{ auth.username }}</span>
        <el-button link type="primary" @click="logout">退出登录</el-button>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

function logout() {
  auth.logout();
  router.push("/login");
}
</script>

<style scoped>
.layout {
  min-height: 100vh;
}
.aside {
  border-right: 1px solid #e4e7ed;
  background: #fff;
}
.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 500;
  color: #1d9e75;
}
.menu {
  border-right: none;
}
.header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
}
.user {
  color: #606266;
  font-size: 14px;
}
.main {
  background: #f5f7fa;
}
</style>
```

- [ ] **Step 3: Verify live** (needs the backend running: `cd backend && DATABASE_URL="sqlite:///./dev.db" uv run python -m app.seed && DATABASE_URL="sqlite:///./dev.db" SCHEDULER_ENABLED=false uv run uvicorn app.main:app --port 8000`)

Run: `cd admin && npm run dev`, open `http://localhost:5174/admin/`
Expected: redirected to `/admin/login`; wrong password shows inline "Invalid username or
password"; `admin`/`admin123` lands on the articles placeholder inside the sidebar layout;
退出登录 returns to login.

- [ ] **Step 4: Type gate and commit**

Run: `cd admin && npm run build`
Expected: passes.

```bash
git add admin/src/
git commit -m "feat(admin): login view and sidebar layout"
```

---

### Task 4: Countries & sites management

**Files:**
- Replace: `admin/src/views/SitesView.vue`

- [ ] **Step 1: Replace `admin/src/views/SitesView.vue`**

```vue
<template>
  <el-tabs v-model="tab">
    <el-tab-pane label="站点" name="sites">
      <div class="toolbar">
        <el-button type="primary" @click="openSiteDialog()">新增站点</el-button>
        <el-button :loading="loading" @click="loadAll">刷新</el-button>
      </div>
      <el-table v-loading="loading" :data="sites">
        <el-table-column prop="name" label="名称" min-width="130" />
        <el-table-column label="国家" width="130">
          <template #default="{ row }">{{ countryLabel(row.country_id) }}</template>
        </el-table-column>
        <el-table-column prop="language" label="语言" width="70" />
        <el-table-column label="采集方式" width="90">
          <template #default="{ row }">{{ row.discovery_method === "rss" ? "RSS" : "列表页" }}</template>
        </el-table-column>
        <el-table-column prop="tier" label="层级" width="70" />
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch
              :model-value="row.enabled"
              @change="(v: string | number | boolean) => toggleSite(row, Boolean(v))"
            />
          </template>
        </el-table-column>
        <el-table-column label="最近抓取" min-width="180">
          <template #default="{ row }">
            <div v-if="row.last_crawl_status">
              <span :class="{ failed: row.last_crawl_status.startsWith('failed') }">
                {{ row.last_crawl_status }}
              </span>
              <div class="muted">{{ formatTime(row.last_crawl_at) }}</div>
            </div>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="crawlNow(row)">抓取</el-button>
            <el-button link type="primary" @click="openSiteDialog(row)">编辑</el-button>
            <el-button link type="danger" @click="removeSite(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="国家" name="countries">
      <div class="toolbar">
        <el-button type="primary" @click="openCountryDialog()">新增国家</el-button>
      </div>
      <el-table v-loading="loading" :data="countries">
        <el-table-column prop="code" label="代码" width="80" />
        <el-table-column prop="flag_emoji" label="国旗" width="70" />
        <el-table-column prop="name_zh" label="中文名" min-width="110" />
        <el-table-column prop="name_en" label="英文名" min-width="130" />
        <el-table-column prop="tier" label="层级" width="70" />
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch
              :model-value="row.enabled"
              @change="(v: string | number | boolean) => toggleCountry(row, Boolean(v))"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openCountryDialog(row)">编辑</el-button>
            <el-button link type="danger" @click="removeCountry(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>
  </el-tabs>

  <el-dialog v-model="siteDialog" :title="siteForm.id ? '编辑站点' : '新增站点'" width="560px">
    <el-form label-width="110px">
      <el-form-item label="国家" required>
        <el-select v-model="siteForm.country_id" placeholder="选择国家">
          <el-option
            v-for="c in countries"
            :key="c.id"
            :value="c.id"
            :label="`${c.flag_emoji} ${c.name_zh}`"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="名称" required>
        <el-input v-model="siteForm.name" />
      </el-form-item>
      <el-form-item label="Base URL" required>
        <el-input v-model="siteForm.base_url" placeholder="https://..." />
      </el-form-item>
      <el-form-item label="语言">
        <el-radio-group v-model="siteForm.language">
          <el-radio value="en">英语</el-radio>
          <el-radio value="fr">法语</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="层级">
        <el-select v-model="siteForm.tier">
          <el-option :value="1" label="Tier 1（每小时）" />
          <el-option :value="2" label="Tier 2（每6小时）" />
          <el-option :value="3" label="低频（每天）" />
        </el-select>
      </el-form-item>
      <el-form-item label="采集方式">
        <el-radio-group v-model="siteForm.discovery_method">
          <el-radio value="rss">RSS</el-radio>
          <el-radio value="listing">列表页</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="siteForm.discovery_method === 'rss'" label="Feed URL" required>
        <el-input v-model="siteForm.feed_url" placeholder="https://.../feed/" />
      </el-form-item>
      <template v-else>
        <el-form-item label="列表页 URL" required>
          <el-input v-model="siteForm.listing_url" />
        </el-form-item>
        <el-form-item label="链接选择器">
          <el-input v-model="siteForm.listing_selector" placeholder="CSS 选择器，留空用同域启发式" />
        </el-form-item>
      </template>
      <el-collapse>
        <el-collapse-item title="高级：提取选择器（可选，留空用通用提取）">
          <el-form-item label="标题选择器"><el-input v-model="siteForm.title_selector" /></el-form-item>
          <el-form-item label="正文选择器"><el-input v-model="siteForm.body_selector" /></el-form-item>
          <el-form-item label="图片选择器"><el-input v-model="siteForm.image_selector" /></el-form-item>
          <el-form-item label="日期选择器"><el-input v-model="siteForm.date_selector" /></el-form-item>
        </el-collapse-item>
      </el-collapse>
    </el-form>
    <template #footer>
      <el-button @click="siteDialog = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="saveSite">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="countryDialog" :title="countryForm.id ? '编辑国家' : '新增国家'" width="420px">
    <el-form label-width="90px">
      <el-form-item label="代码" required>
        <el-input v-model="countryForm.code" placeholder="两位大写，如 GH" maxlength="2" />
      </el-form-item>
      <el-form-item label="中文名" required><el-input v-model="countryForm.name_zh" /></el-form-item>
      <el-form-item label="英文名" required><el-input v-model="countryForm.name_en" /></el-form-item>
      <el-form-item label="国旗" required>
        <el-input v-model="countryForm.flag_emoji" placeholder="🇬🇭" maxlength="8" />
      </el-form-item>
      <el-form-item label="层级">
        <el-select v-model="countryForm.tier">
          <el-option :value="1" label="Tier 1" />
          <el-option :value="2" label="Tier 2" />
          <el-option :value="3" label="低频" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="countryDialog = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="saveCountry">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { onMounted, reactive, ref } from "vue";

import {
  createCountry,
  createSite,
  deleteCountry,
  deleteSite,
  listCountries,
  listSites,
  triggerCrawl,
  updateCountry,
  updateSite,
} from "../api/endpoints";
import type { Country, Site, SiteIn } from "../api/types";

const tab = ref("sites");
const loading = ref(false);
const saving = ref(false);
const countries = ref<Country[]>([]);
const sites = ref<Site[]>([]);

const siteDialog = ref(false);
const countryDialog = ref(false);

const emptySite = (): SiteIn & { id?: number } => ({
  country_id: 0,
  name: "",
  base_url: "",
  language: "en",
  discovery_method: "rss",
  feed_url: null,
  listing_url: null,
  listing_selector: null,
  title_selector: null,
  body_selector: null,
  image_selector: null,
  date_selector: null,
  tier: 1,
  enabled: true,
});
const siteForm = reactive<SiteIn & { id?: number }>(emptySite());

const emptyCountry = (): Omit<Country, "id"> & { id?: number } => ({
  code: "",
  name_en: "",
  name_zh: "",
  flag_emoji: "",
  tier: 1,
  enabled: true,
});
const countryForm = reactive<Omit<Country, "id"> & { id?: number }>(emptyCountry());

onMounted(loadAll);

async function loadAll() {
  loading.value = true;
  try {
    [countries.value, sites.value] = await Promise.all([listCountries(), listSites()]);
  } finally {
    loading.value = false;
  }
}

function countryLabel(id: number): string {
  const c = countries.value.find((c) => c.id === id);
  return c ? `${c.flag_emoji} ${c.name_zh}` : String(id);
}

function formatTime(iso: string | null): string {
  return iso ? iso.replace("T", " ").slice(0, 16) : "";
}

function openSiteDialog(row?: Site) {
  Object.assign(siteForm, emptySite(), row ?? {});
  if (row) siteForm.id = row.id;
  else delete siteForm.id;
  siteDialog.value = true;
}

async function saveSite() {
  if (!siteForm.country_id || !siteForm.name || !siteForm.base_url) {
    ElMessage.warning("请填写国家、名称和 Base URL");
    return;
  }
  if (siteForm.discovery_method === "rss" && !siteForm.feed_url) {
    ElMessage.warning("RSS 方式需要填写 Feed URL");
    return;
  }
  if (siteForm.discovery_method === "listing" && !siteForm.listing_url) {
    ElMessage.warning("列表页方式需要填写列表页 URL");
    return;
  }
  saving.value = true;
  try {
    const { id, ...body } = siteForm;
    if (id) await updateSite(id, body);
    else await createSite(body);
    siteDialog.value = false;
    await loadAll();
    ElMessage.success("已保存");
  } catch {
    /* interceptor already toasted */
  } finally {
    saving.value = false;
  }
}

async function toggleSite(row: Site, enabled: boolean) {
  const { id, last_crawl_at, last_crawl_status, country, ...body } = row;
  try {
    await updateSite(id, { ...body, enabled });
    row.enabled = enabled;
  } catch {
    /* interceptor toasted */
  }
}

async function removeSite(row: Site) {
  await ElMessageBox.confirm(`确定删除站点「${row.name}」？`, "删除确认", { type: "warning" });
  try {
    await deleteSite(row.id);
    await loadAll();
    ElMessage.success("已删除");
  } catch {
    /* 409 has articles — interceptor toasted */
  }
}

async function crawlNow(row: Site) {
  try {
    const { crawl_run_id } = await triggerCrawl(row.id);
    ElMessage.success(`已开始抓取（记录 #${crawl_run_id}），可在「抓取与翻译」页查看进度`);
  } catch {
    /* 409 already running / 404 before Plan 2 — interceptor toasted */
  }
}

function openCountryDialog(row?: Country) {
  Object.assign(countryForm, emptyCountry(), row ?? {});
  if (row) countryForm.id = row.id;
  else delete countryForm.id;
  countryDialog.value = true;
}

async function saveCountry() {
  if (!countryForm.code || !countryForm.name_zh || !countryForm.name_en || !countryForm.flag_emoji) {
    ElMessage.warning("请填写完整的国家信息");
    return;
  }
  saving.value = true;
  try {
    const { id, ...body } = countryForm;
    body.code = body.code.toUpperCase();
    if (id) await updateCountry(id, body);
    else await createCountry(body);
    countryDialog.value = false;
    await loadAll();
    ElMessage.success("已保存");
  } catch {
    /* interceptor toasted */
  } finally {
    saving.value = false;
  }
}

async function toggleCountry(row: Country, enabled: boolean) {
  const { id, ...body } = row;
  try {
    await updateCountry(id, { ...body, enabled });
    row.enabled = enabled;
  } catch {
    /* interceptor toasted */
  }
}

async function removeCountry(row: Country) {
  await ElMessageBox.confirm(`确定删除国家「${row.name_zh}」？`, "删除确认", { type: "warning" });
  try {
    await deleteCountry(row.id);
    await loadAll();
    ElMessage.success("已删除");
  } catch {
    /* 409 has sites/articles — interceptor toasted */
  }
}
</script>

<style scoped>
.toolbar {
  margin-bottom: 12px;
  display: flex;
  gap: 8px;
}
.failed {
  color: #e24b4a;
}
.muted {
  color: #93918a;
  font-size: 12px;
}
</style>
```

- [ ] **Step 2: Verify live** (backend running as in Task 3)

Open `http://localhost:5174/admin/sites`:
- Both tabs list the 10 seeded sites / 4 countries.
- Create a Tier-2 country (e.g. BJ 贝宁 🇧🇯) and a site under it; edit it; disable it; delete
  site then country. Duplicate code shows the 409 warning toast; deleting a country that
  still has a site shows the 409 warning.
- 抓取 button: with only Plan 1 running it toasts the generic error (route missing) —
  acceptable until Plan 2; with Plan 2 running it toasts the run id.

- [ ] **Step 3: Type gate and commit**

Run: `cd admin && npm run build`
Expected: passes.

```bash
git add admin/src/views/SitesView.vue
git commit -m "feat(admin): countries and sites management with crawl-now"
```

---

### Task 5: Articles management with paragraph-safe editing

**Files:**
- Replace: `admin/src/views/ArticlesView.vue`

- [ ] **Step 1: Replace `admin/src/views/ArticlesView.vue`**

```vue
<template>
  <div class="filters">
    <el-select v-model="filters.status" placeholder="全部状态" clearable class="filter">
      <el-option v-for="s in ARTICLE_STATUSES" :key="s.value" :value="s.value" :label="s.label" />
    </el-select>
    <el-select v-model="filters.country" placeholder="全部国家" clearable class="filter">
      <el-option
        v-for="c in countries"
        :key="c.code"
        :value="c.code"
        :label="`${c.flag_emoji} ${c.name_zh}`"
      />
    </el-select>
    <el-select v-model="filters.site_id" placeholder="全部站点" clearable class="filter-wide">
      <el-option v-for="s in sites" :key="s.id" :value="s.id" :label="s.name" />
    </el-select>
    <el-button :loading="loading" @click="load">查询</el-button>
  </div>

  <el-table v-loading="loading" :data="rows">
    <el-table-column type="expand">
      <template #default="{ row }">
        <div class="expand">
          <p>来源：<a :href="row.source_url" target="_blank" rel="noopener">{{ row.source_url }}</a></p>
          <p v-if="row.translation_error" class="failed">翻译错误：{{ row.translation_error }}</p>
        </div>
      </template>
    </el-table-column>
    <el-table-column prop="id" label="ID" width="70" />
    <el-table-column label="图片" width="70">
      <template #default="{ row }">
        <img v-if="row.main_image_url" :src="row.main_image_url" class="thumb" />
        <span v-else class="muted">—</span>
      </template>
    </el-table-column>
    <el-table-column label="标题" min-width="240">
      <template #default="{ row }">
        <div class="title-cell">{{ row.title }}</div>
        <div v-if="row.title_zh" class="muted title-cell">{{ row.title_zh }}</div>
      </template>
    </el-table-column>
    <el-table-column prop="site_name" label="站点" width="120" />
    <el-table-column prop="country_code" label="国家" width="70" />
    <el-table-column label="分类" width="80">
      <template #default="{ row }">{{ categoryLabel(row.category) }}</template>
    </el-table-column>
    <el-table-column label="状态" width="90">
      <template #default="{ row }">
        <el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="轮播" width="70">
      <template #default="{ row }">
        <el-button
          link
          :type="row.is_banner ? 'warning' : 'info'"
          @click="toggleBanner(row)"
        >{{ row.is_banner ? "★" : "☆" }}</el-button>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="190" fixed="right">
      <template #default="{ row }">
        <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
        <el-button link type="primary" @click="retranslate(row)">重翻译</el-button>
        <el-button link type="danger" @click="remove(row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>

  <el-pagination
    v-model:current-page="filters.page"
    :page-size="filters.page_size"
    :total="total"
    layout="prev, pager, next, total"
    class="pager"
    @current-change="load"
  />

  <el-dialog v-model="editDialog" title="编辑新闻" width="860px" top="4vh">
    <el-form label-width="90px">
      <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
      <el-form-item label="中文标题"><el-input v-model="form.title_zh" /></el-form-item>
      <div class="row2">
        <el-form-item label="分类">
          <el-select v-model="form.category" clearable>
            <el-option v-for="c in CATEGORIES" :key="c.value" :value="c.value" :label="c.label" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option v-for="s in ARTICLE_STATUSES" :key="s.value" :value="s.value" :label="s.label" />
          </el-select>
        </el-form-item>
      </div>
      <el-form-item label="主图 URL">
        <el-input v-model="form.main_image_url" />
        <img v-if="form.main_image_url" :src="form.main_image_url" class="preview" />
      </el-form-item>
      <div class="row2">
        <el-form-item label="原文段落" class="para-item">
          <el-input v-model="form.paragraphsText" type="textarea" :rows="14" />
          <div class="muted">段落数: {{ sourceCount }}（空行分段）</div>
        </el-form-item>
        <el-form-item label="中文段落" class="para-item">
          <el-input v-model="form.paragraphsZhText" type="textarea" :rows="14" />
          <div class="muted">段落数: {{ zhCount }}</div>
        </el-form-item>
      </div>
      <el-alert
        v-if="zhCount > 0 && sourceCount !== zhCount"
        title="段落数不一致：双语对照视图将错位"
        type="warning"
        :closable="false"
      />
    </el-form>
    <template #footer>
      <el-button @click="editDialog = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import {
  deleteArticle,
  listArticles,
  listCountries,
  listSites,
  patchArticle,
  retranslateArticle,
} from "../api/endpoints";
import type { ArticleAdmin, Country, Site } from "../api/types";
import { ARTICLE_STATUSES, CATEGORIES } from "../api/types";
import { joinParagraphs, splitParagraphs } from "../utils/paragraphs";

const loading = ref(false);
const saving = ref(false);
const rows = ref<ArticleAdmin[]>([]);
const total = ref(0);
const countries = ref<Country[]>([]);
const sites = ref<Site[]>([]);

const filters = reactive({
  status: undefined as string | undefined,
  country: undefined as string | undefined,
  site_id: undefined as number | undefined,
  page: 1,
  page_size: 20,
});

const editDialog = ref(false);
const editing = ref<ArticleAdmin | null>(null);
const form = reactive({
  title: "",
  title_zh: "",
  category: "" as string | null,
  status: "",
  main_image_url: "" as string | null,
  paragraphsText: "",
  paragraphsZhText: "",
});

const sourceCount = computed(() => splitParagraphs(form.paragraphsText).length);
const zhCount = computed(() => splitParagraphs(form.paragraphsZhText).length);

onMounted(async () => {
  [countries.value, sites.value] = await Promise.all([listCountries(), listSites()]);
  await load();
});

async function load() {
  loading.value = true;
  try {
    const data = await listArticles({ ...filters });
    rows.value = data.items;
    total.value = data.total;
  } finally {
    loading.value = false;
  }
}

function statusLabel(v: string) {
  return ARTICLE_STATUSES.find((s) => s.value === v)?.label ?? v;
}
function statusTag(v: string) {
  return ARTICLE_STATUSES.find((s) => s.value === v)?.tag ?? "info";
}
function categoryLabel(v: string | null) {
  return CATEGORIES.find((c) => c.value === v)?.label ?? (v || "—");
}

async function toggleBanner(row: ArticleAdmin) {
  const updated = await patchArticle(row.id, { is_banner: !row.is_banner });
  row.is_banner = updated.is_banner;
}

async function retranslate(row: ArticleAdmin) {
  await ElMessageBox.confirm(`将「${row.title}」重新加入翻译队列？`, "重新翻译", { type: "info" });
  const updated = await retranslateArticle(row.id);
  row.status = updated.status;
  row.translation_error = updated.translation_error;
  ElMessage.success("已加入翻译队列");
}

async function remove(row: ArticleAdmin) {
  await ElMessageBox.confirm(`确定删除「${row.title}」？`, "删除确认", { type: "warning" });
  await deleteArticle(row.id);
  ElMessage.success("已删除");
  await load();
}

function openEdit(row: ArticleAdmin) {
  editing.value = row;
  form.title = row.title;
  form.title_zh = row.title_zh ?? "";
  form.category = row.category;
  form.status = row.status;
  form.main_image_url = row.main_image_url;
  form.paragraphsText = joinParagraphs(row.paragraphs);
  form.paragraphsZhText = joinParagraphs(row.paragraphs_zh);
  editDialog.value = true;
}

async function save() {
  const row = editing.value;
  if (!row) return;
  if (zhCount.value > 0 && sourceCount.value !== zhCount.value) {
    await ElMessageBox.confirm(
      "段落数不一致，双语对照将错位，确定保存？",
      "段落对齐警告",
      { type: "warning" },
    );
  }
  const body: Parameters<typeof patchArticle>[1] = {};
  if (form.title !== row.title) body.title = form.title;
  if ((form.title_zh || null) !== row.title_zh) body.title_zh = form.title_zh || null;
  if (form.category !== row.category) body.category = form.category || null;
  if (form.status !== row.status) body.status = form.status;
  if ((form.main_image_url || null) !== row.main_image_url)
    body.main_image_url = form.main_image_url || null;
  const paragraphs = splitParagraphs(form.paragraphsText);
  if (JSON.stringify(paragraphs) !== JSON.stringify(row.paragraphs)) body.paragraphs = paragraphs;
  const paragraphsZh = splitParagraphs(form.paragraphsZhText);
  if (JSON.stringify(paragraphsZh) !== JSON.stringify(row.paragraphs_zh ?? []))
    body.paragraphs_zh = paragraphsZh;

  if (Object.keys(body).length === 0) {
    editDialog.value = false;
    return;
  }
  saving.value = true;
  try {
    await patchArticle(row.id, body);
    editDialog.value = false;
    ElMessage.success("已保存");
    await load();
  } catch {
    /* interceptor toasted */
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.filters {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.filter {
  width: 140px;
}
.filter-wide {
  width: 180px;
}
.thumb {
  width: 48px;
  height: 32px;
  object-fit: cover;
  border-radius: 4px;
}
.title-cell {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.muted {
  color: #93918a;
  font-size: 12px;
}
.failed {
  color: #e24b4a;
}
.expand {
  padding: 4px 16px;
  font-size: 13px;
}
.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
.row2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 12px;
}
.para-item :deep(.el-form-item__content) {
  display: block;
}
.preview {
  margin-top: 8px;
  max-height: 120px;
  border-radius: 4px;
}
</style>
```

- [ ] **Step 2: Verify live**

With fixture articles in the backend (insert the three fixture articles from
`.claude/skills/verify/SKILL.md` if the DB is empty):
- Filters by status/country/site narrow the table; pagination works.
- Star toggles banner instantly; 重翻译 flips status to 待翻译; expand row shows source
  link and translation error.
- Edit dialog: paragraph counters live-update; making counts differ shows the warning
  alert and saving asks for confirmation; saving edited 中文段落 persists (re-open to check).
- Delete works with confirm.

- [ ] **Step 3: Type gate and commit**

Run: `cd admin && npm run build`
Expected: passes.

```bash
git add admin/src/views/ArticlesView.vue
git commit -m "feat(admin): articles table with paragraph-safe edit dialog"
```

---

### Task 6: Pipeline monitor

**Files:**
- Replace: `admin/src/views/PipelineView.vue`

Depends on Plan 2's `GET /crawl-runs`; with only Plan 1 running the page shows the
error toast and empty tables — build it now, verify fully once Plan 2 is executed.

- [ ] **Step 1: Replace `admin/src/views/PipelineView.vue`**

```vue
<template>
  <h3>抓取记录</h3>
  <div class="toolbar">
    <el-select v-model="siteId" placeholder="全部站点" clearable class="filter-wide" @change="loadRuns">
      <el-option v-for="s in sites" :key="s.id" :value="s.id" :label="s.name" />
    </el-select>
    <el-button :loading="loadingRuns" @click="loadRuns">刷新</el-button>
    <el-switch v-model="autoRefresh" active-text="自动刷新（10 秒）" />
  </div>
  <el-table v-loading="loadingRuns" :data="runs">
    <el-table-column type="expand">
      <template #default="{ row }">
        <div class="expand">{{ row.error || "无错误" }}</div>
      </template>
    </el-table-column>
    <el-table-column prop="id" label="ID" width="70" />
    <el-table-column prop="site_name" label="站点" min-width="130" />
    <el-table-column label="开始时间" width="150">
      <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
    </el-table-column>
    <el-table-column label="结束时间" width="150">
      <template #default="{ row }">{{ formatTime(row.finished_at) }}</template>
    </el-table-column>
    <el-table-column label="状态" width="90">
      <template #default="{ row }">
        <el-tag :type="runTag(row.status)">{{ runLabel(row.status) }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="articles_found" label="发现" width="70" />
    <el-table-column prop="articles_new" label="新增" width="70" />
  </el-table>
  <el-pagination
    v-model:current-page="page"
    :page-size="pageSize"
    :total="totalRuns"
    layout="prev, pager, next, total"
    class="pager"
    @current-change="loadRuns"
  />

  <h3 class="section">翻译失败</h3>
  <div class="toolbar">
    <el-button :loading="loadingFailed" @click="loadFailed">刷新</el-button>
    <el-button type="primary" :disabled="failed.length === 0" :loading="retrying" @click="retryAll">
      全部重试（{{ failed.length }}）
    </el-button>
  </div>
  <el-table v-loading="loadingFailed" :data="failed">
    <el-table-column prop="id" label="ID" width="70" />
    <el-table-column prop="title" label="标题" min-width="220" />
    <el-table-column prop="site_name" label="站点" width="130" />
    <el-table-column prop="translation_error" label="错误" min-width="220" show-overflow-tooltip />
    <el-table-column label="操作" width="100" fixed="right">
      <template #default="{ row }">
        <el-button link type="primary" @click="retryOne(row)">重试</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import { onMounted, onUnmounted, ref, watch } from "vue";

import { listArticles, listCrawlRuns, listSites, retranslateArticle } from "../api/endpoints";
import type { ArticleAdmin, CrawlRun, Site } from "../api/types";

const sites = ref<Site[]>([]);
const runs = ref<CrawlRun[]>([]);
const failed = ref<ArticleAdmin[]>([]);
const siteId = ref<number | undefined>(undefined);
const page = ref(1);
const pageSize = 20;
const totalRuns = ref(0);
const loadingRuns = ref(false);
const loadingFailed = ref(false);
const retrying = ref(false);
const autoRefresh = ref(false);

let timer: ReturnType<typeof setInterval> | null = null;

onMounted(async () => {
  sites.value = await listSites();
  await Promise.all([loadRuns(), loadFailed()]);
});

onUnmounted(stopTimer);

watch(autoRefresh, (on) => {
  if (on) timer = setInterval(loadRuns, 10_000);
  else stopTimer();
});

function stopTimer() {
  if (timer) clearInterval(timer);
  timer = null;
}

async function loadRuns() {
  loadingRuns.value = true;
  try {
    const data = await listCrawlRuns({ site_id: siteId.value, page: page.value, page_size: pageSize });
    runs.value = data.items;
    totalRuns.value = data.total;
  } finally {
    loadingRuns.value = false;
  }
}

async function loadFailed() {
  loadingFailed.value = true;
  try {
    const data = await listArticles({ status: "translation_failed", page: 1, page_size: 50 });
    failed.value = data.items;
  } finally {
    loadingFailed.value = false;
  }
}

async function retryOne(row: ArticleAdmin) {
  await retranslateArticle(row.id);
  ElMessage.success(`#${row.id} 已加入翻译队列`);
  await loadFailed();
}

async function retryAll() {
  retrying.value = true;
  let done = 0;
  try {
    for (const row of failed.value) {
      await retranslateArticle(row.id);
      done += 1;
    }
    ElMessage.success(`已重新排队 ${done} 篇`);
  } finally {
    retrying.value = false;
    await loadFailed();
  }
}

function formatTime(iso: string | null): string {
  return iso ? iso.replace("T", " ").slice(0, 19) : "—";
}
function runLabel(s: string) {
  return { running: "进行中", success: "成功", failed: "失败" }[s] ?? s;
}
function runTag(s: string) {
  return ({ running: "warning", success: "success", failed: "danger" } as const)[
    s as "running" | "success" | "failed"
  ] ?? "info";
}
</script>

<style scoped>
h3 {
  margin: 0 0 12px;
  font-weight: 500;
}
.section {
  margin-top: 32px;
}
.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}
.filter-wide {
  width: 180px;
}
.expand {
  padding: 4px 16px;
  font-size: 13px;
  white-space: pre-wrap;
}
.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
</style>
```

- [ ] **Step 2: Verify live** (fully verifiable only with Plan 2 executed; with Plan 1 only,
confirm the page renders, the failures table loads, and the runs table shows the error toast)

- Runs table lists crawl runs newest-first with status tags and expandable error text;
  site filter and pagination work; auto-refresh polls every 10s while enabled and stops
  when the page unmounts.
- Failures section lists `translation_failed` articles; 重试 re-queues one; 全部重试 loops
  through all with a success count.

- [ ] **Step 3: Type gate and commit**

Run: `cd admin && npm run build`
Expected: passes.

```bash
git add admin/src/views/PipelineView.vue
git commit -m "feat(admin): pipeline monitor with crawl runs and translation retry"
```

---

### Task 7: Settings (AI translation config)

**Files:**
- Replace: `admin/src/views/SettingsView.vue`

- [ ] **Step 1: Replace `admin/src/views/SettingsView.vue`**

```vue
<template>
  <el-card class="card">
    <template #header>AI 翻译配置</template>
    <el-form label-width="110px" class="form">
      <el-form-item label="Base URL">
        <el-input v-model="form.ai_base_url" placeholder="https://api.openai.com/v1" />
      </el-form-item>
      <el-form-item label="模型">
        <el-input v-model="form.ai_model" placeholder="gpt-4o-mini" />
      </el-form-item>
      <el-form-item label="API Key">
        <el-input
          v-model="form.ai_api_key"
          type="password"
          show-password
          :placeholder="maskedPlaceholder"
        />
        <div class="muted">留空则保持现有 Key 不变</div>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        <el-button :loading="testing" @click="runTest">测试翻译</el-button>
      </el-form-item>
      <el-alert
        v-if="testResult && testResult.ok"
        type="success"
        :closable="false"
        :title="`测试成功（${testResult.latency_ms} ms）：${testResult.title_zh}`"
        :description="testResult.paragraph_zh"
      />
      <el-alert
        v-else-if="testResult"
        type="error"
        :closable="false"
        :title="`测试失败：${testResult.error}`"
      />
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import { getConfig, testTranslation, updateConfig } from "../api/endpoints";
import type { TestTranslationResult } from "../api/endpoints";

const saving = ref(false);
const testing = ref(false);
const masked = ref("");
const testResult = ref<TestTranslationResult | null>(null);

const form = reactive({
  ai_base_url: "",
  ai_model: "",
  ai_api_key: "",
});

const maskedPlaceholder = computed(() =>
  masked.value ? `当前：${masked.value}` : "尚未配置",
);

onMounted(load);

async function load() {
  const cfg = await getConfig();
  form.ai_base_url = cfg.ai_base_url;
  form.ai_model = cfg.ai_model;
  masked.value = cfg.ai_api_key_masked;
  form.ai_api_key = "";
}

async function save() {
  saving.value = true;
  try {
    const body: { ai_base_url: string; ai_model: string; ai_api_key?: string } = {
      ai_base_url: form.ai_base_url,
      ai_model: form.ai_model,
    };
    if (form.ai_api_key) body.ai_api_key = form.ai_api_key;
    const cfg = await updateConfig(body);
    masked.value = cfg.ai_api_key_masked;
    form.ai_api_key = "";
    ElMessage.success("已保存");
  } catch {
    /* interceptor toasted */
  } finally {
    saving.value = false;
  }
}

async function runTest() {
  testing.value = true;
  testResult.value = null;
  try {
    testResult.value = await testTranslation();
  } catch {
    /* 404 before Plan 2 — interceptor toasted */
  } finally {
    testing.value = false;
  }
}
</script>

<style scoped>
.card {
  max-width: 640px;
}
.form :deep(.el-alert) {
  margin-top: 8px;
}
.muted {
  color: #93918a;
  font-size: 12px;
}
</style>
```

- [ ] **Step 2: Verify live**

- Page loads the current config; masked key shows in the placeholder (`当前：****1234`).
- Saving with the key field empty keeps the stored key (masked value unchanged);
  entering a new key updates the mask.
- 测试翻译: with Plan 2 + a real key → success alert with latency and 中文 sample;
  with a bad key → red alert with the provider error; with Plan 1 only → error toast (404).

- [ ] **Step 3: Type gate and commit**

Run: `cd admin && npm run build`
Expected: passes.

```bash
git add admin/src/views/SettingsView.vue
git commit -m "feat(admin): AI translation settings with key masking and test button"
```

---

### Task 8: Full live verification

**Files:** none — end-to-end walkthrough against the running backend.

- [ ] **Step 1: Run the full test suite and build**

Run: `cd admin && npm run test && npm run build`
Expected: 10 tests pass; build clean.

- [ ] **Step 2: Start backend (seeded) + admin dev server**

```bash
cd backend
rm -f dev.db
DATABASE_URL="sqlite:///./dev.db" uv run python -m app.seed
DATABASE_URL="sqlite:///./dev.db" SCHEDULER_ENABLED=false uv run uvicorn app.main:app --port 8000
# separate terminal:
cd admin && npm run dev
```

Insert the three fixture articles (script in `.claude/skills/verify/SKILL.md`) so the
articles page has data.

- [ ] **Step 3: Walk every flow**

1. Unauthenticated `http://localhost:5174/admin/articles` → redirected to login with
   `?redirect=/articles`; after login lands back on articles.
2. Wrong password → inline error, no redirect loop.
3. Sites: create/edit/disable/delete site and country; duplicate code → 409 toast;
   delete country with site → 409 toast.
4. Articles: filter by each status/country/site; banner star; edit dialog paragraph
   counters and mismatch confirm; save 中文段落 edit and re-open to confirm persistence;
   retranslate; delete.
5. Pipeline: renders; failures list works (runs table needs Plan 2).
6. Settings: save without key keeps mask; save with key updates mask.
7. Session expiry: delete the token in devtools localStorage, click any action →
   redirected to login.

- [ ] **Step 4: Commit any fixes found, then finish**

```bash
git add admin/
git commit -m "test(admin): live verification fixes"
```

(Skip the commit if the walkthrough found nothing to fix.)
