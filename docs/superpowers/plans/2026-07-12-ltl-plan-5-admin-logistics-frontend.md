# LTL Plan 5: Admin Logistics Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a role-gated 物流 (Logistics) section to the existing ZokoDaily admin SPA — dashboard, driver/vehicle/route review queues, CS order workspace, commission ledger, config, staff, and blacklist — consuming the Plan 1–2 `/api/admin/lg/*` API, plus one small backend change so the UI knows the staff role.

**Architecture:** Extends the existing admin SPA (Vue 3 + `<script setup>` + TS + Pinia + vue-router + **Element Plus**, Chinese UI, served under `/admin/`). The shared `api` axios instance (`/api/admin` base, bearer, `handleApiError` interceptor) gains logistics endpoint functions; the auth store gains `role` (fetched from an extended `/auth/me`); the sidebar shows a role-filtered 物流 submenu; new views live under `admin/src/views/lg/`. Document images are shown via an `AuthImage` component that fetches the auth-gated attachment as a blob with the admin bearer.

**Tech Stack:** unchanged — Vue 3.4, Element Plus 2.7, `@element-plus/icons-vue`, Pinia 2, vue-router 4, axios, Vite 5, vue-tsc. Backend: FastAPI, pytest (one task).

**Testing note (per spec §9):** the admin SPA has no unit-test suite and this plan does not add one (Element-Plus component testing is disproportionate here). Verification is: **pytest TDD for the single backend change (Task 1)**; **`vue-tsc --noEmit` as the per-task gate for every frontend task**; and a **live headless Playwright admin-journey smoke run (Task 14)**. Each frontend task's "verify" step is the typecheck; behavior is proven in Task 14.

**Plan sequence:** LTL Plans 1–4 (done) → **LTL Plan 5 (this)** → LTL Plan 6 (deployment).

**Working directory:** frontend commands run from `admin/`; the Task 1 backend command runs from `backend/`.
**Spec:** `docs/superpowers/specs/2026-07-12-ltl-plan-5-admin-frontend-design.md`.

**Existing conventions to follow (verified in the codebase):**
- `admin/src/api/client.ts`: `api` axios instance, `TOKEN_KEY = "zoko-admin-token"`, `USER_KEY`, a response interceptor `handleApiError` that maps 401→re-login, 409/422→`ElMessage.warning(detail)`, else generic error. **Logistics screens rely on this — do not add their own error toasts for those cases.**
- `admin/src/api/endpoints.ts`: thin typed functions over `api`; `login()` uses a bare `axios.post` (no bearer needed).
- Views use Element Plus (`el-table`, `el-tag`, `el-dialog`, `el-form`, `el-pagination`, `el-card`, `el-select`, `el-button`), `ElMessage`/`ElMessageBox`, Chinese labels. Config screens follow `SettingsView.vue`.
- Router: nested under `AdminLayout`, base `/admin/`, guard in `router.beforeEach`.

**Backend admin logistics endpoints consumed (all built in Plans 1–2):**
`/api/admin/lg/stats/overview` · `/drivers` (+`/{id}`,`/{id}/review`,`/{id}/freeze`,`/{id}/unfreeze`) · `/vehicles` (+`/{id}/review`) · `/routes` (+`/{id}/review`,`/{id}/suspend`,`/{id}/resume`) · `/orders` (+`/{id}`,`/{id}/confirm-price`,`/{id}/reassign`,`/{id}/cancel`,`/{id}/exception-close`,`/{id}/complete`,`/{id}/remarks`) · `/commissions` (+`/{id}/settle`,`/{id}/waive`) · `/config` · `/staff` · `/blacklist` (+`DELETE /{id}`).

---

## File structure created by this plan

```
backend/app/api/admin/auth.py     # MODIFIED: /me returns role
backend/tests/test_auth.py        # MODIFIED: assert role in /me

admin/src/
├── api/
│   ├── types.ts                  # MODIFIED: + logistics types + status option consts
│   └── endpoints.ts              # MODIFIED: + me() + all lg* functions
├── stores/auth.ts                # MODIFIED: + role, login() fetches it
├── router.ts                     # MODIFIED: + /lg/* routes + role guard
├── layout/AdminLayout.vue        # MODIFIED: + role-filtered 物流 submenu
├── components/
│   ├── AuthImage.vue             # blob-fetch an auth-gated attachment
│   └── ReviewDialog.vue          # shared approve/reject dialog
└── views/lg/
    ├── LgDashboardView.vue
    ├── LgDriversView.vue
    ├── LgVehiclesView.vue
    ├── LgRoutesView.vue
    ├── LgOrdersView.vue
    ├── LgCommissionsView.vue
    ├── LgConfigView.vue
    ├── LgStaffView.vue
    └── LgBlacklistView.vue
```

---

### Task 1: Backend — `/api/admin/auth/me` returns the staff role

**Files:**
- Modify: `backend/app/api/admin/auth.py`, `backend/tests/test_auth.py`

- [ ] **Step 1: Update the failing test**

In `backend/tests/test_auth.py`, replace the final assertion of `test_me_requires_token`:

```python
    token = _login(client).json()["access_token"]
    r = client.get("/api/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"username": "admin", "role": "admin"}
```

Add a new test after it:

```python
def test_me_returns_non_admin_role(client, db_session):
    db_session.add(
        AdminUser(username="susan", password_hash=hash_password("secret123"), role="cs")
    )
    db_session.commit()
    token = _login(client, username="susan").json()["access_token"]
    r = client.get("/api/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"username": "susan", "role": "cs"}
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `uv run pytest tests/test_auth.py -v`
Expected: FAIL — `me` returns `{"username": "admin"}` without `role`.

- [ ] **Step 3: Implement**

Replace the `me` endpoint in `backend/app/api/admin/auth.py`:

```python
@router.get("/me")
def me(username: str = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = db.query(AdminUser).filter_by(username=username).one_or_none()
    return {"username": username, "role": user.role if user else "admin"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_auth.py -v` → PASS
Run: `uv run pytest` → full backend suite PASS (177+2 assertions unaffected)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/admin/auth.py backend/tests/test_auth.py
git commit -m "feat(admin-api): /auth/me returns staff role"
```

---

### Task 2: Frontend logistics types

**Files:**
- Modify: `admin/src/api/types.ts`

- [ ] **Step 1: Append the logistics types + status option constants**

Add to the end of `admin/src/api/types.ts`:

```typescript
export interface LgDriver {
  id: number;
  user_id: number;
  phone: string;
  full_name: string;
  gender: string;
  date_of_birth: string;
  ghana_card_number: string;
  ghana_card_front_id: string;
  ghana_card_back_id: string;
  licence_number: string;
  licence_class: string;
  licence_expiry: string;
  licence_photo_id: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  status: string;
  availability: string;
  review_remark: string;
}

export interface LgVehicle {
  id: number;
  driver_id: number;
  plate_number: string;
  brand_model: string;
  vehicle_type: string;
  year: number;
  vin: string;
  cargo_length_m: number;
  cargo_width_m: number;
  cargo_height_m: number;
  max_load_kg: number;
  max_volume_m3: number;
  photo_front_id: string;
  photo_left_id: string;
  photo_right_id: string;
  photo_rear_id: string;
  photo_interior_id: string;
  reg_cert_id: string;
  roadworthy_cert_id: string;
  roadworthy_expiry: string;
  insurance_cert_id: string;
  insurance_expiry: string;
  status: string;
  review_remark: string;
}

export interface LgRoute {
  id: number;
  driver_id: number;
  origin_region: string;
  origin_town: string;
  dest_region: string;
  dest_town: string;
  via_towns: string[];
  frequency: string;
  weekdays: number[];
  once_date: string | null;
  depart_time: string;
  est_duration_hours: number;
  default_vehicle_id: number;
  cargo_types: string[];
  prohibited_notes: string;
  rate_per_ton: number | null;
  rate_per_m3: number | null;
  min_charge: number | null;
  negotiable: boolean;
  status: string;
  review_remark: string;
}

export interface LgOrderParty {
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

export interface LgOrder {
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
  photo_ids: string[];
  freight_ghs: number | null;
  commission_ghs: number | null;
  pickup_time: string;
  cancel_reason: string;
  created_at: string;
  pickup_town: string;
  delivery_town: string;
  driver: LgOrderParty | null;
  shipper: LgOrderParty | null;
}

export interface CsRemark {
  author: string;
  body: string;
  created_at: string;
}

// Detail endpoint returns the list fields plus the CS remark list and reject_count.
// (LgOrder omits the cargo `remarks` string, so there is no field-type clash.)
export interface LgOrderDetail extends LgOrder {
  remarks: CsRemark[];
  reject_count: number;
}

export interface LgCommission {
  id: number;
  order_id: number;
  driver_id: number;
  freight_ghs: number;
  rate: number;
  amount_ghs: number;
  status: string;
  method: string;
  reference: string;
  note: string;
  settled_by: string;
}

export interface StatsOverview {
  drivers: Record<string, number>;
  vehicles: number;
  routes_active: number;
  trips_upcoming: number;
  orders: Record<string, number>;
  orders_total: number;
  gmv_ghs: number;
  commission: { pending_ghs: number; settled_ghs: number };
  top_lanes: { lane: string; orders: number }[];
  completion_rate: number;
  cancellation_rate: number;
  capacity_utilization: number;
}

export interface Staff {
  id: number;
  username: string;
  role: string;
}

export interface BlacklistEntry {
  id: number;
  value_type: string;
  value: string;
  reason: string;
  created_by: string;
}

export interface LgConfig {
  lg_commission_rate: string;
  lg_payment_instructions: string;
  lg_sms_provider: string;
  lg_sms_sender_id: string;
  lg_sms_api_key: string; // masked
}

export const DRIVER_STATUSES = [
  { value: "draft", label: "草稿", tag: "info" },
  { value: "pending_review", label: "待审核", tag: "warning" },
  { value: "approved", label: "已通过", tag: "success" },
  { value: "rejected", label: "已驳回", tag: "danger" },
  { value: "frozen", label: "已冻结", tag: "info" },
] as const;

export const VEHICLE_STATUSES = [
  { value: "pending_review", label: "待审核", tag: "warning" },
  { value: "approved", label: "已通过", tag: "success" },
  { value: "rejected", label: "已驳回", tag: "danger" },
  { value: "deactivated", label: "已停用", tag: "info" },
] as const;

export const ROUTE_STATUSES = [
  { value: "pending_review", label: "待审核", tag: "warning" },
  { value: "approved", label: "已通过", tag: "success" },
  { value: "rejected", label: "已驳回", tag: "danger" },
  { value: "suspended", label: "已暂停", tag: "info" },
] as const;

export const ORDER_STATUSES = [
  { value: "submitted", label: "待处理", tag: "warning" },
  { value: "price_confirmed", label: "已确认价格", tag: "primary" },
  { value: "awaiting_pickup", label: "待取货", tag: "primary" },
  { value: "in_transit", label: "运输中", tag: "primary" },
  { value: "delivered", label: "已送达", tag: "success" },
  { value: "completed", label: "已完成", tag: "success" },
  { value: "cancelled", label: "已取消", tag: "info" },
  { value: "exception_closed", label: "异常关闭", tag: "danger" },
] as const;

export const COMMISSION_STATUSES = [
  { value: "pending", label: "待结算", tag: "warning" },
  { value: "settled", label: "已结算", tag: "success" },
  { value: "waived", label: "已豁免", tag: "info" },
] as const;

// Element Plus el-tag `type` accepts this union; keep statusMeta's return assignable to it.
export type TagType = "success" | "info" | "warning" | "danger" | "primary";

export function statusMeta(
  list: readonly { value: string; label: string; tag: string }[],
  value: string,
): { label: string; tag: TagType } {
  const found = list.find((s) => s.value === value);
  return found
    ? { label: found.label, tag: found.tag as TagType }
    : { label: value, tag: "info" };
}
```

- [ ] **Step 2: Verify typecheck**

Run (from `admin/`): `npx vue-tsc --noEmit` → exit 0

- [ ] **Step 3: Commit**

```bash
git add admin/src/api/types.ts
git commit -m "feat(admin): logistics types and status option constants"
```

---

### Task 3: Frontend endpoints

**Files:**
- Modify: `admin/src/api/endpoints.ts`

- [ ] **Step 1: Append the logistics endpoint functions**

Add these imports to the existing `import type { … } from "./types"` block:
`BlacklistEntry, LgCommission, LgConfig, LgDriver, LgOrder, LgOrderDetail, LgRoute, LgVehicle, Staff, StatsOverview`.

Append to `admin/src/api/endpoints.ts`:

```typescript
export async function me(): Promise<{ username: string; role: string }> {
  return (await api.get<{ username: string; role: string }>("/auth/me")).data;
}

export interface PageParams {
  status?: string;
  page?: number;
  page_size?: number;
}

// --- dashboard
export async function lgStats(range?: { start?: string; end?: string }): Promise<StatsOverview> {
  return (await api.get<StatsOverview>("/lg/stats/overview", { params: range })).data;
}

// --- drivers
export async function lgDrivers(params: PageParams): Promise<Paginated<LgDriver>> {
  return (await api.get<Paginated<LgDriver>>("/lg/drivers", { params })).data;
}
export async function lgReviewDriver(id: number, action: "approve" | "reject", reason: string): Promise<LgDriver> {
  return (await api.post<LgDriver>(`/lg/drivers/${id}/review`, { action, reason })).data;
}
export async function lgFreezeDriver(id: number, reason: string): Promise<LgDriver> {
  return (await api.post<LgDriver>(`/lg/drivers/${id}/freeze`, { reason })).data;
}
export async function lgUnfreezeDriver(id: number): Promise<LgDriver> {
  return (await api.post<LgDriver>(`/lg/drivers/${id}/unfreeze`)).data;
}

// --- vehicles
export async function lgVehicles(params: PageParams): Promise<Paginated<LgVehicle>> {
  return (await api.get<Paginated<LgVehicle>>("/lg/vehicles", { params })).data;
}
export async function lgReviewVehicle(id: number, action: "approve" | "reject", reason: string): Promise<LgVehicle> {
  return (await api.post<LgVehicle>(`/lg/vehicles/${id}/review`, { action, reason })).data;
}

// --- routes
export async function lgRoutes(params: PageParams): Promise<Paginated<LgRoute>> {
  return (await api.get<Paginated<LgRoute>>("/lg/routes", { params })).data;
}
export async function lgReviewRoute(id: number, action: "approve" | "reject", reason: string): Promise<LgRoute> {
  return (await api.post<LgRoute>(`/lg/routes/${id}/review`, { action, reason })).data;
}
export async function lgSuspendRoute(id: number, reason: string): Promise<LgRoute> {
  return (await api.post<LgRoute>(`/lg/routes/${id}/suspend`, { reason })).data;
}
export async function lgResumeRoute(id: number): Promise<LgRoute> {
  return (await api.post<LgRoute>(`/lg/routes/${id}/resume`)).data;
}

// --- orders
export async function lgOrders(params: PageParams): Promise<Paginated<LgOrder>> {
  return (await api.get<Paginated<LgOrder>>("/lg/orders", { params })).data;
}
export async function lgOrder(id: number): Promise<LgOrderDetail> {
  return (await api.get<LgOrderDetail>(`/lg/orders/${id}`)).data;
}
export interface ConfirmPriceBody {
  freight_ghs: number;
  pickup_time: string;
  commission_ghs?: number;
  override_reason?: string;
}
export async function lgConfirmPrice(id: number, body: ConfirmPriceBody): Promise<LgOrderDetail> {
  return (await api.post<LgOrderDetail>(`/lg/orders/${id}/confirm-price`, body)).data;
}
export async function lgReassign(id: number, tripId: number): Promise<LgOrderDetail> {
  return (await api.post<LgOrderDetail>(`/lg/orders/${id}/reassign`, { trip_id: tripId })).data;
}
export async function lgCancelOrder(id: number, reason: string): Promise<LgOrderDetail> {
  return (await api.post<LgOrderDetail>(`/lg/orders/${id}/cancel`, { reason })).data;
}
export async function lgExceptionClose(id: number, reason: string): Promise<LgOrderDetail> {
  return (await api.post<LgOrderDetail>(`/lg/orders/${id}/exception-close`, { reason })).data;
}
export async function lgCompleteOrder(id: number): Promise<LgOrderDetail> {
  return (await api.post<LgOrderDetail>(`/lg/orders/${id}/complete`)).data;
}
export async function lgAddRemark(id: number, body: string): Promise<void> {
  await api.post(`/lg/orders/${id}/remarks`, { body });
}

// --- commissions
export async function lgCommissions(params: PageParams & { driver_id?: number }): Promise<Paginated<LgCommission>> {
  return (await api.get<Paginated<LgCommission>>("/lg/commissions", { params })).data;
}
export async function lgSettleCommission(id: number, method: string, reference: string): Promise<LgCommission> {
  return (await api.post<LgCommission>(`/lg/commissions/${id}/settle`, { method, reference })).data;
}
export async function lgWaiveCommission(id: number, reason: string): Promise<LgCommission> {
  return (await api.post<LgCommission>(`/lg/commissions/${id}/waive`, { reason })).data;
}

// --- config / staff / blacklist
export async function lgConfig(): Promise<LgConfig> {
  return (await api.get<LgConfig>("/lg/config")).data;
}
export async function lgUpdateConfig(body: Partial<LgConfig>): Promise<{ ok: boolean }> {
  return (await api.put<{ ok: boolean }>("/lg/config", body)).data;
}
export async function lgStaff(): Promise<Staff[]> {
  return (await api.get<Staff[]>("/lg/staff")).data;
}
export async function lgCreateStaff(body: { username: string; password: string; role: string }): Promise<Staff> {
  return (await api.post<Staff>("/lg/staff", body)).data;
}
export async function lgBlacklist(): Promise<BlacklistEntry[]> {
  return (await api.get<BlacklistEntry[]>("/lg/blacklist")).data;
}
export async function lgAddBlacklist(body: { value_type: string; value: string; reason: string }): Promise<BlacklistEntry> {
  return (await api.post<BlacklistEntry>("/lg/blacklist", body)).data;
}
export async function lgDeleteBlacklist(id: number): Promise<void> {
  await api.delete(`/lg/blacklist/${id}`);
}
```

- [ ] **Step 2: Verify typecheck**

Run: `npx vue-tsc --noEmit` → exit 0

- [ ] **Step 3: Commit**

```bash
git add admin/src/api/endpoints.ts
git commit -m "feat(admin): logistics endpoint functions + me()"
```

---

### Task 4: Auth store gains `role`

**Files:**
- Modify: `admin/src/stores/auth.ts`, `admin/src/api/client.ts`

- [ ] **Step 1: Add a role storage key**

In `admin/src/api/client.ts`, after `export const USER_KEY = "zoko-admin-user";` add:

```typescript
export const ROLE_KEY = "zoko-admin-role";
```

and in `handleApiError`'s 401 branch, also clear it — change the two `removeItem` lines to three:

```typescript
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(ROLE_KEY);
```

- [ ] **Step 2: Implement the store change**

Replace `admin/src/stores/auth.ts`:

```typescript
import { defineStore } from "pinia";

import { ROLE_KEY, TOKEN_KEY, USER_KEY } from "../api/client";
import { login as apiLogin, me } from "../api/endpoints";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) ?? "",
    username: localStorage.getItem(USER_KEY) ?? "",
    role: localStorage.getItem(ROLE_KEY) ?? "",
  }),
  getters: {
    isLoggedIn: (state) => state.token.length > 0,
  },
  actions: {
    async login(username: string, password: string) {
      const { access_token } = await apiLogin(username, password);
      this.token = access_token;
      localStorage.setItem(TOKEN_KEY, access_token);
      // token is set before me() so the interceptor attaches the bearer
      const who = await me();
      this.username = who.username;
      this.role = who.role;
      localStorage.setItem(USER_KEY, who.username);
      localStorage.setItem(ROLE_KEY, who.role);
    },
    can(roles: string[]): boolean {
      return roles.includes(this.role);
    },
    logout() {
      this.token = "";
      this.username = "";
      this.role = "";
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      localStorage.removeItem(ROLE_KEY);
    },
  },
});
```

- [ ] **Step 3: Verify typecheck**

Run: `npx vue-tsc --noEmit` → exit 0

- [ ] **Step 4: Commit**

```bash
git add admin/src/stores/auth.ts admin/src/api/client.ts
git commit -m "feat(admin): auth store tracks staff role"
```

---

### Task 5: Router routes + role guard + sidebar submenu

**Files:**
- Modify: `admin/src/router.ts`, `admin/src/layout/AdminLayout.vue`

- [ ] **Step 1: Add the logistics routes with `meta.roles` and a role guard**

In `admin/src/router.ts`, add these child routes inside the `AdminLayout` `children` array
(after the `settings` route):

```typescript
        { path: "lg/dashboard", name: "lg-dashboard", component: () => import("./views/lg/LgDashboardView.vue"), meta: { roles: ["admin", "auditor", "cs"] } },
        { path: "lg/drivers", name: "lg-drivers", component: () => import("./views/lg/LgDriversView.vue"), meta: { roles: ["admin", "auditor"] } },
        { path: "lg/vehicles", name: "lg-vehicles", component: () => import("./views/lg/LgVehiclesView.vue"), meta: { roles: ["admin", "auditor"] } },
        { path: "lg/routes", name: "lg-routes", component: () => import("./views/lg/LgRoutesView.vue"), meta: { roles: ["admin", "auditor"] } },
        { path: "lg/orders", name: "lg-orders", component: () => import("./views/lg/LgOrdersView.vue"), meta: { roles: ["admin", "cs"] } },
        { path: "lg/commissions", name: "lg-commissions", component: () => import("./views/lg/LgCommissionsView.vue"), meta: { roles: ["admin", "cs"] } },
        { path: "lg/config", name: "lg-config", component: () => import("./views/lg/LgConfigView.vue"), meta: { roles: ["admin"] } },
        { path: "lg/staff", name: "lg-staff", component: () => import("./views/lg/LgStaffView.vue"), meta: { roles: ["admin"] } },
        { path: "lg/blacklist", name: "lg-blacklist", component: () => import("./views/lg/LgBlacklistView.vue"), meta: { roles: ["admin"] } },
```

Replace the guard at the bottom of the file:

```typescript
import { TOKEN_KEY, ROLE_KEY } from "./api/client";

router.beforeEach((to) => {
  if (to.name !== "login" && !localStorage.getItem(TOKEN_KEY)) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  const roles = to.meta.roles as string[] | undefined;
  if (roles) {
    const role = localStorage.getItem(ROLE_KEY) ?? "";
    if (!roles.includes(role)) return { name: "lg-dashboard" };
  }
});
```

(Change the existing top-of-file `import { TOKEN_KEY } from "./api/client";` to also import
`ROLE_KEY`, or add the import shown above — keep a single import line.)

- [ ] **Step 2: Add the role-filtered 物流 submenu**

Replace the `<el-menu>` block and script in `admin/src/layout/AdminLayout.vue`. Template menu:

```vue
      <el-menu :default-active="route.path" router class="menu">
        <el-menu-item index="/articles">新闻管理</el-menu-item>
        <el-menu-item index="/sites">国家与站点</el-menu-item>
        <el-menu-item index="/pipeline">抓取与翻译</el-menu-item>
        <el-menu-item index="/settings">系统设置</el-menu-item>
        <el-sub-menu index="lg">
          <template #title>物流</template>
          <el-menu-item
            v-for="item in lgMenu"
            :key="item.path"
            :index="item.path"
          >{{ item.label }}</el-menu-item>
        </el-sub-menu>
      </el-menu>
```

In the `<script setup>` block, add after `const auth = useAuthStore();`:

```typescript
import { computed } from "vue";

const LG_ITEMS = [
  { path: "/lg/dashboard", label: "物流看板", roles: ["admin", "auditor", "cs"] },
  { path: "/lg/drivers", label: "司机审核", roles: ["admin", "auditor"] },
  { path: "/lg/vehicles", label: "车辆审核", roles: ["admin", "auditor"] },
  { path: "/lg/routes", label: "线路审核", roles: ["admin", "auditor"] },
  { path: "/lg/orders", label: "订单工作台", roles: ["admin", "cs"] },
  { path: "/lg/commissions", label: "佣金结算", roles: ["admin", "cs"] },
  { path: "/lg/config", label: "物流设置", roles: ["admin"] },
  { path: "/lg/staff", label: "员工管理", roles: ["admin"] },
  { path: "/lg/blacklist", label: "黑名单", roles: ["admin"] },
];
const lgMenu = computed(() => LG_ITEMS.filter((i) => i.roles.includes(auth.role)));
```

- [ ] **Step 3: Verify typecheck**

Run: `npx vue-tsc --noEmit` → exit 0 (view files are lazy imports; they are created in later
tasks. To keep the build green now, create nine one-line stubs:)

```bash
cd admin/src/views && mkdir -p lg && cd lg
for f in LgDashboardView LgDriversView LgVehiclesView LgRoutesView LgOrdersView LgCommissionsView LgConfigView LgStaffView LgBlacklistView; do
  printf '<template><div /></template>\n' > "$f.vue"
done
cd ../../../..
```

Each stub is fully replaced by its task below. Run `npx vue-tsc --noEmit` again → exit 0.

- [ ] **Step 4: Commit**

```bash
git add admin/src/router.ts admin/src/layout/AdminLayout.vue admin/src/views/lg
git commit -m "feat(admin): logistics routes, role guard, and sidebar submenu"
```

---

### Task 6: `AuthImage` component

**Files:**
- Create: `admin/src/components/AuthImage.vue`

- [ ] **Step 1: Implement**

`<img src>` cannot carry the admin bearer, so fetch the auth-gated attachment as a blob with
the bearer and render via an object URL. The attachment lives at the H5 path
`/api/lg/uploads/{id}` (not `/api/admin`), and `get_principal` accepts admin tokens.

Create `admin/src/components/AuthImage.vue`:

```vue
<script setup lang="ts">
import axios from "axios";
import { onBeforeUnmount, ref, watch } from "vue";

import { TOKEN_KEY } from "../api/client";

const props = defineProps<{ id: string }>();
const src = ref("");
const failed = ref(false);

async function load(id: string) {
  revoke();
  failed.value = false;
  if (!id) return;
  try {
    const token = localStorage.getItem(TOKEN_KEY) ?? "";
    const resp = await axios.get(`/api/lg/uploads/${id}`, {
      responseType: "blob",
      headers: { Authorization: `Bearer ${token}` },
    });
    src.value = URL.createObjectURL(resp.data);
  } catch {
    failed.value = true;
  }
}

function revoke() {
  if (src.value) {
    URL.revokeObjectURL(src.value);
    src.value = "";
  }
}

watch(() => props.id, (id) => load(id), { immediate: true });
onBeforeUnmount(revoke);
</script>

<template>
  <el-image v-if="src" :src="src" :preview-src-list="[src]" fit="cover" class="auth-img" />
  <div v-else class="auth-img placeholder">{{ failed ? "加载失败" : "…" }}</div>
</template>

<style scoped>
.auth-img { width: 96px; height: 96px; border-radius: 6px; border: 1px solid #e4e7ed; }
.placeholder { display: flex; align-items: center; justify-content: center; color: #93918a; font-size: 12px; }
</style>
```

- [ ] **Step 2: Verify typecheck**

Run: `npx vue-tsc --noEmit` → exit 0

- [ ] **Step 3: Verify the admin bearer actually works against the uploads endpoint**

Quick manual check (backend seeded + running on :8000; any driver with an uploaded attachment,
or reuse an id from the DB). Confirm an admin token can GET an attachment:

```bash
TOKEN=$(curl -s localhost:8000/api/admin/auth/login -H 'content-type: application/json' -d '{"username":"admin","password":"admin123"}' | sed -E 's/.*"access_token":"([^"]+)".*/\1/')
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/api/lg/uploads/SOME_ATTACHMENT_ID -H "Authorization: Bearer $TOKEN"
```

Expected: `200` (proves no proxy route is needed). If it returns 401/403, STOP and add an
`/api/admin/lg/uploads/{id}` proxy route before proceeding — but per the design it returns 200.

- [ ] **Step 4: Commit**

```bash
git add admin/src/components/AuthImage.vue
git commit -m "feat(admin): AuthImage loads auth-gated attachments as blobs"
```

---

### Task 7: `ReviewDialog` component + Driver review view

**Files:**
- Create: `admin/src/components/ReviewDialog.vue`
- Replace: `admin/src/views/lg/LgDriversView.vue`

- [ ] **Step 1: Implement the shared review dialog**

Create `admin/src/components/ReviewDialog.vue`:

```vue
<script setup lang="ts">
import { ElMessage } from "element-plus";
import { ref, watch } from "vue";

const props = defineProps<{
  modelValue: boolean;
  title: string;
  images: { label: string; id: string }[];
}>();
const emit = defineEmits<{
  "update:modelValue": [boolean];
  decide: [action: "approve" | "reject", reason: string];
}>();

const reason = ref("");
const busy = ref(false);

watch(() => props.modelValue, (open) => {
  if (open) reason.value = "";
});

async function decide(action: "approve" | "reject") {
  if (action === "reject" && !reason.value.trim()) {
    ElMessage.warning("驳回需填写原因");
    return;
  }
  busy.value = true;
  try {
    emit("decide", action, reason.value.trim());
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="720px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="gallery">
      <div v-for="img in images" :key="img.id" class="cell">
        <span class="lbl">{{ img.label }}</span>
        <AuthImage :id="img.id" />
      </div>
    </div>
    <slot />
    <el-input
      v-model="reason"
      type="textarea"
      :rows="2"
      placeholder="驳回原因（通过可留空）"
      class="reason"
    />
    <template #footer>
      <el-button :loading="busy" @click="emit('update:modelValue', false)">关闭</el-button>
      <el-button type="danger" :loading="busy" @click="decide('reject')">驳回</el-button>
      <el-button type="primary" :loading="busy" @click="decide('approve')">通过</el-button>
    </template>
  </el-dialog>
</template>

<script lang="ts">
import AuthImage from "./AuthImage.vue";
export default { components: { AuthImage } };
</script>

<style scoped>
.gallery { display: flex; flex-wrap: wrap; gap: 12px; }
.cell { display: flex; flex-direction: column; gap: 4px; }
.lbl { font-size: 12px; color: #606266; }
.reason { margin-top: 12px; }
</style>
```

- [ ] **Step 2: Implement the driver review view**

Replace `admin/src/views/lg/LgDriversView.vue`:

```vue
<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { onMounted, ref } from "vue";

import { lgDrivers, lgFreezeDriver, lgReviewDriver, lgUnfreezeDriver } from "../../api/endpoints";
import { DRIVER_STATUSES, statusMeta, type LgDriver } from "../../api/types";
import ReviewDialog from "../../components/ReviewDialog.vue";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();
const rows = ref<LgDriver[]>([]);
const total = ref(0);
const page = ref(1);
const status = ref("pending_review");
const loading = ref(false);

const dialog = ref(false);
const current = ref<LgDriver | null>(null);

async function load() {
  loading.value = true;
  try {
    const data = await lgDrivers({ status: status.value || undefined, page: page.value, page_size: 20 });
    rows.value = data.items;
    total.value = data.total;
  } catch {
    /* interceptor toasted */
  } finally {
    loading.value = false;
  }
}
onMounted(load);

function openReview(d: LgDriver) {
  current.value = d;
  dialog.value = true;
}

async function decide(action: "approve" | "reject", reason: string) {
  if (!current.value) return;
  try {
    await lgReviewDriver(current.value.id, action, reason);
    ElMessage.success(action === "approve" ? "已通过" : "已驳回");
    dialog.value = false;
    await load();
  } catch {
    /* interceptor toasted */
  }
}

async function freeze(d: LgDriver) {
  try {
    const { value } = await ElMessageBox.prompt("冻结原因", "冻结司机", { inputPattern: /.+/, inputErrorMessage: "请填写原因" });
    await lgFreezeDriver(d.id, value);
    ElMessage.success("已冻结");
    await load();
  } catch {
    /* cancelled or toasted */
  }
}

async function unfreeze(d: LgDriver) {
  await lgUnfreezeDriver(d.id);
  ElMessage.success("已解冻");
  await load();
}
</script>

<template>
  <div>
    <div class="bar">
      <el-select v-model="status" placeholder="全部状态" clearable style="width: 160px" @change="page = 1; load()">
        <el-option v-for="s in DRIVER_STATUSES" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
    </div>

    <el-table v-loading="loading" :data="rows" stripe>
      <el-table-column prop="full_name" label="姓名" width="120" />
      <el-table-column prop="phone" label="电话" width="150" />
      <el-table-column prop="ghana_card_number" label="Ghana Card" width="170" />
      <el-table-column label="驾照" width="120">
        <template #default="{ row }">{{ row.licence_class }} · {{ row.licence_expiry }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusMeta(DRIVER_STATUSES, row.status).tag">{{ statusMeta(DRIVER_STATUSES, row.status).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending_review'" link type="primary" @click="openReview(row)">审核</el-button>
          <el-button v-if="auth.can(['admin']) && row.status === 'approved'" link type="warning" @click="freeze(row)">冻结</el-button>
          <el-button v-if="auth.can(['admin']) && row.status === 'frozen'" link type="success" @click="unfreeze(row)">解冻</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager" layout="prev, pager, next" :total="total" :page-size="20"
      :current-page="page" @current-change="(p: number) => { page = p; load(); }"
    />

    <ReviewDialog
      v-if="current"
      v-model="dialog"
      :title="`审核司机 · ${current.full_name}`"
      :images="[
        { label: 'Ghana Card 正面', id: current.ghana_card_front_id },
        { label: 'Ghana Card 背面', id: current.ghana_card_back_id },
        { label: '驾照', id: current.licence_photo_id },
      ]"
      @decide="decide"
    >
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="性别">{{ current.gender }}</el-descriptions-item>
        <el-descriptions-item label="出生日期">{{ current.date_of_birth }}</el-descriptions-item>
        <el-descriptions-item label="驾照号">{{ current.licence_number }}</el-descriptions-item>
        <el-descriptions-item label="紧急联系人">{{ current.emergency_contact_name }} · {{ current.emergency_contact_phone }}</el-descriptions-item>
      </el-descriptions>
    </ReviewDialog>
  </div>
</template>

<style scoped>
.bar { margin-bottom: 12px; }
.pager { margin-top: 12px; justify-content: flex-end; }
</style>
```

- [ ] **Step 3: Verify typecheck**

Run: `npx vue-tsc --noEmit` → exit 0

- [ ] **Step 4: Commit**

```bash
git add admin/src/components/ReviewDialog.vue admin/src/views/lg/LgDriversView.vue
git commit -m "feat(admin): shared review dialog + driver review queue"
```

---

### Task 8: Vehicle review view

**Files:**
- Replace: `admin/src/views/lg/LgVehiclesView.vue`

- [ ] **Step 1: Implement**

Replace `admin/src/views/lg/LgVehiclesView.vue`:

```vue
<script setup lang="ts">
import { ElMessage } from "element-plus";
import { onMounted, ref } from "vue";

import { lgReviewVehicle, lgVehicles } from "../../api/endpoints";
import { statusMeta, VEHICLE_STATUSES, type LgVehicle } from "../../api/types";
import ReviewDialog from "../../components/ReviewDialog.vue";

const rows = ref<LgVehicle[]>([]);
const total = ref(0);
const page = ref(1);
const status = ref("pending_review");
const loading = ref(false);
const dialog = ref(false);
const current = ref<LgVehicle | null>(null);

async function load() {
  loading.value = true;
  try {
    const data = await lgVehicles({ status: status.value || undefined, page: page.value, page_size: 20 });
    rows.value = data.items;
    total.value = data.total;
  } catch {
    /* toasted */
  } finally {
    loading.value = false;
  }
}
onMounted(load);

function openReview(v: LgVehicle) {
  current.value = v;
  dialog.value = true;
}

async function decide(action: "approve" | "reject", reason: string) {
  if (!current.value) return;
  try {
    await lgReviewVehicle(current.value.id, action, reason);
    ElMessage.success(action === "approve" ? "已通过" : "已驳回");
    dialog.value = false;
    await load();
  } catch {
    /* toasted */
  }
}
</script>

<template>
  <div>
    <div class="bar">
      <el-select v-model="status" placeholder="全部状态" clearable style="width: 160px" @change="page = 1; load()">
        <el-option v-for="s in VEHICLE_STATUSES" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
    </div>

    <el-table v-loading="loading" :data="rows" stripe>
      <el-table-column prop="plate_number" label="车牌" width="130" />
      <el-table-column prop="vehicle_type" label="类型" width="120" />
      <el-table-column prop="brand_model" label="品牌型号" />
      <el-table-column label="载重/容积" width="150">
        <template #default="{ row }">{{ row.max_load_kg }}kg · {{ row.max_volume_m3 }}m³</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusMeta(VEHICLE_STATUSES, row.status).tag">{{ statusMeta(VEHICLE_STATUSES, row.status).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending_review'" link type="primary" @click="openReview(row)">审核</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager" layout="prev, pager, next" :total="total" :page-size="20"
      :current-page="page" @current-change="(p: number) => { page = p; load(); }"
    />

    <ReviewDialog
      v-if="current"
      v-model="dialog"
      :title="`审核车辆 · ${current.plate_number}`"
      :images="[
        { label: '前', id: current.photo_front_id },
        { label: '左', id: current.photo_left_id },
        { label: '右', id: current.photo_right_id },
        { label: '后', id: current.photo_rear_id },
        { label: '货厢', id: current.photo_interior_id },
        { label: '行驶证', id: current.reg_cert_id },
        { label: '年检', id: current.roadworthy_cert_id },
        { label: '保险', id: current.insurance_cert_id },
      ]"
      @decide="decide"
    >
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="年检到期">{{ current.roadworthy_expiry }}</el-descriptions-item>
        <el-descriptions-item label="保险到期">{{ current.insurance_expiry }}</el-descriptions-item>
        <el-descriptions-item label="年份">{{ current.year }}</el-descriptions-item>
        <el-descriptions-item label="VIN">{{ current.vin || "—" }}</el-descriptions-item>
      </el-descriptions>
    </ReviewDialog>
  </div>
</template>

<style scoped>
.bar { margin-bottom: 12px; }
.pager { margin-top: 12px; justify-content: flex-end; }
</style>
```

- [ ] **Step 2: Verify typecheck**

Run: `npx vue-tsc --noEmit` → exit 0

- [ ] **Step 3: Commit**

```bash
git add admin/src/views/lg/LgVehiclesView.vue
git commit -m "feat(admin): vehicle review queue"
```

---

### Task 9: Route review view

**Files:**
- Replace: `admin/src/views/lg/LgRoutesView.vue`

- [ ] **Step 1: Implement**

Replace `admin/src/views/lg/LgRoutesView.vue`:

```vue
<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { onMounted, ref } from "vue";

import { lgResumeRoute, lgReviewRoute, lgRoutes, lgSuspendRoute } from "../../api/endpoints";
import { ROUTE_STATUSES, statusMeta, type LgRoute } from "../../api/types";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();
const rows = ref<LgRoute[]>([]);
const total = ref(0);
const page = ref(1);
const status = ref("pending_review");
const loading = ref(false);
const dialog = ref(false);
const current = ref<LgRoute | null>(null);
const reason = ref("");

async function load() {
  loading.value = true;
  try {
    const data = await lgRoutes({ status: status.value || undefined, page: page.value, page_size: 20 });
    rows.value = data.items;
    total.value = data.total;
  } catch {
    /* toasted */
  } finally {
    loading.value = false;
  }
}
onMounted(load);

function openReview(r: LgRoute) {
  current.value = r;
  reason.value = "";
  dialog.value = true;
}

function priceLabel(r: LgRoute): string {
  if (r.negotiable) return "面议";
  const parts: string[] = [];
  if (r.rate_per_ton) parts.push(`GHS ${r.rate_per_ton}/吨`);
  if (r.rate_per_m3) parts.push(`GHS ${r.rate_per_m3}/m³`);
  return parts.join(" · ") || "—";
}

async function decide(action: "approve" | "reject") {
  if (!current.value) return;
  if (action === "reject" && !reason.value.trim()) {
    ElMessage.warning("驳回需填写原因");
    return;
  }
  try {
    await lgReviewRoute(current.value.id, action, reason.value.trim());
    ElMessage.success(action === "approve" ? "已通过" : "已驳回");
    dialog.value = false;
    await load();
  } catch {
    /* toasted */
  }
}

async function suspend(r: LgRoute) {
  try {
    const { value } = await ElMessageBox.prompt("暂停原因", "暂停线路", { inputPattern: /.+/, inputErrorMessage: "请填写原因" });
    await lgSuspendRoute(r.id, value);
    ElMessage.success("已暂停");
    await load();
  } catch {
    /* cancelled or toasted */
  }
}

async function resume(r: LgRoute) {
  await lgResumeRoute(r.id);
  ElMessage.success("已恢复");
  await load();
}
</script>

<template>
  <div>
    <div class="bar">
      <el-select v-model="status" placeholder="全部状态" clearable style="width: 160px" @change="page = 1; load()">
        <el-option v-for="s in ROUTE_STATUSES" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
    </div>

    <el-table v-loading="loading" :data="rows" stripe>
      <el-table-column label="线路">
        <template #default="{ row }">{{ row.origin_town }} → {{ row.dest_town }}</template>
      </el-table-column>
      <el-table-column prop="frequency" label="班次" width="90" />
      <el-table-column label="定价" width="200">
        <template #default="{ row }">{{ priceLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusMeta(ROUTE_STATUSES, row.status).tag">{{ statusMeta(ROUTE_STATUSES, row.status).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending_review'" link type="primary" @click="openReview(row)">审核</el-button>
          <el-button v-if="auth.can(['admin']) && row.status === 'approved'" link type="warning" @click="suspend(row)">暂停</el-button>
          <el-button v-if="auth.can(['admin']) && row.status === 'suspended'" link type="success" @click="resume(row)">恢复</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager" layout="prev, pager, next" :total="total" :page-size="20"
      :current-page="page" @current-change="(p: number) => { page = p; load(); }"
    />

    <el-dialog v-if="current" v-model="dialog" :title="`审核线路 · ${current.origin_town} → ${current.dest_town}`" width="600px">
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="途经">{{ current.via_towns.join("、") || "—" }}</el-descriptions-item>
        <el-descriptions-item label="发车">{{ current.depart_time }} · 约{{ current.est_duration_hours }}小时</el-descriptions-item>
        <el-descriptions-item label="可运货物">{{ current.cargo_types.join("、") }}</el-descriptions-item>
        <el-descriptions-item label="禁运">{{ current.prohibited_notes || "—" }}</el-descriptions-item>
        <el-descriptions-item label="定价">{{ priceLabel(current) }}</el-descriptions-item>
      </el-descriptions>
      <el-input v-model="reason" type="textarea" :rows="2" placeholder="驳回原因（通过可留空）" style="margin-top: 12px" />
      <template #footer>
        <el-button @click="dialog = false">关闭</el-button>
        <el-button type="danger" @click="decide('reject')">驳回</el-button>
        <el-button type="primary" @click="decide('approve')">通过</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.bar { margin-bottom: 12px; }
.pager { margin-top: 12px; justify-content: flex-end; }
</style>
```

- [ ] **Step 2: Verify typecheck**

Run: `npx vue-tsc --noEmit` → exit 0

- [ ] **Step 3: Commit**

```bash
git add admin/src/views/lg/LgRoutesView.vue
git commit -m "feat(admin): route review queue"
```

---

### Task 10: Dashboard view

**Files:**
- Replace: `admin/src/views/lg/LgDashboardView.vue`

- [ ] **Step 1: Implement**

Replace `admin/src/views/lg/LgDashboardView.vue`:

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";

import { lgStats } from "../../api/endpoints";
import type { StatsOverview } from "../../api/types";

const stats = ref<StatsOverview | null>(null);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    stats.value = await lgStats();
  } catch {
    /* toasted */
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>

<template>
  <div v-loading="loading">
    <template v-if="stats">
      <div class="cards">
        <el-card class="kpi"><div class="n">{{ stats.drivers.approved ?? 0 }}</div><div class="l">已通过司机</div></el-card>
        <el-card class="kpi"><div class="n">{{ stats.vehicles }}</div><div class="l">车辆</div></el-card>
        <el-card class="kpi"><div class="n">{{ stats.routes_active }}</div><div class="l">在营线路</div></el-card>
        <el-card class="kpi"><div class="n">{{ stats.trips_upcoming }}</div><div class="l">未来行程</div></el-card>
        <el-card class="kpi"><div class="n">{{ stats.orders_total }}</div><div class="l">订单总数</div></el-card>
        <el-card class="kpi"><div class="n">GHS {{ stats.gmv_ghs }}</div><div class="l">成交额(GMV)</div></el-card>
        <el-card class="kpi"><div class="n">GHS {{ stats.commission.pending_ghs }}</div><div class="l">待结算佣金</div></el-card>
        <el-card class="kpi"><div class="n">GHS {{ stats.commission.settled_ghs }}</div><div class="l">已结算佣金</div></el-card>
        <el-card class="kpi"><div class="n">{{ (stats.completion_rate * 100).toFixed(0) }}%</div><div class="l">完成率</div></el-card>
        <el-card class="kpi"><div class="n">{{ (stats.cancellation_rate * 100).toFixed(0) }}%</div><div class="l">取消率</div></el-card>
        <el-card class="kpi"><div class="n">{{ (stats.capacity_utilization * 100).toFixed(0) }}%</div><div class="l">运力利用率</div></el-card>
      </div>

      <el-card class="lanes" header="热门线路">
        <el-table :data="stats.top_lanes" size="small">
          <el-table-column prop="lane" label="线路" />
          <el-table-column prop="orders" label="订单数" width="120" />
        </el-table>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
.kpi { text-align: center; }
.kpi .n { font-size: 22px; font-weight: 600; color: #1d9e75; }
.kpi .l { font-size: 12px; color: #606266; margin-top: 4px; }
.lanes { margin-top: 16px; max-width: 520px; }
</style>
```

- [ ] **Step 2: Verify typecheck**

Run: `npx vue-tsc --noEmit` → exit 0

- [ ] **Step 3: Commit**

```bash
git add admin/src/views/lg/LgDashboardView.vue
git commit -m "feat(admin): logistics dashboard"
```

---

### Task 11: Order workspace view

**Files:**
- Replace: `admin/src/views/lg/LgOrdersView.vue`

- [ ] **Step 1: Implement**

Replace `admin/src/views/lg/LgOrdersView.vue`:

```vue
<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { onMounted, reactive, ref } from "vue";

import {
  lgAddRemark, lgCancelOrder, lgCompleteOrder, lgConfirmPrice, lgExceptionClose,
  lgOrder, lgOrders, lgReassign,
} from "../../api/endpoints";
import { ORDER_STATUSES, statusMeta, type LgOrder, type LgOrderDetail } from "../../api/types";

const rows = ref<LgOrder[]>([]);
const total = ref(0);
const page = ref(1);
const status = ref("submitted");
const loading = ref(false);

const drawer = ref(false);
const detail = ref<LgOrderDetail | null>(null);
const remarkText = ref("");
const price = reactive({ freight_ghs: 0, pickup_time: "", commission_ghs: undefined as number | undefined, override_reason: "" });

async function load() {
  loading.value = true;
  try {
    const data = await lgOrders({ status: status.value || undefined, page: page.value, page_size: 20 });
    rows.value = data.items;
    total.value = data.total;
  } catch {
    /* toasted */
  } finally {
    loading.value = false;
  }
}
onMounted(load);

async function open(id: number) {
  detail.value = await lgOrder(id);
  price.freight_ghs = detail.value.freight_ghs ?? 0;
  price.pickup_time = detail.value.pickup_time ?? "";
  price.commission_ghs = undefined;
  price.override_reason = "";
  remarkText.value = "";
  drawer.value = true;
}

async function refresh() {
  if (detail.value) detail.value = await lgOrder(detail.value.id);
  await load();
}

async function confirmPrice() {
  if (!detail.value) return;
  try {
    await lgConfirmPrice(detail.value.id, {
      freight_ghs: price.freight_ghs,
      pickup_time: price.pickup_time,
      commission_ghs: price.commission_ghs,
      override_reason: price.override_reason || undefined,
    });
    ElMessage.success("已确认价格");
    await refresh();
  } catch {
    /* toasted (incl. 409 capacity shortfall) */
  }
}

async function reassign() {
  if (!detail.value) return;
  try {
    const { value } = await ElMessageBox.prompt("目标行程 ID", "改派", { inputPattern: /^\d+$/, inputErrorMessage: "请输入行程 ID" });
    await lgReassign(detail.value.id, Number(value));
    ElMessage.success("已改派");
    await refresh();
  } catch {
    /* cancelled or toasted */
  }
}

async function closeOrder(kind: "cancel" | "exception") {
  if (!detail.value) return;
  try {
    const { value } = await ElMessageBox.prompt(kind === "cancel" ? "取消原因" : "异常处理说明", kind === "cancel" ? "取消订单" : "异常关闭", { inputPattern: /.+/, inputErrorMessage: "请填写原因" });
    if (kind === "cancel") await lgCancelOrder(detail.value.id, value);
    else await lgExceptionClose(detail.value.id, value);
    ElMessage.success("已处理");
    await refresh();
  } catch {
    /* cancelled or toasted */
  }
}

async function complete() {
  if (!detail.value) return;
  await lgCompleteOrder(detail.value.id);
  ElMessage.success("已完成");
  await refresh();
}

async function addRemark() {
  if (!detail.value || !remarkText.value.trim()) return;
  await lgAddRemark(detail.value.id, remarkText.value.trim());
  remarkText.value = "";
  await refresh();
}
</script>

<template>
  <div>
    <div class="bar">
      <el-select v-model="status" placeholder="全部状态" clearable style="width: 160px" @change="page = 1; load()">
        <el-option v-for="s in ORDER_STATUSES" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
    </div>

    <el-table v-loading="loading" :data="rows" stripe @row-click="(r: LgOrder) => open(r.id)">
      <el-table-column prop="id" label="#" width="70" />
      <el-table-column label="线路">
        <template #default="{ row }">{{ row.origin_town }} → {{ row.dest_town }}</template>
      </el-table-column>
      <el-table-column label="货物">
        <template #default="{ row }">{{ row.cargo_name }} · {{ row.weight_kg }}kg · {{ row.volume_m3 }}m³</template>
      </el-table-column>
      <el-table-column label="运费" width="110">
        <template #default="{ row }">{{ row.freight_ghs != null ? "GHS " + row.freight_ghs : "—" }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusMeta(ORDER_STATUSES, row.status).tag">{{ statusMeta(ORDER_STATUSES, row.status).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" />
    </el-table>

    <el-pagination
      class="pager" layout="prev, pager, next" :total="total" :page-size="20"
      :current-page="page" @current-change="(p: number) => { page = p; load(); }"
    />

    <el-drawer v-model="drawer" :title="detail ? `订单 #${detail.id}` : ''" size="480px">
      <template v-if="detail">
        <el-tag :type="statusMeta(ORDER_STATUSES, detail.status).tag" class="st">{{ statusMeta(ORDER_STATUSES, detail.status).label }}</el-tag>

        <el-descriptions :column="1" border size="small" class="sec">
          <el-descriptions-item label="线路">{{ detail.origin_town }} → {{ detail.dest_town }}（{{ detail.depart_date }} {{ detail.depart_time }}）</el-descriptions-item>
          <el-descriptions-item label="货物">{{ detail.cargo_name }} · {{ detail.pieces }}件 · {{ detail.weight_kg }}kg · {{ detail.volume_m3 }}m³</el-descriptions-item>
          <el-descriptions-item label="取送">{{ detail.pickup_town }} → {{ detail.delivery_town }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.shipper" label="货主">{{ detail.shipper.contact_name }} · {{ detail.shipper.contact_phone }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.driver" label="司机">{{ detail.driver.full_name }} · {{ detail.driver.plate_number }} · {{ detail.driver.phone }}</el-descriptions-item>
          <el-descriptions-item label="拒单次数">{{ detail.reject_count }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="detail.status === 'submitted' || detail.status === 'price_confirmed'" class="sec">
          <h4>确认价格</h4>
          <el-form label-width="90px">
            <el-form-item label="运费(GHS)"><el-input-number v-model="price.freight_ghs" :min="0" :step="10" /></el-form-item>
            <el-form-item label="取货时间"><el-input v-model="price.pickup_time" placeholder="如 周六 08:00" /></el-form-item>
            <el-form-item label="佣金覆盖"><el-input-number v-model="price.commission_ghs" :min="0" :step="5" placeholder="留空自动按比例" /></el-form-item>
            <el-form-item v-if="price.commission_ghs != null" label="覆盖原因"><el-input v-model="price.override_reason" /></el-form-item>
            <el-form-item>
              <el-button type="primary" @click="confirmPrice">确认价格</el-button>
              <el-button v-if="detail.status === 'submitted'" @click="reassign">改派</el-button>
            </el-form-item>
          </el-form>
        </div>

        <div class="sec actions">
          <el-button v-if="detail.status === 'delivered'" type="success" @click="complete">完成</el-button>
          <el-button v-if="!['completed','cancelled','exception_closed'].includes(detail.status)" @click="closeOrder('cancel')">取消</el-button>
          <el-button v-if="!['completed','cancelled','exception_closed'].includes(detail.status)" type="danger" @click="closeOrder('exception')">异常关闭</el-button>
        </div>

        <div class="sec">
          <h4>客服备注</h4>
          <div v-for="(r, i) in detail.remarks" :key="i" class="remark">
            <span class="who">{{ r.author }}</span>
            <span class="txt">{{ r.body }}</span>
          </div>
          <div class="remark-add">
            <el-input v-model="remarkText" placeholder="添加备注" @keyup.enter="addRemark" />
            <el-button @click="addRemark">添加</el-button>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.bar { margin-bottom: 12px; }
.pager { margin-top: 12px; justify-content: flex-end; }
.st { margin-bottom: 12px; }
.sec { margin-bottom: 18px; }
.sec h4 { margin: 0 0 8px; font-size: 13px; color: #303133; }
.actions { display: flex; gap: 8px; }
.remark { display: flex; gap: 8px; font-size: 13px; padding: 4px 0; }
.remark .who { color: #1d9e75; font-weight: 500; }
.remark-add { display: flex; gap: 8px; margin-top: 8px; }
</style>
```

- [ ] **Step 2: Verify typecheck**

Run: `npx vue-tsc --noEmit` → exit 0

- [ ] **Step 3: Commit**

```bash
git add admin/src/views/lg/LgOrdersView.vue
git commit -m "feat(admin): CS order workspace"
```

---

### Task 12: Commissions view

**Files:**
- Replace: `admin/src/views/lg/LgCommissionsView.vue`

- [ ] **Step 1: Implement**

Replace `admin/src/views/lg/LgCommissionsView.vue`:

```vue
<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { onMounted, reactive, ref } from "vue";

import { lgCommissions, lgSettleCommission, lgWaiveCommission } from "../../api/endpoints";
import { COMMISSION_STATUSES, statusMeta, type LgCommission } from "../../api/types";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();
const rows = ref<LgCommission[]>([]);
const total = ref(0);
const page = ref(1);
const status = ref("pending");
const loading = ref(false);

const dialog = ref(false);
const current = ref<LgCommission | null>(null);
const form = reactive({ method: "momo", reference: "" });

async function load() {
  loading.value = true;
  try {
    const data = await lgCommissions({ status: status.value || undefined, page: page.value, page_size: 20 });
    rows.value = data.items;
    total.value = data.total;
  } catch {
    /* toasted */
  } finally {
    loading.value = false;
  }
}
onMounted(load);

function openSettle(c: LgCommission) {
  current.value = c;
  form.method = "momo";
  form.reference = "";
  dialog.value = true;
}

async function settle() {
  if (!current.value) return;
  try {
    await lgSettleCommission(current.value.id, form.method, form.reference);
    ElMessage.success("已结算");
    dialog.value = false;
    await load();
  } catch {
    /* toasted */
  }
}

async function waive(c: LgCommission) {
  try {
    const { value } = await ElMessageBox.prompt("豁免原因", "豁免佣金", { inputPattern: /.+/, inputErrorMessage: "请填写原因" });
    await lgWaiveCommission(c.id, value);
    ElMessage.success("已豁免");
    await load();
  } catch {
    /* cancelled or toasted */
  }
}
</script>

<template>
  <div>
    <div class="bar">
      <el-select v-model="status" placeholder="全部状态" clearable style="width: 160px" @change="page = 1; load()">
        <el-option v-for="s in COMMISSION_STATUSES" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
    </div>

    <el-table v-loading="loading" :data="rows" stripe>
      <el-table-column prop="order_id" label="订单#" width="80" />
      <el-table-column prop="driver_id" label="司机#" width="80" />
      <el-table-column label="运费" width="110"><template #default="{ row }">GHS {{ row.freight_ghs }}</template></el-table-column>
      <el-table-column label="费率" width="90"><template #default="{ row }">{{ (row.rate * 100).toFixed(0) }}%</template></el-table-column>
      <el-table-column label="佣金" width="110"><template #default="{ row }">GHS {{ row.amount_ghs }}</template></el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusMeta(COMMISSION_STATUSES, row.status).tag">{{ statusMeta(COMMISSION_STATUSES, row.status).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="结算方式" width="140">
        <template #default="{ row }">{{ row.method ? row.method + " · " + row.reference : "—" }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending'" link type="primary" @click="openSettle(row)">结算</el-button>
          <el-button v-if="auth.can(['admin']) && row.status === 'pending'" link type="info" @click="waive(row)">豁免</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager" layout="prev, pager, next" :total="total" :page-size="20"
      :current-page="page" @current-change="(p: number) => { page = p; load(); }"
    />

    <el-dialog v-model="dialog" title="结算佣金" width="420px">
      <el-form label-width="90px">
        <el-form-item label="方式">
          <el-select v-model="form.method">
            <el-option label="MoMo" value="momo" />
            <el-option label="银行" value="bank" />
            <el-option label="现金" value="cash" />
          </el-select>
        </el-form-item>
        <el-form-item label="流水号"><el-input v-model="form.reference" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="settle">确认结算</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.bar { margin-bottom: 12px; }
.pager { margin-top: 12px; justify-content: flex-end; }
</style>
```

- [ ] **Step 2: Verify typecheck**

Run: `npx vue-tsc --noEmit` → exit 0

- [ ] **Step 3: Commit**

```bash
git add admin/src/views/lg/LgCommissionsView.vue
git commit -m "feat(admin): commission ledger with settle/waive"
```

---

### Task 13: Config, Staff, and Blacklist views

**Files:**
- Replace: `admin/src/views/lg/LgConfigView.vue`, `admin/src/views/lg/LgStaffView.vue`, `admin/src/views/lg/LgBlacklistView.vue`

- [ ] **Step 1: Config view**

Replace `admin/src/views/lg/LgConfigView.vue`:

```vue
<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import { lgConfig, lgUpdateConfig } from "../../api/endpoints";

const saving = ref(false);
const maskedKey = ref("");
const form = reactive({
  lg_commission_rate: "0.08",
  lg_payment_instructions: "",
  lg_sms_provider: "mock",
  lg_sms_sender_id: "ZokoDaily",
  lg_sms_api_key: "",
});

const keyPlaceholder = computed(() => (maskedKey.value ? `当前：${maskedKey.value}` : "尚未配置"));

onMounted(async () => {
  const cfg = await lgConfig();
  form.lg_commission_rate = cfg.lg_commission_rate;
  form.lg_payment_instructions = cfg.lg_payment_instructions;
  form.lg_sms_provider = cfg.lg_sms_provider;
  form.lg_sms_sender_id = cfg.lg_sms_sender_id;
  maskedKey.value = cfg.lg_sms_api_key;
  form.lg_sms_api_key = "";
});

async function save() {
  const rate = Number(form.lg_commission_rate);
  if (Number.isNaN(rate) || rate < 0 || rate > 0.5) {
    ElMessage.warning("佣金比例需在 0 到 0.5 之间");
    return;
  }
  saving.value = true;
  try {
    const body: Record<string, string> = {
      lg_commission_rate: form.lg_commission_rate,
      lg_payment_instructions: form.lg_payment_instructions,
      lg_sms_provider: form.lg_sms_provider,
      lg_sms_sender_id: form.lg_sms_sender_id,
    };
    if (form.lg_sms_api_key) body.lg_sms_api_key = form.lg_sms_api_key;
    await lgUpdateConfig(body);
    ElMessage.success("已保存");
    form.lg_sms_api_key = "";
  } catch {
    /* toasted */
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <el-card class="card" header="物流设置">
    <el-form label-width="130px" class="form">
      <el-form-item label="佣金比例">
        <el-input v-model="form.lg_commission_rate" placeholder="0.08" style="width: 160px" />
        <span class="muted">0–0.5，如 0.08 表示 8%</span>
      </el-form-item>
      <el-form-item label="收款说明">
        <el-input v-model="form.lg_payment_instructions" type="textarea" :rows="3" placeholder="展示给司机的 MoMo/银行收款信息" />
      </el-form-item>
      <el-form-item label="短信服务商">
        <el-select v-model="form.lg_sms_provider" style="width: 160px">
          <el-option label="mock（仅记录）" value="mock" />
          <el-option label="Arkesel" value="arkesel" />
        </el-select>
      </el-form-item>
      <el-form-item label="短信签名">
        <el-input v-model="form.lg_sms_sender_id" style="width: 220px" />
      </el-form-item>
      <el-form-item label="短信 API Key">
        <el-input v-model="form.lg_sms_api_key" type="password" show-password :placeholder="keyPlaceholder" />
        <div class="muted">留空则保持现有 Key 不变</div>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<style scoped>
.card { max-width: 640px; }
.muted { color: #93918a; font-size: 12px; margin-left: 8px; }
</style>
```

- [ ] **Step 2: Staff view**

Replace `admin/src/views/lg/LgStaffView.vue`:

```vue
<script setup lang="ts">
import { ElMessage } from "element-plus";
import { onMounted, reactive, ref } from "vue";

import { lgCreateStaff, lgStaff } from "../../api/endpoints";
import type { Staff } from "../../api/types";

const rows = ref<Staff[]>([]);
const loading = ref(false);
const dialog = ref(false);
const form = reactive({ username: "", password: "", role: "cs" });

const ROLE_LABEL: Record<string, string> = { admin: "管理员", auditor: "审核员", cs: "客服" };

async function load() {
  loading.value = true;
  try {
    rows.value = await lgStaff();
  } catch {
    /* toasted */
  } finally {
    loading.value = false;
  }
}
onMounted(load);

function openCreate() {
  form.username = "";
  form.password = "";
  form.role = "cs";
  dialog.value = true;
}

async function create() {
  if (!form.username.trim() || form.password.length < 6) {
    ElMessage.warning("用户名必填，密码至少 6 位");
    return;
  }
  try {
    await lgCreateStaff({ username: form.username.trim(), password: form.password, role: form.role });
    ElMessage.success("已创建");
    dialog.value = false;
    await load();
  } catch {
    /* toasted (incl. 409 duplicate) */
  }
}
</script>

<template>
  <div>
    <div class="bar"><el-button type="primary" @click="openCreate">新增员工</el-button></div>

    <el-table v-loading="loading" :data="rows" stripe>
      <el-table-column prop="id" label="#" width="70" />
      <el-table-column prop="username" label="用户名" />
      <el-table-column label="角色" width="140">
        <template #default="{ row }">{{ ROLE_LABEL[row.role] ?? row.role }}</template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" title="新增员工" width="420px">
      <el-form label-width="80px">
        <el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="form.password" type="password" show-password /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role">
            <el-option label="管理员" value="admin" />
            <el-option label="审核员" value="auditor" />
            <el-option label="客服" value="cs" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="create">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.bar { margin-bottom: 12px; }
</style>
```

- [ ] **Step 3: Blacklist view**

Replace `admin/src/views/lg/LgBlacklistView.vue`:

```vue
<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { onMounted, reactive, ref } from "vue";

import { lgAddBlacklist, lgBlacklist, lgDeleteBlacklist } from "../../api/endpoints";
import type { BlacklistEntry } from "../../api/types";

const rows = ref<BlacklistEntry[]>([]);
const loading = ref(false);
const dialog = ref(false);
const form = reactive({ value_type: "phone", value: "", reason: "" });

const TYPE_LABEL: Record<string, string> = { phone: "手机号", ghana_card: "Ghana Card", plate: "车牌" };

async function load() {
  loading.value = true;
  try {
    rows.value = await lgBlacklist();
  } catch {
    /* toasted */
  } finally {
    loading.value = false;
  }
}
onMounted(load);

function openCreate() {
  form.value_type = "phone";
  form.value = "";
  form.reason = "";
  dialog.value = true;
}

async function create() {
  if (!form.value.trim()) {
    ElMessage.warning("请填写值");
    return;
  }
  try {
    await lgAddBlacklist({ value_type: form.value_type, value: form.value.trim(), reason: form.reason });
    ElMessage.success("已加入黑名单");
    dialog.value = false;
    await load();
  } catch {
    /* toasted */
  }
}

async function remove(e: BlacklistEntry) {
  try {
    await ElMessageBox.confirm(`确认移除 ${e.value}？`, "移除黑名单", { type: "warning" });
    await lgDeleteBlacklist(e.id);
    ElMessage.success("已移除");
    await load();
  } catch {
    /* cancelled or toasted */
  }
}
</script>

<template>
  <div>
    <div class="bar"><el-button type="primary" @click="openCreate">新增</el-button></div>

    <el-table v-loading="loading" :data="rows" stripe>
      <el-table-column label="类型" width="140">
        <template #default="{ row }">{{ TYPE_LABEL[row.value_type] ?? row.value_type }}</template>
      </el-table-column>
      <el-table-column prop="value" label="值" />
      <el-table-column prop="reason" label="原因" />
      <el-table-column prop="created_by" label="操作人" width="120" />
      <el-table-column label="操作" width="90">
        <template #default="{ row }">
          <el-button link type="danger" @click="remove(row)">移除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" title="新增黑名单" width="420px">
      <el-form label-width="80px">
        <el-form-item label="类型">
          <el-select v-model="form.value_type">
            <el-option label="手机号" value="phone" />
            <el-option label="Ghana Card" value="ghana_card" />
            <el-option label="车牌" value="plate" />
          </el-select>
        </el-form-item>
        <el-form-item label="值"><el-input v-model="form.value" /></el-form-item>
        <el-form-item label="原因"><el-input v-model="form.reason" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="create">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.bar { margin-bottom: 12px; }
</style>
```

- [ ] **Step 4: Verify typecheck**

Run: `npx vue-tsc --noEmit` → exit 0

- [ ] **Step 5: Commit**

```bash
git add admin/src/views/lg/LgConfigView.vue admin/src/views/lg/LgStaffView.vue admin/src/views/lg/LgBlacklistView.vue
git commit -m "feat(admin): logistics config, staff, and blacklist views"
```

---

### Task 14: Build + live admin-journey smoke test

**Files:** none (verification only)

- [ ] **Step 1: Type-check and build the admin app**

Run (from `admin/`): `npm run build`
Expected: `vue-tsc --noEmit` passes and `vite build` succeeds (each `Lg*View` emits a chunk).

- [ ] **Step 2: Boot backend + admin dev server with seeded data**

```bash
# backend (from backend/)
rm -f verify.db && DATABASE_URL="sqlite:///./verify.db" uv run python -m app.seed
DATABASE_URL="sqlite:///./verify.db" SCHEDULER_ENABLED=false UPLOAD_DIR=uploads_e2e uv run uvicorn app.main:app --port 8000 &
# admin (from admin/) — vite serves under /admin/
npm run dev &
```

Seed an approved-driver graph + a submitted order (reuse the helper from the Plan 4 smoke test,
which inserts driver/vehicle/route/trip + a shipper order), so the review queues and order
workspace have data. Also create an `auditor` and a `cs` staff account via the API:

```bash
TOKEN=$(curl -s localhost:8000/api/admin/auth/login -H 'content-type: application/json' -d '{"username":"admin","password":"admin123"}' | sed -E 's/.*"access_token":"([^"]+)".*/\1/')
for r in auditor cs; do curl -s localhost:8000/api/admin/lg/staff -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d "{\"username\":\"$r\",\"password\":\"pw123456\",\"role\":\"$r\"}" >/dev/null; done
```

- [ ] **Step 3: Drive the admin journey headlessly (Playwright from the backend venv)**

Write `backend/e2e_admin.py` that (mobile viewport not needed — use 1280×800):
1. Log in at `/admin/login` as `admin`/`admin123`; assert the 物流 submenu shows all 9 items.
2. Go to `/admin/lg/drivers?…` via the menu; open the pending driver, click 通过; assert the row
   leaves the pending queue (reload → approved).
3. Approve the pending vehicle and route the same way.
4. Go to 订单工作台; open the submitted order; confirm price (freight 500, pickup "Sat 08:00");
   assert status becomes 已确认价格 and commission is implied. Advance the order to delivered via
   the API (driver accept/depart/deliver using the driver's H5 token, or direct status writes),
   then click 完成; assert 已完成.
5. Go to 佣金结算; settle the pending commission (momo + ref); assert 已结算.
6. Go to 物流看板; assert GMV and settled-commission KPIs are non-zero.
7. Log out; log in as `auditor`; assert the submenu shows only 看板/司机/车辆/线路 and that
   navigating to `/admin/lg/orders` redirects to the dashboard (role guard).
8. Log out; log in as `cs`; assert the submenu shows only 看板/订单工作台/佣金结算.
9. Assert no console errors; screenshot the dashboard and the order workspace.

Run: `DATABASE_URL="sqlite:///./verify.db" uv run python e2e_admin.py`
Expected: all checks PASS.

- [ ] **Step 4: Clean up**

Stop both servers; remove `backend/e2e_admin.py`, `verify.db`, `uploads_e2e`, and `admin/dist`.

- [ ] **Step 5: Commit (if any doc/config changed) and finish**

No source changes in this task. Record the smoke-run result in the PR description.

---

## What this plan deliberately defers

| Deferred item | Where it lands |
| --- | --- |
| docker-compose upload volume, nginx `/admin` wiring, MySQL `role` column migration | LTL Plan 6 (deployment) |
| Trip-picker for order reassignment (list a route's open trips) | V2 (needs a new backend endpoint; V1 enters a trip id) |
| Admin unit-test suite (Vitest + Element Plus) | Separate infra task if desired |
| Bulk actions, CSV export, charts, saved filters | V2 polish |

## Self-review notes for the executor

- **Role gating is UX, not security.** Menu/button visibility uses `auth.role`; the backend
  `require_roles` is the real gate (403 backstop, surfaced by `handleApiError`).
- **AuthImage uses a raw `axios` call** to `/api/lg/uploads/{id}` with the admin bearer — not the
  `api` instance (whose base is `/api/admin`). Verified in Task 6 that admin tokens are accepted.
- **Order detail `remarks` is an array** (`CsRemark[]`), distinct from the list row's cargo
  `remarks` string — the list `LgOrder` omits `remarks`; the detail `LgOrderDetail` adds it.
- **`handleApiError` already toasts** 401/409/422; view `catch` blocks intentionally do nothing
  so errors aren't double-reported.
