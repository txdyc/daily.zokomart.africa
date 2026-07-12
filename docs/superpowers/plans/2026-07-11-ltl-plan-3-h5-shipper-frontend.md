# LTL Plan 3: H5 Shipper Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Logistics" section to the existing ZokoDaily H5 app: a three-tab shell (News · Logistics · Me), phone+OTP login, trip browsing with filters, trip/route detail, the shipper order form, my-orders with contact disclosure, and the notification center — all consuming the Plan 1/2 `/api/lg/*` API.

**Architecture:** Extends the existing Vue 3 + `<script setup>` + TS + Pinia + vue-router + vue-i18n + Vant app under `h5/`. A new axios instance (`lgClient`) targets `/api/lg`, attaching a bearer token from `localStorage`; a Pinia `auth` store owns the session. News reading stays anonymous; logistics ordering requires login, enforced by a router guard. UI follows the existing custom-component style (native elements + CSS tokens, Vant only for `van-list`/`van-pull-refresh`), English strings for logistics with the admin/news bilingual toggle untouched.

**Tech Stack:** unchanged — Vue 3.4, Vant 4.9, Pinia 2, vue-router 4, vue-i18n 9, axios, Vite 5, Vitest 1.6 + @vue/test-utils, vue-tsc. No new dependencies.

**Plan sequence:** LTL Plan 1 (done) → LTL Plan 2 (done) → **LTL Plan 3 (this: H5 shipper)** → LTL Plan 4 (H5 driver center) → LTL Plan 5 (admin frontend) → LTL Plan 6 (deployment).

**Working directory:** all commands run from `h5/` unless stated otherwise.
**Spec:** `D:\GHANA\COMPANIES\daily.zokomart\Less-than-Truckload_prd.md` (V1.1) §4.1 (H5 tabs), §4.4 (accounts/OTP), §8 (trip browse), §9 (order form), §10 (order lifecycle, contact disclosure), §14 (notifications).

**Existing conventions to follow (verified in the codebase):**
- API layer: `src/api/client.ts` is an axios instance with a response interceptor that unwraps `error.response.data.detail` into `new Error(message)`. Mirror this for `lgClient`.
- Stores: Pinia option stores (`src/stores/feed.ts`, `prefs.ts`). The feed store separates `loading` (UI/van-list v-model) from an in-flight guard — reuse that lesson for the browse store.
- i18n: `createI18n({ legacy: false })`, keys in `src/i18n/en.ts` + `zh.ts`, used via `useI18n().t`.
- Components: custom, styled with CSS variables from `src/styles/tokens.css`; inline SVG icons; `van-list` + `van-pull-refresh` for infinite lists (registered in `src/main.ts`).
- Tests: `tests/helpers.ts` exports `freshPinia()` + `testI18n()`; specs `vi.mock("../src/api/…")` the API module and mount with `global.plugins`.

**Backend endpoints consumed (all built in Plans 1–2):**
`POST /api/lg/auth/request-otp` · `POST /api/lg/auth/login` · `GET /api/lg/auth/me` ·
`GET /api/lg/trips` (public browse) · `GET /api/lg/routes/{id}` (public detail) ·
`POST /api/lg/uploads` · `POST /api/lg/orders` · `GET /api/lg/orders/mine` ·
`GET /api/lg/orders/{id}` · `POST /api/lg/orders/{id}/cancel` ·
`GET /api/lg/notifications` · `POST /api/lg/notifications/{id}/read`.

---

## File structure created by this plan

```
h5/src/
├── api/
│   ├── lgClient.ts        # axios instance for /api/lg + bearer + 401 handling
│   ├── lgTypes.ts         # TS interfaces for the shipper surface
│   └── lg.ts              # typed API functions
├── stores/
│   ├── auth.ts            # session: token, phone, userId, login/logout/hydrate
│   └── lgFeed.ts          # trip browse: filters, pagination, loadMore/refresh
├── components/
│   ├── TabBar.vue         # bottom News · Logistics · Me
│   ├── TripCard.vue       # one browse result
│   ├── OrderStatusTag.vue # coloured status pill
│   └── ImageUpload.vue    # file → /uploads → attachment id
├── views/
│   ├── LogisticsView.vue  # browse tab (filters + van-list + pull-refresh)
│   ├── TripDetailView.vue # route detail + book CTA
│   ├── OrderFormView.vue  # cargo form → submit
│   ├── MeView.vue         # account hub (logged-in / logged-out)
│   ├── LoginView.vue      # phone → OTP
│   ├── MyOrdersView.vue   # shipper order list
│   ├── OrderDetailView.vue# status timeline + contact + cancel
│   └── NotificationsView.vue
├── router.ts              # MODIFIED: tabs + logistics routes + auth guard
├── main.ts                # MODIFIED: hydrate auth, wire 401 → login redirect
└── i18n/{en,zh}.ts        # MODIFIED: + lg.* namespace

h5/tests/
├── helpers.ts             # MODIFIED: testRouter(), setLgToken()
├── authStore.spec.ts
├── lgFeedStore.spec.ts
├── tabBar.spec.ts
├── loginView.spec.ts
├── meView.spec.ts
├── orderForm.spec.ts
├── myOrders.spec.ts
├── orderDetail.spec.ts
└── notifications.spec.ts
```

**Route map after this plan:**

| Path | Name | View | Auth |
| --- | --- | --- | --- |
| `/` | news | HomeView (existing) + TabBar | no |
| `/article/:id` | article | ArticleView (existing) | no |
| `/lg` | logistics | LogisticsView + TabBar | no |
| `/lg/trip/:id` | trip | TripDetailView | no |
| `/lg/order/new/:tripId` | order-new | OrderFormView | **yes** |
| `/me` | me | MeView + TabBar | no |
| `/me/login` | login | LoginView | no |
| `/me/orders` | my-orders | MyOrdersView | **yes** |
| `/me/orders/:id` | order-detail | OrderDetailView | **yes** |
| `/me/notifications` | notifications | NotificationsView | **yes** |

---

### Task 1: LG API client, types, and auth store

**Files:**
- Create: `h5/src/api/lgClient.ts`, `h5/src/api/lgTypes.ts`, `h5/src/api/lg.ts`, `h5/src/stores/auth.ts`
- Test: `h5/tests/authStore.spec.ts`

- [ ] **Step 1: Write the failing test**

Create `h5/tests/authStore.spec.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "../src/stores/auth";
import { freshPinia } from "./helpers";

vi.mock("../src/api/lg", () => ({
  requestOtp: vi.fn(() => Promise.resolve({ ok: true })),
  login: vi.fn(() =>
    Promise.resolve({ access_token: "tok-123", token_type: "bearer", user_id: 7, phone: "+233241234567" }),
  ),
}));
import { login, requestOtp } from "../src/api/lg";

describe("auth store", () => {
  beforeEach(() => {
    freshPinia();
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("starts logged out", () => {
    expect(useAuthStore().loggedIn).toBe(false);
  });

  it("requestCode delegates to the api", async () => {
    await useAuthStore().requestCode("0241234567");
    expect(requestOtp).toHaveBeenCalledWith("0241234567");
  });

  it("signIn stores the session and persists the token", async () => {
    const auth = useAuthStore();
    await auth.signIn("0241234567", "123456");
    expect(login).toHaveBeenCalledWith("0241234567", "123456");
    expect(auth.loggedIn).toBe(true);
    expect(auth.phone).toBe("+233241234567");
    expect(auth.userId).toBe(7);
    expect(localStorage.getItem("lg-token")).toBe("tok-123");
  });

  it("signOut clears state and storage", async () => {
    const auth = useAuthStore();
    await auth.signIn("0241234567", "123456");
    auth.signOut();
    expect(auth.loggedIn).toBe(false);
    expect(auth.token).toBe("");
    expect(localStorage.getItem("lg-token")).toBeNull();
  });

  it("hydrates the token from storage on creation", () => {
    localStorage.setItem("lg-token", "persisted");
    freshPinia();
    expect(useAuthStore().token).toBe("persisted");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/authStore.spec.ts`
Expected: FAIL — cannot resolve `../src/stores/auth`

- [ ] **Step 3: Write the implementation**

Create `h5/src/api/lgClient.ts`:

```typescript
import axios from "axios";

export const LG_TOKEN_KEY = "lg-token";

export const lgApi = axios.create({ baseURL: "/api/lg", timeout: 15000 });

lgApi.interceptors.request.use((config) => {
  const token = localStorage.getItem(LG_TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

lgApi.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem(LG_TOKEN_KEY);
      window.dispatchEvent(new Event("lg-unauthorized"));
    }
    const message = error?.response?.data?.detail ?? error?.message ?? "Network error";
    return Promise.reject(new Error(String(message)));
  },
);
```

Create `h5/src/api/lgTypes.ts`:

```typescript
export interface AuthSession {
  access_token: string;
  token_type: string;
  user_id: number;
  phone: string;
}

export interface TripCard {
  trip_id: number;
  route_id: number;
  depart_date: string;
  depart_time: string;
  origin_region: string;
  origin_town: string;
  dest_region: string;
  dest_town: string;
  via_towns: string[];
  est_duration_hours: number;
  vehicle_type: string;
  brand_model: string;
  remaining_load_kg: number;
  remaining_volume_m3: number;
  rate_per_ton: number | null;
  rate_per_m3: number | null;
  min_charge: number | null;
  negotiable: boolean;
  cargo_types: string[];
}

export interface TripList {
  items: TripCard[];
  total: number;
  page: number;
  page_size: number;
}

export interface UpcomingTrip {
  trip_id: number;
  depart_date: string;
  depart_time: string;
  remaining_load_kg: number;
  remaining_volume_m3: number;
}

export interface RouteDetail {
  id: number;
  origin_region: string;
  origin_town: string;
  dest_region: string;
  dest_town: string;
  via_towns: string[];
  est_duration_hours: number;
  cargo_types: string[];
  prohibited_notes: string;
  rate_per_ton: number | null;
  rate_per_m3: number | null;
  min_charge: number | null;
  negotiable: boolean;
  vehicle: {
    vehicle_type: string;
    brand_model: string;
    max_load_kg: number;
    max_volume_m3: number;
    cargo_length_m: number;
    cargo_width_m: number;
    cargo_height_m: number;
  };
  upcoming_trips: UpcomingTrip[];
}

export interface OrderDraft {
  trip_id: number;
  contact_name: string;
  contact_phone: string;
  pickup_region: string;
  pickup_town: string;
  pickup_details: string;
  delivery_region: string;
  delivery_town: string;
  delivery_details: string;
  consignee_name: string;
  consignee_phone: string;
  cargo_name: string;
  cargo_category: string;
  packaging: string;
  pieces: number;
  weight_kg: number;
  volume_m3: number;
  fragile: boolean;
  needs_loading: boolean;
  needs_pickup: boolean;
  pickup_window: string;
  remarks: string;
  photo_ids: string[];
}

export interface OrderParty {
  full_name?: string;
  plate_number?: string;
  phone?: string;
  contact_name?: string;
  contact_phone?: string;
  pickup_details?: string;
  delivery_details?: string;
  consignee_name?: string;
  consignee_phone?: string;
}

export interface OrderView {
  id: number;
  status: string;
  trip_id: number;
  depart_date: string;
  depart_time: string;
  origin_town: string;
  dest_town: string;
  cargo_name: string;
  cargo_category: string;
  packaging: string;
  pieces: number;
  weight_kg: number;
  volume_m3: number;
  fragile: boolean;
  needs_loading: boolean;
  needs_pickup: boolean;
  pickup_window: string;
  remarks: string;
  photo_ids: string[];
  freight_ghs: number | null;
  commission_ghs: number | null;
  pickup_time: string;
  cancel_reason: string;
  created_at: string;
  pickup_town: string;
  delivery_town: string;
  driver: OrderParty | null;
  shipper: OrderParty | null;
}

export interface OrderList {
  items: OrderView[];
  total: number;
  page: number;
  page_size: number;
}

export interface NotificationItem {
  id: number;
  kind: string;
  title: string;
  body: string;
  read: boolean;
  created_at: string;
}

export interface NotificationList {
  items: NotificationItem[];
  total: number;
  unread: number;
  page: number;
  page_size: number;
}

export interface UploadResult {
  id: string;
  url: string;
}
```

Create `h5/src/api/lg.ts`:

```typescript
import { lgApi } from "./lgClient";
import type {
  AuthSession,
  NotificationList,
  OrderDraft,
  OrderList,
  OrderView,
  RouteDetail,
  TripList,
  UploadResult,
} from "./lgTypes";

export interface BrowseParams {
  origin_town?: string;
  dest_town?: string;
  origin_region?: string;
  dest_region?: string;
  date?: string;
  page?: number;
  page_size?: number;
}

export async function requestOtp(phone: string): Promise<{ ok: boolean }> {
  const { data } = await lgApi.post("/auth/request-otp", { phone });
  return data;
}

export async function login(phone: string, code: string): Promise<AuthSession> {
  const { data } = await lgApi.post<AuthSession>("/auth/login", { phone, code });
  return data;
}

export async function me(): Promise<{ id: number; phone: string }> {
  const { data } = await lgApi.get("/auth/me");
  return data;
}

export async function browseTrips(params: BrowseParams): Promise<TripList> {
  const { data } = await lgApi.get<TripList>("/trips", { params });
  return data;
}

export async function routeDetail(id: number | string): Promise<RouteDetail> {
  const { data } = await lgApi.get<RouteDetail>(`/routes/${id}`);
  return data;
}

export async function uploadImage(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await lgApi.post<UploadResult>("/uploads", form);
  return data;
}

export async function submitOrder(draft: OrderDraft): Promise<OrderView> {
  const { data } = await lgApi.post<OrderView>("/orders", draft);
  return data;
}

export async function myOrders(page = 1): Promise<OrderList> {
  const { data } = await lgApi.get<OrderList>("/orders/mine", { params: { page } });
  return data;
}

export async function orderDetail(id: number | string): Promise<OrderView> {
  const { data } = await lgApi.get<OrderView>(`/orders/${id}`);
  return data;
}

export async function cancelOrder(id: number | string, reason: string): Promise<OrderView> {
  const { data } = await lgApi.post<OrderView>(`/orders/${id}/cancel`, { reason });
  return data;
}

export async function listNotifications(page = 1): Promise<NotificationList> {
  const { data } = await lgApi.get<NotificationList>("/notifications", { params: { page } });
  return data;
}

export async function markNotificationRead(id: number): Promise<void> {
  await lgApi.post(`/notifications/${id}/read`);
}
```

Create `h5/src/stores/auth.ts`:

```typescript
import { defineStore } from "pinia";

import { login, requestOtp } from "../api/lg";
import { LG_TOKEN_KEY } from "../api/lgClient";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem(LG_TOKEN_KEY) ?? "",
    phone: "",
    userId: 0,
  }),
  getters: {
    loggedIn: (s) => !!s.token,
  },
  actions: {
    async requestCode(phone: string) {
      await requestOtp(phone);
    },
    async signIn(phone: string, code: string) {
      const session = await login(phone, code);
      this.token = session.access_token;
      this.phone = session.phone;
      this.userId = session.user_id;
      localStorage.setItem(LG_TOKEN_KEY, session.access_token);
    },
    signOut() {
      this.token = "";
      this.phone = "";
      this.userId = 0;
      localStorage.removeItem(LG_TOKEN_KEY);
    },
  },
});
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run tests/authStore.spec.ts` → 5 PASS

- [ ] **Step 5: Commit**

```bash
cd .. && git add h5/src/api h5/src/stores/auth.ts h5/tests/authStore.spec.ts
git commit -m "feat(h5): lg api client, types, and auth store"
```

---

### Task 2: Router restructure, TabBar, and shell views

**Files:**
- Create: `h5/src/components/TabBar.vue`, `h5/src/views/LogisticsView.vue` (placeholder), `h5/src/views/MeView.vue` (placeholder)
- Modify: `h5/src/router.ts`, `h5/src/views/HomeView.vue`, `h5/tests/helpers.ts`
- Test: `h5/tests/tabBar.spec.ts`

- [ ] **Step 1: Write the failing test**

Append to `h5/tests/helpers.ts`:

```typescript
import { createRouter, createWebHistory } from "vue-router";

export function testRouter() {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: "/", name: "news", component: { template: "<div />" } },
      { path: "/lg", name: "logistics", component: { template: "<div />" } },
      { path: "/me", name: "me", component: { template: "<div />" } },
      { path: "/me/login", name: "login", component: { template: "<div />" } },
      { path: "/me/orders", name: "my-orders", component: { template: "<div />" } },
      { path: "/me/orders/:id", name: "order-detail", component: { template: "<div />" } },
      { path: "/me/notifications", name: "notifications", component: { template: "<div />" } },
      { path: "/lg/trip/:id", name: "trip", component: { template: "<div />" } },
      { path: "/lg/order/new/:tripId", name: "order-new", component: { template: "<div />" } },
    ],
  });
}

export function setLgToken(token = "test-token") {
  localStorage.setItem("lg-token", token);
}
```

Create `h5/tests/tabBar.spec.ts`:

```typescript
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import TabBar from "../src/components/TabBar.vue";
import { freshPinia, testI18n, testRouter } from "./helpers";

async function mountTabBar(path = "/") {
  const router = testRouter();
  router.push(path);
  await router.isReady();
  const w = mount(TabBar, { global: { plugins: [freshPinia(), testI18n("en"), router] } });
  return { w, router };
}

describe("TabBar", () => {
  it("renders three tabs", async () => {
    const { w } = await mountTabBar();
    expect(w.findAll(".tab")).toHaveLength(3);
  });

  it("marks the active tab from the current route", async () => {
    const { w } = await mountTabBar("/lg");
    const active = w.find(".tab.active");
    expect(active.text()).toContain("Logistics");
  });

  it("navigates when a tab is tapped", async () => {
    const { w, router } = await mountTabBar("/");
    await w.findAll(".tab")[2].trigger("click");
    await flushPromises();
    expect(router.currentRoute.value.name).toBe("me");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/tabBar.spec.ts`
Expected: FAIL — cannot resolve `../src/components/TabBar.vue`

- [ ] **Step 3: Write the implementation**

Create `h5/src/components/TabBar.vue`:

```vue
<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";

const { t } = useI18n();
const route = useRoute();

const tabs = computed(() => [
  { name: "news", to: "/", label: t("lg.tabs.news"), icon: "M4 10l8-6 8 6v9a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1z" },
  { name: "logistics", to: "/lg", label: t("lg.tabs.logistics"), icon: "M3 7h10v7H3zM13 10h4l3 3v1h-7zM7 18a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM17 18a2 2 0 1 0 0-4 2 2 0 0 0 0 4z" },
  { name: "me", to: "/me", label: t("lg.tabs.me"), icon: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 20a8 8 0 0 1 16 0z" },
]);

const activeRoot = computed(() => {
  const p = route.path;
  if (p === "/" || p.startsWith("/article")) return "news";
  if (p.startsWith("/lg")) return "logistics";
  return "me";
});
</script>

<template>
  <nav class="tabbar">
    <RouterLink
      v-for="tab in tabs"
      :key="tab.name"
      class="tab"
      :class="{ active: activeRoot === tab.name }"
      :to="tab.to"
    >
      <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
        <path :d="tab.icon" />
      </svg>
      <span>{{ tab.label }}</span>
    </RouterLink>
  </nav>
</template>

<style scoped>
.tabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 20;
  display: flex;
  background: var(--bg);
  border-top: 1px solid var(--border);
  padding-bottom: env(safe-area-inset-bottom, 0);
}
.tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 7px 0;
  font-size: 11px;
  color: var(--text-muted);
  text-decoration: none;
}
.tab.active {
  color: var(--brand-500);
}
</style>
```

Create `h5/src/views/LogisticsView.vue` (placeholder replaced in Task 5):

```vue
<script setup lang="ts">
import TabBar from "../components/TabBar.vue";
</script>

<template>
  <div class="page">
    <main class="body"></main>
    <TabBar />
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: var(--surface);
}
.body {
  padding-bottom: 64px;
}
</style>
```

Create `h5/src/views/MeView.vue` (placeholder replaced in Task 4):

```vue
<script setup lang="ts">
import TabBar from "../components/TabBar.vue";
</script>

<template>
  <div class="page">
    <main class="body"></main>
    <TabBar />
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: var(--surface);
}
.body {
  padding-bottom: 64px;
}
</style>
```

Modify `h5/src/router.ts` to the full route map (auth guard added; guarded routes carry `meta.requiresAuth`):

```typescript
import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "./stores/auth";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "news", component: () => import("./views/HomeView.vue") },
    { path: "/article/:id", name: "article", component: () => import("./views/ArticleView.vue") },
    { path: "/lg", name: "logistics", component: () => import("./views/LogisticsView.vue") },
    { path: "/lg/trip/:id", name: "trip", component: () => import("./views/TripDetailView.vue") },
    {
      path: "/lg/order/new/:tripId",
      name: "order-new",
      component: () => import("./views/OrderFormView.vue"),
      meta: { requiresAuth: true },
    },
    { path: "/me", name: "me", component: () => import("./views/MeView.vue") },
    { path: "/me/login", name: "login", component: () => import("./views/LoginView.vue") },
    {
      path: "/me/orders",
      name: "my-orders",
      component: () => import("./views/MyOrdersView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/me/orders/:id",
      name: "order-detail",
      component: () => import("./views/OrderDetailView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/me/notifications",
      name: "notifications",
      component: () => import("./views/NotificationsView.vue"),
      meta: { requiresAuth: true },
    },
  ],
});

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !useAuthStore().loggedIn) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
});
```

Modify `h5/src/views/HomeView.vue` — render the TabBar and reserve space. Add the import
after the existing `NewsGrid` import:

```typescript
import TabBar from "../components/TabBar.vue";
```

In the template, add `<TabBar />` as the last child inside `<div class="home">` (after the
`</van-pull-refresh>`), and add bottom padding to `.home`:

```css
.home {
  min-height: 100vh;
  background: var(--surface);
  padding-bottom: 64px;
}
```

**Note:** Task 2 references view files created in later tasks (`TripDetailView`, `OrderFormView`,
etc.) via lazy `import()`. Lazy imports are only resolved on navigation, so the app builds and
the News/Logistics/Me tabs work now; the other routes light up as their tasks land. To keep
`vue-tsc` green in the meantime, create each not-yet-built view as a one-line stub now:

```bash
cd h5/src/views
for f in TripDetailView OrderFormView LoginView MyOrdersView OrderDetailView NotificationsView; do
  printf '<template><div /></template>\n' > "$f.vue"
done
cd ../../..
```

Each stub is fully replaced by its task below.

- [ ] **Step 4: Run tests + typecheck**

Run: `npx vitest run tests/tabBar.spec.ts` → 3 PASS
Run: `npx vue-tsc --noEmit` → exit 0 (i18n `lg.*` keys resolve at runtime, not compile time)

- [ ] **Step 5: Commit**

```bash
cd .. && git add h5/src/router.ts h5/src/components/TabBar.vue h5/src/views h5/tests/helpers.ts h5/tests/tabBar.spec.ts
git commit -m "feat(h5): three-tab shell, router restructure, auth guard"
```

---

### Task 3: Logistics i18n namespace

**Files:**
- Modify: `h5/src/i18n/en.ts`, `h5/src/i18n/zh.ts`

(Configuration data — no test; strings are exercised by the component tests in later tasks.)

- [ ] **Step 1: Add the `lg` namespace to `h5/src/i18n/en.ts`**

Add this `lg` key to the exported object (before the closing brace):

```typescript
  lg: {
    tabs: { news: "News", logistics: "Logistics", me: "Me" },
    browse: {
      title: "Find transport",
      from: "From (town)",
      to: "To (town)",
      date: "Date",
      search: "Search",
      clear: "Clear",
      empty: "No trips match your search",
      remaining: "Remaining",
      perTon: "/ton",
      perM3: "/m³",
      negotiable: "Negotiable",
      book: "Request this trip",
      departs: "Departs",
      duration: "~{h}h",
    },
    order: {
      title: "Transport request",
      contact: "Your contact",
      contactName: "Contact name",
      contactPhone: "Contact phone",
      pickup: "Pickup",
      delivery: "Delivery",
      region: "Region",
      town: "Town",
      addressDetails: "Address details",
      consignee: "Consignee",
      consigneeName: "Consignee name",
      consigneePhone: "Consignee phone",
      cargo: "Cargo",
      cargoName: "Cargo name",
      category: "Category",
      packaging: "Packaging",
      pieces: "Pieces",
      weight: "Weight (kg)",
      volume: "Volume (m³)",
      fragile: "Fragile",
      needsLoading: "Loading/unloading help",
      needsPickup: "Pickup service needed",
      pickupWindow: "Preferred pickup time",
      photos: "Cargo photos (optional)",
      remarks: "Remarks",
      submit: "Submit request",
      submitting: "Submitting…",
      submitted: "Request submitted — customer service will contact you.",
      priceNote: "Indicative price. Final price is confirmed by customer service.",
      disclaimer:
        "ZokoDaily matches you with drivers only. Freight is agreed and paid directly with the driver.",
      overCapacity: "This trip doesn't have enough remaining space.",
      packagingOptions: {
        carton: "Carton",
        pallet: "Pallet",
        bag: "Bag",
        drum: "Drum",
        loose: "Loose",
        other: "Other",
      },
    },
    auth: {
      loginTitle: "Sign in",
      phone: "Phone number",
      phoneHint: "Ghana mobile number",
      sendCode: "Send code",
      resendIn: "Resend in {s}s",
      code: "Verification code",
      verify: "Verify & sign in",
      codeSent: "Code sent by SMS",
      invalid: "Invalid phone or code",
    },
    me: {
      guest: "Sign in to place and track orders",
      signIn: "Sign in",
      myOrders: "My orders",
      notifications: "Notifications",
      signOut: "Sign out",
      account: "Account",
    },
    orders: {
      mineTitle: "My orders",
      empty: "You have no orders yet",
      detailTitle: "Order",
      cargo: "Cargo",
      trip: "Trip",
      freight: "Freight",
      driver: "Driver",
      plate: "Vehicle",
      phone: "Phone",
      pickupTime: "Pickup time",
      cancel: "Cancel order",
      cancelReason: "Reason for cancellation",
      cancelConfirm: "Cancel this order?",
      cancelled: "Order cancelled",
      contactHidden: "Driver contact appears once the driver accepts.",
      status: {
        submitted: "Submitted",
        price_confirmed: "Price confirmed",
        awaiting_pickup: "Awaiting pickup",
        in_transit: "In transit",
        delivered: "Delivered",
        completed: "Completed",
        cancelled: "Cancelled",
        exception_closed: "Closed",
      },
    },
    notif: {
      title: "Notifications",
      empty: "No notifications",
      markRead: "Mark read",
    },
    common: {
      back: "Back",
      loading: "Loading…",
      retry: "Retry",
      required: "This field is required",
    },
  },
```

- [ ] **Step 2: Add the same namespace, translated, to `h5/src/i18n/zh.ts`**

Add this `lg` key to the exported object:

```typescript
  lg: {
    tabs: { news: "新闻", logistics: "物流", me: "我的" },
    browse: {
      title: "寻找运力",
      from: "出发地（城镇）",
      to: "目的地（城镇）",
      date: "日期",
      search: "搜索",
      clear: "清除",
      empty: "没有符合条件的行程",
      remaining: "剩余",
      perTon: "/吨",
      perM3: "/立方米",
      negotiable: "面议",
      book: "预约此行程",
      departs: "发车",
      duration: "约{h}小时",
    },
    order: {
      title: "运输需求",
      contact: "您的联系方式",
      contactName: "联系人",
      contactPhone: "联系电话",
      pickup: "取货",
      delivery: "送达",
      region: "地区",
      town: "城镇",
      addressDetails: "详细地址",
      consignee: "收货人",
      consigneeName: "收货人姓名",
      consigneePhone: "收货人电话",
      cargo: "货物",
      cargoName: "货物名称",
      category: "类别",
      packaging: "包装",
      pieces: "件数",
      weight: "重量（公斤）",
      volume: "体积（立方米）",
      fragile: "易碎",
      needsLoading: "需要装卸",
      needsPickup: "需要上门取货",
      pickupWindow: "期望取货时间",
      photos: "货物照片（可选）",
      remarks: "备注",
      submit: "提交需求",
      submitting: "提交中…",
      submitted: "需求已提交——客服会与您联系。",
      priceNote: "参考价格，最终价格由客服确认。",
      disclaimer: "ZokoDaily 仅提供司机撮合，运费由您与司机直接商定并支付。",
      overCapacity: "该行程剩余空间不足。",
      packagingOptions: {
        carton: "纸箱",
        pallet: "托盘",
        bag: "袋装",
        drum: "桶装",
        loose: "散装",
        other: "其他",
      },
    },
    auth: {
      loginTitle: "登录",
      phone: "手机号",
      phoneHint: "加纳手机号",
      sendCode: "获取验证码",
      resendIn: "{s}秒后重发",
      code: "验证码",
      verify: "验证并登录",
      codeSent: "验证码已通过短信发送",
      invalid: "手机号或验证码有误",
    },
    me: {
      guest: "登录后可下单并跟踪订单",
      signIn: "登录",
      myOrders: "我的订单",
      notifications: "通知",
      signOut: "退出登录",
      account: "账户",
    },
    orders: {
      mineTitle: "我的订单",
      empty: "暂无订单",
      detailTitle: "订单",
      cargo: "货物",
      trip: "行程",
      freight: "运费",
      driver: "司机",
      plate: "车牌",
      phone: "电话",
      pickupTime: "取货时间",
      cancel: "取消订单",
      cancelReason: "取消原因",
      cancelConfirm: "确认取消该订单？",
      cancelled: "订单已取消",
      contactHidden: "司机接单后可见其联系方式。",
      status: {
        submitted: "已提交",
        price_confirmed: "已确认价格",
        awaiting_pickup: "待取货",
        in_transit: "运输中",
        delivered: "已送达",
        completed: "已完成",
        cancelled: "已取消",
        exception_closed: "已关闭",
      },
    },
    notif: {
      title: "通知",
      empty: "暂无通知",
      markRead: "标为已读",
    },
    common: {
      back: "返回",
      loading: "加载中…",
      retry: "重试",
      required: "此项必填",
    },
  },
```

- [ ] **Step 3: Verify typecheck + existing tests still pass**

Run: `cd h5 && npx vue-tsc --noEmit` → exit 0
Run: `npx vitest run` → all existing specs PASS

- [ ] **Step 4: Commit**

```bash
cd .. && git add h5/src/i18n
git commit -m "feat(h5): logistics i18n namespace (en + zh)"
```

---

### Task 4: Login flow and Me hub

**Files:**
- Replace: `h5/src/views/LoginView.vue`, `h5/src/views/MeView.vue`
- Modify: `h5/src/main.ts`
- Test: `h5/tests/loginView.spec.ts`, `h5/tests/meView.spec.ts`

- [ ] **Step 1: Write the failing tests**

Create `h5/tests/loginView.spec.ts`:

```typescript
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginView from "../src/views/LoginView.vue";
import { useAuthStore } from "../src/stores/auth";
import { freshPinia, testI18n, testRouter } from "./helpers";

vi.mock("../src/api/lg", () => ({
  requestOtp: vi.fn(() => Promise.resolve({ ok: true })),
  login: vi.fn(() =>
    Promise.resolve({ access_token: "tok", token_type: "bearer", user_id: 1, phone: "+233241234567" }),
  ),
}));
import { login, requestOtp } from "../src/api/lg";

async function mountLogin() {
  const router = testRouter();
  router.push("/me/login");
  await router.isReady();
  const w = mount(LoginView, { global: { plugins: [freshPinia(), testI18n("en"), router] } });
  return { w, router };
}

describe("LoginView", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("requests a code for the entered phone", async () => {
    const { w } = await mountLogin();
    await w.find("input[type=tel]").setValue("0241234567");
    await w.find(".send-code").trigger("click");
    expect(requestOtp).toHaveBeenCalledWith("0241234567");
    await flushPromises();
    expect(w.find("input[inputmode=numeric]").exists()).toBe(true);
  });

  it("verifies the code, signs in, and redirects", async () => {
    const { w, router } = await mountLogin();
    const spy = vi.spyOn(router, "replace");
    await w.find("input[type=tel]").setValue("0241234567");
    await w.find(".send-code").trigger("click");
    await flushPromises();
    await w.find("input[inputmode=numeric]").setValue("123456");
    await w.find(".verify").trigger("click");
    await flushPromises();
    expect(login).toHaveBeenCalledWith("0241234567", "123456");
    expect(useAuthStore().loggedIn).toBe(true);
    expect(spy).toHaveBeenCalled();
  });
});
```

Create `h5/tests/meView.spec.ts`:

```typescript
import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it } from "vitest";

import MeView from "../src/views/MeView.vue";
import { useAuthStore } from "../src/stores/auth";
import { freshPinia, testI18n, testRouter } from "./helpers";

async function mountMe() {
  const router = testRouter();
  router.push("/me");
  await router.isReady();
  const pinia = freshPinia();
  const w = mount(MeView, { global: { plugins: [pinia, testI18n("en"), router] } });
  return { w };
}

describe("MeView", () => {
  beforeEach(() => localStorage.clear());

  it("shows a sign-in prompt when logged out", async () => {
    const { w } = await mountMe();
    expect(w.text()).toContain("Sign in");
    expect(w.find(".menu").exists()).toBe(false);
  });

  it("shows the account menu and can sign out when logged in", async () => {
    const { w } = await mountMe();
    const auth = useAuthStore();
    auth.token = "tok";
    auth.phone = "+233241234567";
    await w.vm.$nextTick();
    expect(w.find(".menu").exists()).toBe(true);
    await w.find(".sign-out").trigger("click");
    expect(auth.loggedIn).toBe(false);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run tests/loginView.spec.ts tests/meView.spec.ts`
Expected: FAIL — stub views render empty `<div />`

- [ ] **Step 3: Write the implementation**

Replace `h5/src/views/LoginView.vue`:

```vue
<script setup lang="ts">
import { onUnmounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";

const { t } = useI18n();
const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const phone = ref("");
const code = ref("");
const step = ref<"phone" | "code">("phone");
const error = ref("");
const busy = ref(false);
const cooldown = ref(0);
let timer: ReturnType<typeof setInterval> | undefined;

function startCooldown() {
  cooldown.value = 60;
  timer = setInterval(() => {
    cooldown.value -= 1;
    if (cooldown.value <= 0 && timer) clearInterval(timer);
  }, 1000);
}
onUnmounted(() => timer && clearInterval(timer));

async function sendCode() {
  if (busy.value || cooldown.value > 0) return;
  error.value = "";
  busy.value = true;
  try {
    await auth.requestCode(phone.value.trim());
    step.value = "code";
    startCooldown();
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    busy.value = false;
  }
}

async function verify() {
  if (busy.value) return;
  error.value = "";
  busy.value = true;
  try {
    await auth.signIn(phone.value.trim(), code.value.trim());
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/me";
    router.replace(redirect);
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="login">
    <header class="bar">
      <button class="back" :aria-label="t('lg.common.back')" @click="router.back()">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </button>
      <h1>{{ t("lg.auth.loginTitle") }}</h1>
    </header>

    <div class="form">
      <label class="field">
        <span>{{ t("lg.auth.phone") }}</span>
        <input v-model="phone" type="tel" inputmode="tel" :placeholder="t('lg.auth.phoneHint')" :disabled="step === 'code'" />
      </label>

      <button v-if="step === 'phone'" class="send-code primary" :disabled="busy || !phone" @click="sendCode">
        {{ t("lg.auth.sendCode") }}
      </button>

      <template v-else>
        <label class="field">
          <span>{{ t("lg.auth.code") }}</span>
          <input v-model="code" inputmode="numeric" maxlength="6" :placeholder="t('lg.auth.codeSent')" />
        </label>
        <button class="verify primary" :disabled="busy || code.length < 6" @click="verify">
          {{ t("lg.auth.verify") }}
        </button>
        <button class="resend" :disabled="cooldown > 0 || busy" @click="sendCode">
          {{ cooldown > 0 ? t("lg.auth.resendIn", { s: cooldown }) : t("lg.auth.sendCode") }}
        </button>
      </template>

      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<style scoped>
.login { min-height: 100vh; background: var(--bg); }
.bar { display: flex; align-items: center; gap: 8px; padding: 12px 14px; border-bottom: 1px solid var(--border); }
.bar h1 { font-size: 16px; font-weight: 500; }
.back { border: 0; background: transparent; color: var(--text-primary); display: flex; }
.form { padding: 20px 16px; display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-secondary); }
.field input {
  border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px;
  font-size: 15px; background: var(--surface); outline: none;
}
.primary {
  border: 0; border-radius: var(--radius-pill); background: var(--brand-500); color: #fff;
  padding: 11px; font-size: 15px; font-weight: 500;
}
.primary:disabled { opacity: 0.5; }
.resend { border: 0; background: transparent; color: var(--brand-500); font-size: 13px; padding: 4px; }
.resend:disabled { color: var(--text-muted); }
.error { color: #c0392b; font-size: 13px; text-align: center; }
</style>
```

Replace `h5/src/views/MeView.vue`:

```vue
<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import TabBar from "../components/TabBar.vue";
import { useAuthStore } from "../stores/auth";

const { t } = useI18n();
const auth = useAuthStore();
const router = useRouter();

function signOut() {
  auth.signOut();
}
</script>

<template>
  <div class="page">
    <header class="hero">
      <h1>{{ t("lg.me.account") }}</h1>
      <p v-if="auth.loggedIn" class="phone">{{ auth.phone }}</p>
    </header>

    <div v-if="!auth.loggedIn" class="guest">
      <p>{{ t("lg.me.guest") }}</p>
      <button class="primary" @click="router.push('/me/login')">{{ t("lg.me.signIn") }}</button>
    </div>

    <nav v-else class="menu">
      <RouterLink class="row" to="/me/orders">{{ t("lg.me.myOrders") }}</RouterLink>
      <RouterLink class="row" to="/me/notifications">{{ t("lg.me.notifications") }}</RouterLink>
      <button class="row sign-out" @click="signOut">{{ t("lg.me.signOut") }}</button>
    </nav>

    <TabBar />
  </div>
</template>

<style scoped>
.page { min-height: 100vh; background: var(--surface); padding-bottom: 64px; }
.hero { background: var(--brand-700); color: #fff; padding: 28px 18px 22px; }
.hero h1 { font-size: 20px; font-weight: 600; }
.phone { margin-top: 4px; font-size: 13px; opacity: 0.85; }
.guest { padding: 40px 20px; text-align: center; color: var(--text-secondary); display: flex; flex-direction: column; gap: 16px; align-items: center; }
.primary { border: 0; border-radius: var(--radius-pill); background: var(--brand-500); color: #fff; padding: 10px 28px; font-size: 15px; }
.menu { margin-top: 10px; background: var(--bg); }
.row {
  display: block; width: 100%; text-align: left; padding: 15px 18px; font-size: 15px;
  color: var(--text-primary); text-decoration: none; border: 0; border-bottom: 1px solid var(--border); background: var(--bg);
}
.sign-out { color: #c0392b; }
</style>
```

Modify `h5/src/main.ts` — after `.use(router)` is applied and before `.mount`, wire the
401 handler. Replace the final `createApp(...).mount("#app")` chain with:

```typescript
import { useAuthStore } from "./stores/auth";

const app = createApp(App)
  .use(createPinia())
  .use(router)
  .use(i18n)
  .use(Swipe)
  .use(SwipeItem)
  .use(PullRefresh)
  .use(List)
  .use(Popup);

// A 401 from any /api/lg call clears the session and bounces to login.
window.addEventListener("lg-unauthorized", () => {
  useAuthStore().signOut();
  if (router.currentRoute.value.meta.requiresAuth) {
    router.replace({ name: "login", query: { redirect: router.currentRoute.value.fullPath } });
  }
});

app.mount("#app");
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run tests/loginView.spec.ts tests/meView.spec.ts` → all PASS

- [ ] **Step 5: Commit**

```bash
cd .. && git add h5/src/views/LoginView.vue h5/src/views/MeView.vue h5/src/main.ts h5/tests/loginView.spec.ts h5/tests/meView.spec.ts
git commit -m "feat(h5): phone+OTP login flow and account hub"
```

---

### Task 5: Trip browse store + Logistics view

**Files:**
- Create: `h5/src/stores/lgFeed.ts`, `h5/src/components/TripCard.vue`
- Replace: `h5/src/views/LogisticsView.vue`
- Test: `h5/tests/lgFeedStore.spec.ts`

- [ ] **Step 1: Write the failing test**

Create `h5/tests/lgFeedStore.spec.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useLgFeedStore } from "../src/stores/lgFeed";
import type { TripCard, TripList } from "../src/api/lgTypes";
import { freshPinia } from "./helpers";

vi.mock("../src/api/lg", () => ({ browseTrips: vi.fn() }));
import { browseTrips } from "../src/api/lg";
const mockBrowse = vi.mocked(browseTrips);

function trip(id: number): TripCard {
  return {
    trip_id: id, route_id: 1, depart_date: "2026-07-14", depart_time: "08:00",
    origin_region: "Greater Accra", origin_town: "Accra", dest_region: "Ashanti",
    dest_town: "Kumasi", via_towns: [], est_duration_hours: 6, vehicle_type: "box_truck",
    brand_model: "Kia K2700", remaining_load_kg: 2000, remaining_volume_m3: 10,
    rate_per_ton: 350, rate_per_m3: 60, min_charge: 80, negotiable: false, cargo_types: ["general"],
  };
}
function page(items: TripCard[], p: number, total: number): TripList {
  return { items, total, page: p, page_size: 20 };
}

describe("lgFeed store", () => {
  beforeEach(() => {
    freshPinia();
    mockBrowse.mockReset();
  });

  it("refresh loads page 1 with filters", async () => {
    mockBrowse.mockResolvedValueOnce(page([trip(1), trip(2)], 1, 3));
    const feed = useLgFeedStore();
    feed.filters.dest_town = "Kumasi";
    await feed.refresh();
    expect(mockBrowse).toHaveBeenCalledWith({ page: 1, page_size: 20, dest_town: "Kumasi" });
    expect(feed.items).toHaveLength(2);
    expect(feed.finished).toBe(false);
  });

  it("loadMore appends and finishes at total", async () => {
    mockBrowse
      .mockResolvedValueOnce(page([trip(1), trip(2)], 1, 3))
      .mockResolvedValueOnce(page([trip(3)], 2, 3));
    const feed = useLgFeedStore();
    await feed.refresh();
    await feed.loadMore();
    expect(feed.items.map((t) => t.trip_id)).toEqual([1, 2, 3]);
    expect(feed.finished).toBe(true);
  });

  it("guards against concurrent loads via inFlight, not the van-list flag", async () => {
    mockBrowse.mockResolvedValueOnce(page([trip(1)], 1, 1));
    const feed = useLgFeedStore();
    feed.loading = true; // van-list pre-sets this before emitting @load
    await feed.loadMore();
    expect(mockBrowse).toHaveBeenCalledTimes(1);
    expect(feed.items).toHaveLength(1);
    expect(feed.loading).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/lgFeedStore.spec.ts`
Expected: FAIL — cannot resolve `../src/stores/lgFeed`

- [ ] **Step 3: Write the implementation**

Create `h5/src/stores/lgFeed.ts` (mirrors the news feed store's `inFlight`/`loading`
separation — the fix from the pull-to-refresh bug):

```typescript
import { defineStore } from "pinia";

import { browseTrips, type BrowseParams } from "../api/lg";
import type { TripCard } from "../api/lgTypes";

const PAGE_SIZE = 20;

interface Filters {
  origin_town: string;
  dest_town: string;
  date: string;
}

export const useLgFeedStore = defineStore("lgFeed", {
  state: () => ({
    items: [] as TripCard[],
    page: 0,
    total: 0,
    loading: false, // bound to van-list v-model:loading
    inFlight: false, // real dedupe guard
    error: "",
    filters: { origin_town: "", dest_town: "", date: "" } as Filters,
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
      if (this.inFlight) return;
      this.inFlight = true;
      this.loading = true;
      this.error = "";
      try {
        const params: BrowseParams = { page: this.page + 1, page_size: PAGE_SIZE };
        if (this.filters.origin_town) params.origin_town = this.filters.origin_town;
        if (this.filters.dest_town) params.dest_town = this.filters.dest_town;
        if (this.filters.date) params.date = this.filters.date;
        const data = await browseTrips(params);
        this.page = data.page;
        this.total = data.total;
        this.items.push(...data.items);
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e);
      } finally {
        this.inFlight = false;
        this.loading = false;
      }
    },
  },
});
```

Create `h5/src/components/TripCard.vue`:

```vue
<script setup lang="ts">
import { useI18n } from "vue-i18n";

import type { TripCard } from "../api/lgTypes";

defineProps<{ trip: TripCard }>();
const { t } = useI18n();
</script>

<template>
  <RouterLink class="card" :to="`/lg/trip/${trip.trip_id}`">
    <div class="lane">
      <span class="town">{{ trip.origin_town }}</span>
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M5 12h14M13 6l6 6-6 6" />
      </svg>
      <span class="town">{{ trip.dest_town }}</span>
    </div>
    <p class="when">{{ t("lg.browse.departs") }} {{ trip.depart_date }} {{ trip.depart_time }} · {{ t("lg.browse.duration", { h: trip.est_duration_hours }) }}</p>
    <div class="meta">
      <span class="cap">{{ t("lg.browse.remaining") }} {{ trip.remaining_load_kg }}kg · {{ trip.remaining_volume_m3 }}m³</span>
      <span class="price">
        <template v-if="trip.negotiable">{{ t("lg.browse.negotiable") }}</template>
        <template v-else-if="trip.rate_per_ton">GHS {{ trip.rate_per_ton }}{{ t("lg.browse.perTon") }}</template>
        <template v-else-if="trip.rate_per_m3">GHS {{ trip.rate_per_m3 }}{{ t("lg.browse.perM3") }}</template>
      </span>
    </div>
    <p class="veh">{{ trip.vehicle_type }} · {{ trip.brand_model }}</p>
  </RouterLink>
</template>

<style scoped>
.card { display: block; background: var(--bg); border-radius: var(--radius-card); padding: 12px 14px; margin: 8px 12px; text-decoration: none; color: var(--text-primary); border: 1px solid var(--border); }
.lane { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; color: var(--brand-700); }
.when { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
.meta { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }
.cap { font-size: 12.5px; color: var(--text-secondary); }
.price { font-size: 13px; font-weight: 600; color: var(--brand-500); }
.veh { font-size: 11.5px; color: var(--text-muted); margin-top: 4px; }
</style>
```

Replace `h5/src/views/LogisticsView.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";

import TabBar from "../components/TabBar.vue";
import TripCard from "../components/TripCard.vue";
import { useLgFeedStore } from "../stores/lgFeed";

const { t } = useI18n();
const feed = useLgFeedStore();

const listLoading = computed({
  get: () => feed.loading,
  set: (v: boolean) => (feed.loading = v),
});

function applyFilters() {
  feed.refresh();
}
function clearFilters() {
  feed.filters.origin_town = "";
  feed.filters.dest_town = "";
  feed.filters.date = "";
  feed.refresh();
}

onMounted(() => {
  if (!feed.items.length) feed.refresh();
});
</script>

<template>
  <div class="page">
    <header class="filters">
      <h1>{{ t("lg.browse.title") }}</h1>
      <div class="row">
        <input v-model="feed.filters.origin_town" :placeholder="t('lg.browse.from')" @keyup.enter="applyFilters" />
        <input v-model="feed.filters.dest_town" :placeholder="t('lg.browse.to')" @keyup.enter="applyFilters" />
      </div>
      <div class="row">
        <input v-model="feed.filters.date" type="date" :aria-label="t('lg.browse.date')" />
        <button class="search" @click="applyFilters">{{ t("lg.browse.search") }}</button>
        <button class="clear" @click="clearFilters">{{ t("lg.browse.clear") }}</button>
      </div>
    </header>

    <van-list
      v-model:loading="listLoading"
      :finished="feed.finished"
      finished-text=""
      @load="feed.loadMore()"
    >
      <TripCard v-for="tr in feed.items" :key="tr.trip_id" :trip="tr" />
      <p v-if="feed.finished && !feed.items.length" class="empty">{{ t("lg.browse.empty") }}</p>
    </van-list>

    <TabBar />
  </div>
</template>

<style scoped>
.page { min-height: 100vh; background: var(--surface); padding-bottom: 64px; }
.filters { background: var(--bg); padding: 14px 12px 12px; border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10; }
.filters h1 { font-size: 16px; font-weight: 600; margin-bottom: 10px; }
.row { display: flex; gap: 8px; margin-bottom: 8px; }
.row input { flex: 1; min-width: 0; border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; font-size: 13.5px; background: var(--surface); outline: none; }
.search { border: 0; border-radius: 8px; background: var(--brand-500); color: #fff; padding: 8px 16px; font-size: 13px; }
.clear { border: 1px solid var(--border); border-radius: 8px; background: var(--bg); color: var(--text-secondary); padding: 8px 12px; font-size: 13px; }
.empty { text-align: center; color: var(--text-muted); padding: 50px 0; font-size: 13px; }
</style>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run tests/lgFeedStore.spec.ts` → 3 PASS

- [ ] **Step 5: Commit**

```bash
cd .. && git add h5/src/stores/lgFeed.ts h5/src/components/TripCard.vue h5/src/views/LogisticsView.vue h5/tests/lgFeedStore.spec.ts
git commit -m "feat(h5): trip browse store and logistics listing"
```

---

### Task 6: Trip / route detail view

**Files:**
- Replace: `h5/src/views/TripDetailView.vue`
- Test: `h5/tests/tripDetail.spec.ts`

- [ ] **Step 1: Write the failing test**

Create `h5/tests/tripDetail.spec.ts`:

```typescript
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import TripDetailView from "../src/views/TripDetailView.vue";
import type { RouteDetail } from "../src/api/lgTypes";
import { freshPinia, testI18n, testRouter } from "./helpers";

const detail: RouteDetail = {
  id: 1, origin_region: "Greater Accra", origin_town: "Accra", dest_region: "Ashanti",
  dest_town: "Kumasi", via_towns: ["Nkawkaw"], est_duration_hours: 6, cargo_types: ["general"],
  prohibited_notes: "", rate_per_ton: 350, rate_per_m3: 60, min_charge: 80, negotiable: false,
  vehicle: { vehicle_type: "box_truck", brand_model: "Kia K2700", max_load_kg: 2000, max_volume_m3: 10, cargo_length_m: 3.1, cargo_width_m: 1.7, cargo_height_m: 1.8 },
  upcoming_trips: [
    { trip_id: 5, depart_date: "2026-07-14", depart_time: "08:00", remaining_load_kg: 2000, remaining_volume_m3: 10 },
  ],
};

vi.mock("../src/api/lg", () => ({ routeDetail: vi.fn(() => Promise.resolve(detail)) }));

async function mountDetail() {
  const router = testRouter();
  router.push("/lg/trip/5");
  await router.isReady();
  const w = mount(TripDetailView, { global: { plugins: [freshPinia(), testI18n("en"), router] } });
  await flushPromises();
  return { w, router };
}

describe("TripDetailView", () => {
  it("shows the lane, vehicle, and an upcoming trip", async () => {
    const { w } = await mountDetail();
    expect(w.text()).toContain("Accra");
    expect(w.text()).toContain("Kumasi");
    expect(w.text()).toContain("box_truck");
    expect(w.find(".trip-row").exists()).toBe(true);
  });

  it("books the focused trip", async () => {
    const { w, router } = await mountDetail();
    const spy = vi.spyOn(router, "push");
    await w.find(".book").trigger("click");
    expect(spy).toHaveBeenCalledWith("/lg/order/new/5");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/tripDetail.spec.ts`
Expected: FAIL — stub renders empty `<div />`

- [ ] **Step 3: Write the implementation**

Replace `h5/src/views/TripDetailView.vue`:

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { routeDetail } from "../api/lg";
import type { RouteDetail } from "../api/lgTypes";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const detail = ref<RouteDetail | null>(null);
const error = ref("");

onMounted(async () => {
  try {
    // Detail is keyed by route id. Browse cards pass it as ?route=<id>; on a cold
    // load without the query we fall back to treating the path param as the route id.
    const routeId = typeof route.query.route === "string" ? route.query.route : route.params.id;
    detail.value = await routeDetail(routeId);
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  }
});

function book(tripId: number) {
  router.push(`/lg/order/new/${tripId}`);
}
</script>

<template>
  <div class="detail">
    <header class="bar">
      <button class="back" :aria-label="t('lg.common.back')" @click="router.back()">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </button>
    </header>

    <p v-if="error" class="state">{{ error }}</p>

    <template v-else-if="detail">
      <section class="lane-box">
        <div class="lane">
          <span>{{ detail.origin_town }}</span>
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
          <span>{{ detail.dest_town }}</span>
        </div>
        <p v-if="detail.via_towns.length" class="via">via {{ detail.via_towns.join(", ") }}</p>
        <p class="price">
          <template v-if="detail.negotiable">{{ t("lg.browse.negotiable") }}</template>
          <template v-else>
            <span v-if="detail.rate_per_ton">GHS {{ detail.rate_per_ton }}{{ t("lg.browse.perTon") }}</span>
            <span v-if="detail.rate_per_m3"> · GHS {{ detail.rate_per_m3 }}{{ t("lg.browse.perM3") }}</span>
          </template>
        </p>
      </section>

      <section class="veh">
        <h2>{{ detail.vehicle.vehicle_type }} · {{ detail.vehicle.brand_model }}</h2>
        <p>{{ detail.vehicle.max_load_kg }}kg · {{ detail.vehicle.max_volume_m3 }}m³</p>
      </section>

      <section class="trips">
        <div v-for="tr in detail.upcoming_trips" :key="tr.trip_id" class="trip-row">
          <div>
            <p class="d">{{ tr.depart_date }} {{ tr.depart_time }}</p>
            <p class="r">{{ t("lg.browse.remaining") }} {{ tr.remaining_load_kg }}kg · {{ tr.remaining_volume_m3 }}m³</p>
          </div>
          <button class="book" @click="book(tr.trip_id)">{{ t("lg.browse.book") }}</button>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.detail { min-height: 100vh; background: var(--surface); }
.bar { padding: 12px 14px; background: var(--bg); }
.back { border: 0; background: transparent; color: var(--text-primary); display: flex; }
.state { padding: 60px 20px; text-align: center; color: var(--text-muted); }
.lane-box { background: var(--bg); padding: 16px; margin-bottom: 8px; }
.lane { display: flex; align-items: center; gap: 8px; font-size: 19px; font-weight: 600; color: var(--brand-700); }
.via { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
.price { margin-top: 8px; font-size: 14px; font-weight: 600; color: var(--brand-500); }
.veh { background: var(--bg); padding: 14px 16px; margin-bottom: 8px; }
.veh h2 { font-size: 14px; font-weight: 500; }
.veh p { font-size: 12.5px; color: var(--text-secondary); margin-top: 2px; }
.trips { background: var(--bg); }
.trip-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border); }
.trip-row .d { font-size: 14px; font-weight: 500; }
.trip-row .r { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }
.book { border: 0; border-radius: var(--radius-pill); background: var(--brand-500); color: #fff; padding: 8px 16px; font-size: 13px; }
</style>
```

**Cross-task note for Task 5:** so the detail page can fetch by route id, change the
`TripCard.vue` link to pass the route id as a query param. In `TripCard.vue`, replace the
`:to` binding with:

```vue
    :to="`/lg/trip/${trip.trip_id}?route=${trip.route_id}`"
```

and in `TripDetailView` the `route=` query is read on mount (already handled above). The
upcoming-trip "book" buttons always carry the correct trip id.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run tests/tripDetail.spec.ts` → 2 PASS

- [ ] **Step 5: Commit**

```bash
cd .. && git add h5/src/views/TripDetailView.vue h5/src/components/TripCard.vue h5/tests/tripDetail.spec.ts
git commit -m "feat(h5): trip/route detail with booking CTA"
```

---

### Task 7: Image upload component + order form

**Files:**
- Create: `h5/src/components/ImageUpload.vue`
- Replace: `h5/src/views/OrderFormView.vue`
- Test: `h5/tests/orderForm.spec.ts`

- [ ] **Step 1: Write the failing test**

Create `h5/tests/orderForm.spec.ts`:

```typescript
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import OrderFormView from "../src/views/OrderFormView.vue";
import { freshPinia, testI18n, testRouter } from "./helpers";

vi.mock("../src/api/lg", () => ({
  submitOrder: vi.fn(() => Promise.resolve({ id: 99, status: "submitted" })),
  uploadImage: vi.fn(() => Promise.resolve({ id: "att-1", url: "/api/lg/uploads/att-1" })),
}));
import { submitOrder } from "../src/api/lg";

async function mountForm() {
  const router = testRouter();
  router.push("/lg/order/new/5");
  await router.isReady();
  const w = mount(OrderFormView, { global: { plugins: [freshPinia(), testI18n("en"), router] } });
  return { w, router };
}

function fill(w: Awaited<ReturnType<typeof mountForm>>["w"]) {
  const set = (name: string, value: string) => w.find(`[name=${name}]`).setValue(value);
  set("contact_name", "Efua");
  set("contact_phone", "0201112223");
  set("pickup_town", "Accra");
  set("delivery_town", "Kumasi");
  set("consignee_name", "Yaw");
  set("consignee_phone", "0261112223");
  set("cargo_name", "TV sets");
  set("pieces", "10");
  set("weight_kg", "200");
  set("volume_m3", "1.5");
  set("pickup_window", "tomorrow morning");
}

describe("OrderFormView", () => {
  beforeEach(() => vi.clearAllMocks());

  it("blocks submission until required fields are filled", async () => {
    const { w } = await mountForm();
    await w.find("form").trigger("submit.prevent");
    expect(submitOrder).not.toHaveBeenCalled();
    expect(w.find(".error").exists()).toBe(true);
  });

  it("submits the order with the trip id from the route", async () => {
    const { w, router } = await mountForm();
    const spy = vi.spyOn(router, "replace");
    fill(w);
    await w.find("form").trigger("submit.prevent");
    await flushPromises();
    expect(submitOrder).toHaveBeenCalledWith(expect.objectContaining({ trip_id: 5, cargo_name: "TV sets", weight_kg: 200 }));
    expect(spy).toHaveBeenCalledWith("/me/orders");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/orderForm.spec.ts`
Expected: FAIL — stub renders empty `<div />`

- [ ] **Step 3: Write the implementation**

Create `h5/src/components/ImageUpload.vue`:

```vue
<script setup lang="ts">
import { ref } from "vue";

import { uploadImage } from "../api/lg";

const props = defineProps<{ modelValue: string[]; max?: number }>();
const emit = defineEmits<{ "update:modelValue": [string[]] }>();

const busy = ref(false);
const error = ref("");

async function onPick(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  if (props.modelValue.length >= (props.max ?? 6)) return;
  busy.value = true;
  error.value = "";
  try {
    const res = await uploadImage(file);
    emit("update:modelValue", [...props.modelValue, res.id]);
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    busy.value = false;
    input.value = "";
  }
}

function removeAt(i: number) {
  emit("update:modelValue", props.modelValue.filter((_, idx) => idx !== i));
}
</script>

<template>
  <div class="uploader">
    <span v-for="(id, i) in modelValue" :key="id" class="thumb">
      <img :src="`/api/lg/uploads/${id}`" alt="" />
      <button type="button" class="rm" @click="removeAt(i)">×</button>
    </span>
    <label v-if="modelValue.length < (max ?? 6)" class="add">
      <input type="file" accept="image/*" hidden @change="onPick" />
      <span>{{ busy ? "…" : "+" }}</span>
    </label>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.uploader { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.thumb { position: relative; width: 60px; height: 60px; border-radius: 8px; overflow: hidden; }
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.rm { position: absolute; top: 0; right: 0; border: 0; background: rgba(0,0,0,.55); color: #fff; width: 18px; height: 18px; line-height: 16px; }
.add { width: 60px; height: 60px; border: 1px dashed var(--border); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 24px; color: var(--text-muted); }
.error { color: #c0392b; font-size: 12px; width: 100%; }
</style>
```

Replace `h5/src/views/OrderFormView.vue`:

```vue
<script setup lang="ts">
import { reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { submitOrder } from "../api/lg";
import type { OrderDraft } from "../api/lgTypes";
import ImageUpload from "../components/ImageUpload.vue";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const tripId = Number(route.params.tripId);
const packagingOptions = ["carton", "pallet", "bag", "drum", "loose", "other"];

const draft = reactive<OrderDraft>({
  trip_id: tripId,
  contact_name: "",
  contact_phone: "",
  pickup_region: "",
  pickup_town: "",
  pickup_details: "",
  delivery_region: "",
  delivery_town: "",
  delivery_details: "",
  consignee_name: "",
  consignee_phone: "",
  cargo_name: "",
  cargo_category: "general",
  packaging: "carton",
  pieces: 0,
  weight_kg: 0,
  volume_m3: 0,
  fragile: false,
  needs_loading: false,
  needs_pickup: false,
  pickup_window: "",
  remarks: "",
  photo_ids: [],
});

const error = ref("");
const busy = ref(false);

const REQUIRED: (keyof OrderDraft)[] = [
  "contact_name", "contact_phone", "pickup_town", "delivery_town",
  "consignee_name", "consignee_phone", "cargo_name", "pickup_window",
];

function valid(): boolean {
  for (const f of REQUIRED) {
    if (!String(draft[f]).trim()) return false;
  }
  return draft.pieces > 0 && draft.weight_kg > 0 && draft.volume_m3 > 0;
}

async function submit() {
  error.value = "";
  if (!valid()) {
    error.value = t("lg.common.required");
    return;
  }
  busy.value = true;
  try {
    await submitOrder({ ...draft });
    router.replace("/me/orders");
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    error.value = /capacity/i.test(msg) ? t("lg.order.overCapacity") : msg;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="form-page">
    <header class="bar">
      <button class="back" :aria-label="t('lg.common.back')" @click="router.back()">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6" /></svg>
      </button>
      <h1>{{ t("lg.order.title") }}</h1>
    </header>

    <form @submit.prevent="submit">
      <fieldset>
        <legend>{{ t("lg.order.contact") }}</legend>
        <input name="contact_name" v-model="draft.contact_name" :placeholder="t('lg.order.contactName')" />
        <input name="contact_phone" v-model="draft.contact_phone" type="tel" :placeholder="t('lg.order.contactPhone')" />
      </fieldset>

      <fieldset>
        <legend>{{ t("lg.order.pickup") }}</legend>
        <input name="pickup_region" v-model="draft.pickup_region" :placeholder="t('lg.order.region')" />
        <input name="pickup_town" v-model="draft.pickup_town" :placeholder="t('lg.order.town')" />
        <input name="pickup_details" v-model="draft.pickup_details" :placeholder="t('lg.order.addressDetails')" />
      </fieldset>

      <fieldset>
        <legend>{{ t("lg.order.delivery") }}</legend>
        <input name="delivery_region" v-model="draft.delivery_region" :placeholder="t('lg.order.region')" />
        <input name="delivery_town" v-model="draft.delivery_town" :placeholder="t('lg.order.town')" />
        <input name="delivery_details" v-model="draft.delivery_details" :placeholder="t('lg.order.addressDetails')" />
        <input name="consignee_name" v-model="draft.consignee_name" :placeholder="t('lg.order.consigneeName')" />
        <input name="consignee_phone" v-model="draft.consignee_phone" type="tel" :placeholder="t('lg.order.consigneePhone')" />
      </fieldset>

      <fieldset>
        <legend>{{ t("lg.order.cargo") }}</legend>
        <input name="cargo_name" v-model="draft.cargo_name" :placeholder="t('lg.order.cargoName')" />
        <input name="cargo_category" v-model="draft.cargo_category" :placeholder="t('lg.order.category')" />
        <select v-model="draft.packaging" :aria-label="t('lg.order.packaging')">
          <option v-for="p in packagingOptions" :key="p" :value="p">{{ t(`lg.order.packagingOptions.${p}`) }}</option>
        </select>
        <div class="triple">
          <input name="pieces" v-model.number="draft.pieces" type="number" min="1" :placeholder="t('lg.order.pieces')" />
          <input name="weight_kg" v-model.number="draft.weight_kg" type="number" min="0" step="0.1" :placeholder="t('lg.order.weight')" />
          <input name="volume_m3" v-model.number="draft.volume_m3" type="number" min="0" step="0.1" :placeholder="t('lg.order.volume')" />
        </div>
        <label class="chk"><input type="checkbox" v-model="draft.fragile" /> {{ t("lg.order.fragile") }}</label>
        <label class="chk"><input type="checkbox" v-model="draft.needs_loading" /> {{ t("lg.order.needsLoading") }}</label>
        <label class="chk"><input type="checkbox" v-model="draft.needs_pickup" /> {{ t("lg.order.needsPickup") }}</label>
        <input name="pickup_window" v-model="draft.pickup_window" :placeholder="t('lg.order.pickupWindow')" />
        <input name="remarks" v-model="draft.remarks" :placeholder="t('lg.order.remarks')" />
        <p class="lbl">{{ t("lg.order.photos") }}</p>
        <ImageUpload v-model="draft.photo_ids" />
      </fieldset>

      <p class="note">{{ t("lg.order.priceNote") }}</p>
      <p class="note disc">{{ t("lg.order.disclaimer") }}</p>
      <p v-if="error" class="error">{{ error }}</p>

      <button class="submit" type="submit" :disabled="busy">
        {{ busy ? t("lg.order.submitting") : t("lg.order.submit") }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.form-page { min-height: 100vh; background: var(--surface); }
.bar { display: flex; align-items: center; gap: 8px; padding: 12px 14px; background: var(--bg); border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10; }
.bar h1 { font-size: 16px; font-weight: 500; }
.back { border: 0; background: transparent; color: var(--text-primary); display: flex; }
form { padding: 12px; display: flex; flex-direction: column; gap: 12px; }
fieldset { border: 0; background: var(--bg); border-radius: var(--radius-card); padding: 12px; display: flex; flex-direction: column; gap: 8px; }
legend { font-size: 13px; font-weight: 600; color: var(--brand-700); padding: 0 0 6px; }
input, select { border: 1px solid var(--border); border-radius: 8px; padding: 9px 11px; font-size: 14px; background: var(--surface); outline: none; }
.triple { display: flex; gap: 8px; }
.triple input { flex: 1; min-width: 0; }
.chk { display: flex; align-items: center; gap: 8px; font-size: 13.5px; color: var(--text-secondary); }
.lbl { font-size: 12.5px; color: var(--text-secondary); }
.note { font-size: 12px; color: var(--text-muted); padding: 0 4px; }
.disc { font-style: italic; }
.error { color: #c0392b; font-size: 13px; padding: 0 4px; }
.submit { border: 0; border-radius: var(--radius-pill); background: var(--brand-500); color: #fff; padding: 12px; font-size: 15px; font-weight: 500; }
.submit:disabled { opacity: 0.5; }
</style>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run tests/orderForm.spec.ts` → 2 PASS

- [ ] **Step 5: Commit**

```bash
cd .. && git add h5/src/components/ImageUpload.vue h5/src/views/OrderFormView.vue h5/tests/orderForm.spec.ts
git commit -m "feat(h5): image upload component and shipper order form"
```

---

### Task 8: My orders list + order status tag

**Files:**
- Create: `h5/src/components/OrderStatusTag.vue`
- Replace: `h5/src/views/MyOrdersView.vue`
- Test: `h5/tests/myOrders.spec.ts`

- [ ] **Step 1: Write the failing test**

Create `h5/tests/myOrders.spec.ts`:

```typescript
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import MyOrdersView from "../src/views/MyOrdersView.vue";
import type { OrderList } from "../src/api/lgTypes";
import { freshPinia, testI18n, testRouter } from "./helpers";

const list: OrderList = {
  items: [
    {
      id: 1, status: "price_confirmed", trip_id: 5, depart_date: "2026-07-14", depart_time: "08:00",
      origin_town: "Accra", dest_town: "Kumasi", cargo_name: "TV sets", cargo_category: "electronics",
      packaging: "carton", pieces: 10, weight_kg: 200, volume_m3: 1.5, fragile: true, needs_loading: true,
      needs_pickup: false, pickup_window: "morning", remarks: "", photo_ids: [], freight_ghs: 500,
      commission_ghs: 40, pickup_time: "Sat 08:00", cancel_reason: "", created_at: "2026-07-11T09:00:00",
      pickup_town: "Accra", delivery_town: "Kumasi", driver: null, shipper: null,
    },
  ],
  total: 1, page: 1, page_size: 20,
};

vi.mock("../src/api/lg", () => ({ myOrders: vi.fn(() => Promise.resolve(list)) }));

async function mountList() {
  const router = testRouter();
  router.push("/me/orders");
  await router.isReady();
  const w = mount(MyOrdersView, { global: { plugins: [freshPinia(), testI18n("en"), router] } });
  await flushPromises();
  return { w };
}

describe("MyOrdersView", () => {
  it("lists the shipper's orders with a status tag", async () => {
    const { w } = await mountList();
    expect(w.text()).toContain("TV sets");
    expect(w.text()).toContain("Accra");
    expect(w.find(".status").text()).toContain("Price confirmed");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/myOrders.spec.ts`
Expected: FAIL — stub renders empty `<div />`

- [ ] **Step 3: Write the implementation**

Create `h5/src/components/OrderStatusTag.vue`:

```vue
<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps<{ status: string }>();
const { t } = useI18n();

const tone = computed(() => {
  if (["completed"].includes(props.status)) return "done";
  if (["cancelled", "exception_closed"].includes(props.status)) return "closed";
  if (["submitted"].includes(props.status)) return "new";
  return "active";
});
</script>

<template>
  <span class="status" :class="tone">{{ t(`lg.orders.status.${status}`) }}</span>
</template>

<style scoped>
.status { font-size: 11px; padding: 3px 8px; border-radius: var(--radius-pill); font-weight: 500; }
.new { background: var(--brand-50); color: var(--brand-700); }
.active { background: #fef3e0; color: #b26a00; }
.done { background: #e3f4ec; color: #1d7a52; }
.closed { background: #f0efec; color: var(--text-muted); }
</style>
```

Replace `h5/src/views/MyOrdersView.vue`:

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { myOrders } from "../api/lg";
import type { OrderView } from "../api/lgTypes";
import OrderStatusTag from "../components/OrderStatusTag.vue";

const { t } = useI18n();
const router = useRouter();

const orders = ref<OrderView[]>([]);
const loaded = ref(false);

onMounted(async () => {
  try {
    orders.value = (await myOrders(1)).items;
  } finally {
    loaded.value = true;
  }
});
</script>

<template>
  <div class="page">
    <header class="bar">
      <button class="back" :aria-label="t('lg.common.back')" @click="router.push('/me')">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6" /></svg>
      </button>
      <h1>{{ t("lg.orders.mineTitle") }}</h1>
    </header>

    <p v-if="loaded && !orders.length" class="empty">{{ t("lg.orders.empty") }}</p>

    <RouterLink v-for="o in orders" :key="o.id" class="row" :to="`/me/orders/${o.id}`">
      <div class="top">
        <span class="lane">{{ o.origin_town }} → {{ o.dest_town }}</span>
        <OrderStatusTag :status="o.status" />
      </div>
      <p class="cargo">{{ o.cargo_name }} · {{ o.weight_kg }}kg · {{ o.volume_m3 }}m³</p>
      <p class="when">{{ o.depart_date }} {{ o.depart_time }}</p>
    </RouterLink>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; background: var(--surface); }
.bar { display: flex; align-items: center; gap: 8px; padding: 12px 14px; background: var(--bg); border-bottom: 1px solid var(--border); }
.bar h1 { font-size: 16px; font-weight: 500; }
.back { border: 0; background: transparent; color: var(--text-primary); display: flex; }
.empty { text-align: center; color: var(--text-muted); padding: 60px 0; font-size: 13px; }
.row { display: block; background: var(--bg); padding: 12px 16px; border-bottom: 1px solid var(--border); text-decoration: none; color: var(--text-primary); }
.top { display: flex; justify-content: space-between; align-items: center; }
.lane { font-size: 15px; font-weight: 600; color: var(--brand-700); }
.cargo { font-size: 12.5px; color: var(--text-secondary); margin-top: 4px; }
.when { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
</style>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run tests/myOrders.spec.ts` → 1 PASS

- [ ] **Step 5: Commit**

```bash
cd .. && git add h5/src/components/OrderStatusTag.vue h5/src/views/MyOrdersView.vue h5/tests/myOrders.spec.ts
git commit -m "feat(h5): my-orders list and status tag"
```

---

### Task 9: Order detail with contact disclosure + cancel

**Files:**
- Replace: `h5/src/views/OrderDetailView.vue`
- Test: `h5/tests/orderDetail.spec.ts`

- [ ] **Step 1: Write the failing test**

Create `h5/tests/orderDetail.spec.ts`:

```typescript
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import OrderDetailView from "../src/views/OrderDetailView.vue";
import type { OrderView } from "../src/api/lgTypes";
import { freshPinia, testI18n, testRouter } from "./helpers";

function order(over: Partial<OrderView>): OrderView {
  return {
    id: 1, status: "submitted", trip_id: 5, depart_date: "2026-07-14", depart_time: "08:00",
    origin_town: "Accra", dest_town: "Kumasi", cargo_name: "TV sets", cargo_category: "electronics",
    packaging: "carton", pieces: 10, weight_kg: 200, volume_m3: 1.5, fragile: true, needs_loading: true,
    needs_pickup: false, pickup_window: "morning", remarks: "", photo_ids: [], freight_ghs: null,
    commission_ghs: null, pickup_time: "", cancel_reason: "", created_at: "2026-07-11T09:00:00",
    pickup_town: "Accra", delivery_town: "Kumasi", driver: null, shipper: null, ...over,
  };
}

const mocks = vi.hoisted(() => ({ orderDetail: vi.fn(), cancelOrder: vi.fn() }));
vi.mock("../src/api/lg", () => mocks);

async function mountDetail() {
  const router = testRouter();
  router.push("/me/orders/1");
  await router.isReady();
  const w = mount(OrderDetailView, { global: { plugins: [freshPinia(), testI18n("en"), router] } });
  await flushPromises();
  return { w };
}

describe("OrderDetailView", () => {
  beforeEach(() => vi.clearAllMocks());

  it("hides driver contact before acceptance", async () => {
    mocks.orderDetail.mockResolvedValueOnce(order({ status: "submitted", driver: null }));
    const { w } = await mountDetail();
    expect(w.text()).toContain("appears once the driver accepts");
    expect(w.find(".cancel").exists()).toBe(true); // cancellable while submitted
  });

  it("shows driver contact once disclosed and hides cancel", async () => {
    mocks.orderDetail.mockResolvedValueOnce(
      order({ status: "in_transit", driver: { full_name: "Kwame", plate_number: "GR 1234-24", phone: "+233241234567" } }),
    );
    const { w } = await mountDetail();
    expect(w.text()).toContain("GR 1234-24");
    expect(w.text()).toContain("+233241234567");
    expect(w.find(".cancel").exists()).toBe(false);
  });

  it("cancels a submitted order", async () => {
    mocks.orderDetail.mockResolvedValueOnce(order({ status: "submitted" }));
    mocks.cancelOrder.mockResolvedValueOnce(order({ status: "cancelled" }));
    const { w } = await mountDetail();
    await w.find(".cancel").trigger("click");
    await w.find(".confirm-cancel").trigger("click");
    await flushPromises();
    expect(mocks.cancelOrder).toHaveBeenCalledWith(1, expect.any(String));
    expect(w.find(".status").text()).toContain("Cancelled");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/orderDetail.spec.ts`
Expected: FAIL — stub renders empty `<div />`

- [ ] **Step 3: Write the implementation**

Replace `h5/src/views/OrderDetailView.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { cancelOrder, orderDetail } from "../api/lg";
import type { OrderView } from "../api/lgTypes";
import OrderStatusTag from "../components/OrderStatusTag.vue";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const order = ref<OrderView | null>(null);
const error = ref("");
const showCancel = ref(false);
const reason = ref("");
const busy = ref(false);

const cancellable = computed(
  () => order.value != null && ["submitted", "price_confirmed"].includes(order.value.status),
);

onMounted(async () => {
  try {
    order.value = await orderDetail(String(route.params.id));
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  }
});

async function confirmCancel() {
  if (!order.value || busy.value) return;
  busy.value = true;
  try {
    order.value = await cancelOrder(order.value.id, reason.value.trim() || "cancelled by shipper");
    showCancel.value = false;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="page">
    <header class="bar">
      <button class="back" :aria-label="t('lg.common.back')" @click="router.push('/me/orders')">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6" /></svg>
      </button>
      <h1>{{ t("lg.orders.detailTitle") }}</h1>
    </header>

    <p v-if="error" class="state">{{ error }}</p>

    <template v-else-if="order">
      <section class="head">
        <div class="lane">{{ order.origin_town }} → {{ order.dest_town }}</div>
        <OrderStatusTag :status="order.status" />
      </section>

      <section class="block">
        <h2>{{ t("lg.orders.cargo") }}</h2>
        <p>{{ order.cargo_name }} · {{ order.pieces }} · {{ order.weight_kg }}kg · {{ order.volume_m3 }}m³</p>
        <p class="sub">{{ order.pickup_town }} → {{ order.delivery_town }}</p>
      </section>

      <section class="block">
        <h2>{{ t("lg.orders.trip") }}</h2>
        <p>{{ order.depart_date }} {{ order.depart_time }}</p>
        <p v-if="order.freight_ghs != null" class="sub">{{ t("lg.orders.freight") }}: GHS {{ order.freight_ghs }}</p>
        <p v-if="order.pickup_time" class="sub">{{ t("lg.orders.pickupTime") }}: {{ order.pickup_time }}</p>
      </section>

      <section class="block">
        <h2>{{ t("lg.orders.driver") }}</h2>
        <template v-if="order.driver">
          <p>{{ order.driver.full_name }}</p>
          <p class="sub">{{ t("lg.orders.plate") }}: {{ order.driver.plate_number }}</p>
          <p class="sub">{{ t("lg.orders.phone") }}: <a :href="`tel:${order.driver.phone}`">{{ order.driver.phone }}</a></p>
        </template>
        <p v-else class="hint">{{ t("lg.orders.contactHidden") }}</p>
      </section>

      <button v-if="cancellable" class="cancel" @click="showCancel = true">{{ t("lg.orders.cancel") }}</button>

      <div v-if="showCancel" class="sheet">
        <p>{{ t("lg.orders.cancelConfirm") }}</p>
        <input v-model="reason" :placeholder="t('lg.orders.cancelReason')" />
        <div class="sheet-actions">
          <button class="ghost" @click="showCancel = false">{{ t("lg.common.back") }}</button>
          <button class="confirm-cancel" :disabled="busy" @click="confirmCancel">{{ t("lg.orders.cancel") }}</button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; background: var(--surface); }
.bar { display: flex; align-items: center; gap: 8px; padding: 12px 14px; background: var(--bg); border-bottom: 1px solid var(--border); }
.bar h1 { font-size: 16px; font-weight: 500; }
.back { border: 0; background: transparent; color: var(--text-primary); display: flex; }
.state { padding: 60px 20px; text-align: center; color: var(--text-muted); }
.head { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; background: var(--bg); margin-bottom: 8px; }
.lane { font-size: 17px; font-weight: 600; color: var(--brand-700); }
.block { background: var(--bg); padding: 12px 16px; margin-bottom: 8px; }
.block h2 { font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted); margin-bottom: 6px; }
.block p { font-size: 14px; }
.sub { font-size: 12.5px; color: var(--text-secondary); margin-top: 2px; }
.hint { font-size: 12.5px; color: var(--text-muted); font-style: italic; }
.cancel { display: block; width: calc(100% - 24px); margin: 16px 12px; border: 1px solid #d9534f; color: #c0392b; background: var(--bg); border-radius: var(--radius-pill); padding: 11px; font-size: 14px; }
.sheet { position: fixed; left: 0; right: 0; bottom: 0; background: var(--bg); border-top: 1px solid var(--border); padding: 16px; }
.sheet input { width: 100%; border: 1px solid var(--border); border-radius: 8px; padding: 10px; margin: 10px 0; font-size: 14px; }
.sheet-actions { display: flex; gap: 10px; }
.ghost { flex: 1; border: 1px solid var(--border); background: var(--bg); border-radius: var(--radius-pill); padding: 10px; }
.confirm-cancel { flex: 1; border: 0; background: #c0392b; color: #fff; border-radius: var(--radius-pill); padding: 10px; }
</style>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run tests/orderDetail.spec.ts` → 3 PASS

- [ ] **Step 5: Commit**

```bash
cd .. && git add h5/src/views/OrderDetailView.vue h5/tests/orderDetail.spec.ts
git commit -m "feat(h5): order detail with contact disclosure and cancel"
```

---

### Task 10: Notification center, unread badge, and full verification

**Files:**
- Replace: `h5/src/views/NotificationsView.vue`
- Modify: `h5/src/views/MeView.vue` (unread badge)
- Test: `h5/tests/notifications.spec.ts`

- [ ] **Step 1: Write the failing test**

Create `h5/tests/notifications.spec.ts`:

```typescript
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import NotificationsView from "../src/views/NotificationsView.vue";
import type { NotificationList } from "../src/api/lgTypes";
import { freshPinia, testI18n, testRouter } from "./helpers";

const list: NotificationList = {
  items: [
    { id: 2, kind: "order", title: "Driver accepted your order", body: "Pickup Sat", read: false, created_at: "2026-07-11T10:00:00" },
    { id: 1, kind: "order", title: "Order submitted", body: "", read: true, created_at: "2026-07-11T09:00:00" },
  ],
  total: 2, unread: 1, page: 1, page_size: 20,
};

const mocks = vi.hoisted(() => ({ listNotifications: vi.fn(), markNotificationRead: vi.fn() }));
vi.mock("../src/api/lg", () => mocks);

async function mountNotifs() {
  const router = testRouter();
  router.push("/me/notifications");
  await router.isReady();
  const w = mount(NotificationsView, { global: { plugins: [freshPinia(), testI18n("en"), router] } });
  await flushPromises();
  return { w };
}

describe("NotificationsView", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists notifications, newest first, marking unread ones", async () => {
    mocks.listNotifications.mockResolvedValueOnce(list);
    const { w } = await mountNotifs();
    const rows = w.findAll(".notif");
    expect(rows).toHaveLength(2);
    expect(rows[0].text()).toContain("Driver accepted your order");
    expect(rows[0].classes()).toContain("unread");
  });

  it("marks a notification read on tap", async () => {
    mocks.listNotifications.mockResolvedValueOnce(list);
    mocks.markNotificationRead.mockResolvedValueOnce(undefined);
    const { w } = await mountNotifs();
    await w.findAll(".notif")[0].trigger("click");
    await flushPromises();
    expect(mocks.markNotificationRead).toHaveBeenCalledWith(2);
    expect(w.findAll(".notif")[0].classes()).not.toContain("unread");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/notifications.spec.ts`
Expected: FAIL — stub renders empty `<div />`

- [ ] **Step 3: Write the implementation**

Replace `h5/src/views/NotificationsView.vue`:

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { listNotifications, markNotificationRead } from "../api/lg";
import type { NotificationItem } from "../api/lgTypes";

const { t } = useI18n();
const router = useRouter();

const items = ref<NotificationItem[]>([]);
const loaded = ref(false);

onMounted(async () => {
  try {
    items.value = (await listNotifications(1)).items;
  } finally {
    loaded.value = true;
  }
});

async function open(n: NotificationItem) {
  if (n.read) return;
  await markNotificationRead(n.id);
  n.read = true;
}
</script>

<template>
  <div class="page">
    <header class="bar">
      <button class="back" :aria-label="t('lg.common.back')" @click="router.push('/me')">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6" /></svg>
      </button>
      <h1>{{ t("lg.notif.title") }}</h1>
    </header>

    <p v-if="loaded && !items.length" class="empty">{{ t("lg.notif.empty") }}</p>

    <button v-for="n in items" :key="n.id" class="notif" :class="{ unread: !n.read }" @click="open(n)">
      <span v-if="!n.read" class="dot" />
      <span class="body">
        <span class="title">{{ n.title }}</span>
        <span v-if="n.body" class="text">{{ n.body }}</span>
        <span class="time">{{ n.created_at.slice(0, 16).replace("T", " ") }}</span>
      </span>
    </button>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; background: var(--surface); }
.bar { display: flex; align-items: center; gap: 8px; padding: 12px 14px; background: var(--bg); border-bottom: 1px solid var(--border); }
.bar h1 { font-size: 16px; font-weight: 500; }
.back { border: 0; background: transparent; color: var(--text-primary); display: flex; }
.empty { text-align: center; color: var(--text-muted); padding: 60px 0; font-size: 13px; }
.notif { display: flex; gap: 10px; width: 100%; text-align: left; background: var(--bg); border: 0; border-bottom: 1px solid var(--border); padding: 14px 16px; }
.notif.unread { background: var(--brand-50); }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--brand-500); margin-top: 6px; flex: none; }
.body { display: flex; flex-direction: column; gap: 3px; }
.title { font-size: 14px; font-weight: 500; color: var(--text-primary); }
.text { font-size: 12.5px; color: var(--text-secondary); }
.time { font-size: 11px; color: var(--text-muted); }
</style>
```

Modify `h5/src/views/MeView.vue` to show an unread badge on the Notifications row.
Add to the `<script setup>` block:

```typescript
import { onMounted, ref } from "vue";

import { listNotifications } from "../api/lg";

const unread = ref(0);
onMounted(async () => {
  if (auth.loggedIn) {
    try {
      unread.value = (await listNotifications(1)).unread;
    } catch {
      unread.value = 0;
    }
  }
});
```

Replace the Notifications `RouterLink` row with a badge-carrying version:

```vue
      <RouterLink class="row" to="/me/notifications">
        {{ t("lg.me.notifications") }}
        <span v-if="unread" class="badge">{{ unread }}</span>
      </RouterLink>
```

Add to `MeView.vue` styles:

```css
.row { position: relative; }
.badge { position: absolute; right: 16px; top: 50%; transform: translateY(-50%); background: var(--brand-500); color: #fff; font-size: 11px; min-width: 18px; height: 18px; border-radius: 9px; display: inline-flex; align-items: center; justify-content: center; padding: 0 5px; }
```

- [ ] **Step 4: Run the full frontend suite + typecheck + build**

Run: `npx vitest run` → **all specs PASS** (existing + new)
Run: `npx vue-tsc --noEmit` → exit 0
Run: `npm run build` → succeeds (vue-tsc + vite build)

- [ ] **Step 5: Live smoke test in the preview browser**

Start backend (from `backend/`, seeded SQLite) and the H5 dev server, then verify the new
surface renders and the auth flow works end to end:

```bash
# backend
cd backend && rm -f verify.db && DATABASE_URL="sqlite:///./verify.db" uv run python -m app.seed
DATABASE_URL="sqlite:///./verify.db" SCHEDULER_ENABLED=false uv run uvicorn app.main:app --port 8000 &
```

Then use the preview tools (per the harness verification workflow):
1. `preview_start { name: "h5" }` → open the dev server tab.
2. `navigate` to `/lg` → confirm the Logistics tab, filters, and (empty) list render; check
   `read_console_messages` is clean.
3. `navigate` to `/me` → tap **Sign in**; enter a Ghana number, tap **Send code**; read the
   OTP from the SMS log (`sqlite3 verify.db "SELECT code FROM lg_otp_code ORDER BY id DESC LIMIT 1"`),
   enter it, verify → lands back on `/me` showing the phone and account menu.
4. Screenshot the three tabs (News, Logistics, Me) as proof; confirm the bottom TabBar
   highlights the active tab.
5. Stop the dev server and backend.

(There will be no trips to browse until a driver publishes a route in Plan 4; an empty list
with working filters and a working login flow is the expected Plan 3 result.)

- [ ] **Step 6: Commit**

```bash
cd .. && git add h5/src/views/NotificationsView.vue h5/src/views/MeView.vue h5/tests/notifications.spec.ts
git commit -m "feat(h5): notification center and unread badge"
```

---

## What this plan deliberately defers

| Deferred item | Where it lands |
| --- | --- |
| Driver center: certification, vehicles, routes, trips, assigned orders, commission ledger UI | LTL Plan 4 |
| Driver-specific menu entries + `isDriver` state on the auth store and Me hub | LTL Plan 4 |
| All admin SPA pages (review queues, order workspace, dashboard) | LTL Plan 5 |
| docker-compose upload volume, nginx wiring, MySQL `role` migration | LTL Plan 6 (deployment) |

## Notes for the executor

- **Trip-detail routing:** browse cards link with `?route=<route_id>` so the detail view can
  call `GET /api/lg/routes/{id}` (keyed by route, not trip). The "book" buttons always use the
  concrete trip id. Keep this contract when touching `TripCard.vue` / `TripDetailView.vue`.
- **van-list flag vs guard:** `lgFeed` intentionally keeps `loading` (van-list v-model) separate
  from `inFlight` (dedupe) — this is the exact fix from the earlier pull-to-refresh bug. Don't
  collapse them.
- **Anonymous news untouched:** the News tab, feed store, and article pages are unchanged apart
  from adding `<TabBar />`. Don't route news through the auth guard.
```
