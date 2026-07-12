# LTL Plan 5: Admin Frontend (Logistics) — Design Spec

Status: Draft for review
Date: 2026-07-12
Parent product: ZokoDaily LTL Logistics module
Depends on: LTL Plans 1–2 (backend admin API), the existing news admin SPA
Precedes: LTL Plan 6 (deployment)

---

## 1. Overview

This spec defines the **staff-facing admin UI** for the logistics module: the screens platform
administrators, auditors, and customer-service agents use to review drivers/vehicles/routes,
work orders through their lifecycle, settle commissions, configure the module, manage staff and
the blacklist, and see operational statistics.

Every backend endpoint already exists under `/api/admin/lg/*` and is covered by the 177 passing
backend tests (Plans 1–2). The admin SPA already exists for the news module (Vue 3 + Vite +
Pinia + vue-router + **Element Plus**, Chinese UI, served under `/admin/`). Plan 5 adds a new
**物流 (Logistics)** section to that SPA plus one small backend change so the UI can gate
navigation by staff role.

### 1.1 Goals

1. Staff can run the entire logistics back office from the admin SPA — no more raw API calls.
2. Navigation and actions are scoped to the signed-in staff member's role (admin/auditor/cs).
3. The UI follows the existing admin conventions (Element Plus components, Chinese labels, the
   shared `api` client and `handleApiError` interceptor) so it feels like one product.

### 1.2 Non-goals (deferred)

- Any H5 change — the driver/shipper apps are Plans 3–4 (done).
- A trip-picker for order reassignment (needs a new backend endpoint; V1 enters a trip id).
- Bulk actions, CSV export, saved filters, charts library — V2 polish.
- Bilingual admin — the admin stays Chinese; no i18n framework is introduced.
- Online payment / payout — commissions remain offline; the UI records settlement only.

### 1.3 Success criteria

- An admin can: review and approve a pending driver, approve its vehicle and route, then watch a
  submitted order move through confirm-price → (driver accepts/delivers) → complete, and settle
  the resulting commission — all from the SPA.
- An auditor sees only the dashboard and review queues; a CS agent sees only the dashboard, order
  workspace, and commissions; each is blocked (menu hidden + 403 backstop) from the rest.
- `vue-tsc --noEmit` and `npm run build` stay green for the admin app; the news screens are
  unchanged.

---

## 2. The one backend change

`GET /api/admin/auth/me` currently returns `{"username"}` only. Extend it to also return the
staff member's role so the SPA can gate navigation:

```
GET /api/admin/auth/me  →  {"username": "...", "role": "admin" | "auditor" | "cs"}
```

Implementation: the endpoint already has the username via `get_current_admin`; look up the
`AdminUser` and include `role` (the column added in Plan 1). This is the only backend edit in
Plan 5 and gets its own backend test (`tests/test_auth.py` extension: `me` returns the role).

No other backend changes: all logistics admin endpoints exist and enforce `require_roles`
already, so the SPA's role gating is a UX layer over an enforced backend.

---

## 3. Relationship to existing admin code

Plan 5 **extends** these files (no rewrites):

| File | Extension |
| --- | --- |
| `admin/src/api/types.ts` | + logistics types (Driver, Vehicle, Route, Order, Commission, StatsOverview, Staff, Blacklist, LgConfig, Paginated is reused) |
| `admin/src/api/endpoints.ts` | + `lg*` functions for every `/lg/*` endpoint + `me()` |
| `admin/src/stores/auth.ts` | + `role`; `login()` then calls `me()` to store role; persisted |
| `admin/src/layout/AdminLayout.vue` | + a 物流 `el-sub-menu` group with role-filtered items |
| `admin/src/router.ts` | + `/lg/*` child routes with `meta.roles` + a role guard |

New views live under `admin/src/views/lg/`. Reused as-is: the `api` axios instance (bearer +
`handleApiError` for 401/409/422), `AdminLayout` shell, Element Plus registration, `LoginView`.

---

## 4. Navigation, routing, and role gating

### 4.1 Sidebar

Add a collapsible **物流** (`el-sub-menu`) group beneath the existing flat news items. Its
child items are filtered by the signed-in role:

| Menu item (zh) | Route | Roles |
| --- | --- | --- |
| 物流看板 (Dashboard) | `/lg/dashboard` | admin, auditor, cs |
| 司机审核 (Driver review) | `/lg/drivers` | admin, auditor |
| 车辆审核 (Vehicle review) | `/lg/vehicles` | admin, auditor |
| 线路审核 (Route review) | `/lg/routes` | admin, auditor |
| 订单工作台 (Order workspace) | `/lg/orders` | admin, cs |
| 佣金结算 (Commissions) | `/lg/commissions` | admin, cs |
| 物流设置 (Config) | `/lg/config` | admin |
| 员工管理 (Staff) | `/lg/staff` | admin |
| 黑名单 (Blacklist) | `/lg/blacklist` | admin |

The group renders only items whose `roles` include `auth.role`; the whole group hides if none
match (shouldn't happen — all roles get the dashboard).

### 4.2 Routes and guard

All logistics routes are children of `AdminLayout` (like the news routes) and carry
`meta.roles: string[]`. The existing `router.beforeEach` login guard gains a role check: if a
route has `meta.roles` and `auth.role` is not in it, redirect to `/lg/dashboard` (or `/articles`
if the role somehow lacks dashboard). This prevents deep-link bypass of the hidden menu.

### 4.3 Auth store

`useAuthStore` gains `role: string` (persisted under a new localStorage key). `login()` stores
the token, then calls `me()` and stores `username` + `role`. On app load the store hydrates
`role` from localStorage; a stale token is caught by the existing 401 handler. `logout()` clears
role too.

---

## 5. Screen designs

All screens use Element Plus: `el-table` for lists, `el-tag` for statuses, `el-dialog` for
review/settlement/edit forms, `el-form` for inputs, `el-pagination` for paging, `ElMessage`/
`ElMessageBox` for feedback and confirmations. Each is a focused view under `views/lg/`.

### 5.1 Dashboard — `LgDashboardView` (`/lg/dashboard`)

- Calls `GET /lg/stats/overview` (optional date range via two `el-date-picker`s).
- KPI cards: drivers by status, vehicles, active routes, upcoming trips, orders by status,
  GMV (GHS), commission pending/settled, completion & cancellation rates, capacity utilization.
- A "top lanes" table (lane → order count).
- Read-only; the landing page for every role after login.

### 5.2 Driver review — `LgDriversView` (`/lg/drivers`)

- `el-table` from `GET /lg/drivers?status=&page=` with a status filter (`el-select`) and
  pagination; columns: name, phone, Ghana Card, licence class/expiry, status tag.
- Row click / "审核" opens an `el-dialog` showing full profile + document images (loaded as
  authenticated blobs — see §6.1) with **通过 / 驳回**
  (`POST /drivers/{id}/review {action, reason}`; reject requires a reason).
- For approved drivers, admin-only **冻结 / 解冻** (`/freeze {reason}`, `/unfreeze`). The
  freeze/unfreeze buttons render only when `auth.role === "admin"` (backend is admin-only).

### 5.3 Vehicle review — `LgVehiclesView` (`/lg/vehicles`)

- `el-table` from `GET /lg/vehicles?status=&page=`; columns: plate, type, brand/model, status.
- Review dialog with the five vehicle photos + three documents (image thumbnails) and
  **通过 / 驳回** (`POST /vehicles/{id}/review`). Reject requires a reason.

### 5.4 Route review — `LgRoutesView` (`/lg/routes`)

- `el-table` from `GET /lg/routes?status=&page=`; columns: origin→dest, frequency, pricing,
  status. Review dialog with route details + **通过 / 驳回** (`POST /routes/{id}/review`).
- Admin-only **暂停 / 恢复** for approved/suspended routes (`/suspend {reason}`, `/resume`).

### 5.5 Order workspace — `LgOrdersView` (`/lg/orders`)

The richest screen (admin + cs). Default view is the **待处理 (submitted)** queue with a
first-contact emphasis; a status filter switches queues.

- `el-table` from `GET /lg/orders?status=&page=`; columns: id, lane, cargo summary, status,
  freight, created time.
- Row opens an `el-drawer`/`el-dialog` detail (`GET /lg/orders/{id}`) showing cargo, trip,
  shipper + driver contacts (staff see both, unmasked), CS remarks timeline, reject count.
- Actions, each gated to the order's current status and shown as buttons in the detail:
  - **确认价格** (`confirm-price {freight_ghs, pickup_time, commission_ghs?, override_reason?}`)
    — an `el-form`; commission auto-computes from the configured rate unless overridden (an
    override requires a reason). Blocked with the backend's 409 shortfall message if capacity is
    insufficient (surfaced via `handleApiError`).
  - **改派** (`reassign {trip_id}`) — a small form where CS enters the target trip id (see the
    flagged gap in §1.2); only for submitted orders.
  - **取消 / 异常关闭** (`cancel {reason}` / `exception-close {reason}`) — reason required.
  - **完成** (`complete`) — only for delivered orders; creates the commission record.
  - **添加备注** (`remarks {body}`) — appends to the CS timeline.
- After any action, refetch the order and the list so status/tags update.

### 5.6 Commissions — `LgCommissionsView` (`/lg/commissions`)

- `el-table` from `GET /lg/commissions?status=&driver_id=&page=`; columns: order, driver,
  freight, rate, amount, status, settlement method/reference.
- **结算** (`settle {method, reference}`) via a dialog (`el-select` method: momo/bank/cash + a
  reference field) — admin + cs. Admin-only **豁免** (`waive {reason}`).

### 5.7 Config — `LgConfigView` (`/lg/config`, admin only)

- `GET /lg/config` → an `el-form` for commission rate (validated 0–0.5), payment instructions
  (textarea shown to drivers), SMS provider (mock/arkesel), sender id, and API key (masked;
  written only if changed). `PUT /lg/config` on save. Models the existing `SettingsView`.

### 5.8 Staff — `LgStaffView` (`/lg/staff`, admin only)

- `el-table` from `GET /lg/staff`; **新增员工** dialog (`POST /lg/staff {username, password,
  role}`) with a role `el-select` (admin/auditor/cs).

### 5.9 Blacklist — `LgBlacklistView` (`/lg/blacklist`, admin only)

- `el-table` from `GET /lg/blacklist`; **新增** dialog (`POST {value_type, value, reason}`),
  per-row **删除** (`DELETE /lg/blacklist/{id}`, `ElMessageBox` confirm).

---

## 6. Components and files

New views (`admin/src/views/lg/`): `LgDashboardView`, `LgDriversView`, `LgVehiclesView`,
`LgRoutesView`, `LgOrdersView`, `LgCommissionsView`, `LgConfigView`, `LgStaffView`,
`LgBlacklistView`.

### 6.1 Authenticated attachment images — `AuthImage.vue`

The `/api/lg/uploads/{id}` endpoint is auth-gated, so a plain `<img src="/api/lg/uploads/{id}">`
would fail: the browser cannot attach the admin bearer token to an `<img>` request. A small
`AuthImage.vue` component solves this once for every review dialog: it fetches the attachment
through the shared `api` client (which adds the bearer), receives it as a `blob`
(`responseType: "blob"`), and renders it via `URL.createObjectURL`, revoking the object URL on
unmount. All document/photo thumbnails in the driver, vehicle, and route review dialogs use it.

Note: the admin session uses the `/api/admin` JWT; the uploads endpoint's `get_principal`
accepts admin tokens, so this works without a new backend route — **verify this early** (§10).

### 6.2 Shared review dialog

Optional shared component (`admin/src/components/`): `ReviewDialog.vue` — a reusable
approve/reject dialog (an `AuthImage` gallery + reason + pass/reject) used by the driver,
vehicle, and route queues, since those three share the same review interaction. The plan may
inline if the three diverge; extracting keeps each queue view small.

Files that grow: `api/types.ts`, `api/endpoints.ts`, `stores/auth.ts`, `layout/AdminLayout.vue`,
`router.ts`, and (backend) `api/admin/auth.py`.

---

## 7. Data flow and API additions

New `endpoints.ts` functions (over the existing `api` instance, `/api/admin` base):

```
me(): GET /auth/me → { username, role }
lgStats(range?): GET /lg/stats/overview → StatsOverview
lgDrivers(params) / lgReviewDriver(id, action, reason) / lgFreezeDriver(id, reason) / lgUnfreezeDriver(id)
lgVehicles(params) / lgReviewVehicle(id, action, reason)
lgRoutes(params) / lgReviewRoute(id, action, reason) / lgSuspendRoute(id, reason) / lgResumeRoute(id)
lgOrders(params) / lgOrder(id) / lgConfirmPrice(id, body) / lgReassign(id, tripId)
  / lgCancelOrder(id, reason) / lgExceptionClose(id, reason) / lgCompleteOrder(id) / lgAddRemark(id, body)
lgCommissions(params) / lgSettleCommission(id, method, reference) / lgWaiveCommission(id, reason)
lgConfig() / lgUpdateConfig(body)
lgStaff() / lgCreateStaff(body)
lgBlacklist() / lgAddBlacklist(body) / lgDeleteBlacklist(id)
```

`types.ts` gains interfaces mirroring the backend response shapes (`LgDriver`, `LgVehicle`,
`LgRoute`, `LgOrder`, `LgCommission`, `StatsOverview`, `Staff`, `BlacklistEntry`, `LgConfig`);
list endpoints reuse the existing `Paginated<T>`.

---

## 8. Error handling and states

- The shared `handleApiError` interceptor already turns 401 → re-login, 409/422 →
  `ElMessage.warning(detail)`, other → generic error. Logistics screens rely on it; the 409
  capacity-shortfall and reason-required messages surface automatically.
- Loading: Element Plus `v-loading` on tables/dialogs during fetches.
- Empty: `el-table` empty text per screen.
- Confirmations: destructive/irreversible actions (reject, cancel, exception-close, waive,
  blacklist delete) use `ElMessageBox.confirm` before firing.
- Role backstop: even though menus/buttons are role-filtered, a 403 from a deep-linked action is
  caught and shown; the router guard prevents most deep-link access.

---

## 9. Testing strategy

The admin SPA has **no unit test suite today** (unlike the H5 app). Introducing Vitest +
component tests for a large Element Plus surface is high-effort and out of proportion for this
plan; instead verification mirrors how the backend and admin were validated before:

- **Backend test** for the one backend change: `me` returns the role (added to
  `backend/tests/test_auth.py`), run in the backend suite.
- **Type + build gate**: `vue-tsc --noEmit` and `npm run build` for the admin app stay green.
- **Live admin-journey smoke run** (headless Playwright from the backend venv, as used for
  Plans 1–4): against a seeded backend, log in as `admin`, walk a pending driver through
  approve, approve its vehicle and route, confirm-price a seeded submitted order, (advance the
  order via API to delivered), complete it, settle the commission, and read the dashboard KPIs;
  then log in as an `auditor` and a `cs` account and assert the sidebar shows only their allowed
  menus and a deep link to a forbidden route redirects. Assert no console errors; screenshot the
  dashboard and order workspace.

If the team later wants admin unit tests, that is a separate infra task; this plan does not
block on it.

---

## 10. Risks and mitigations

- **Role source of truth**: the SPA gates by `auth.role`, but the backend `require_roles` is the
  real enforcement — the UI never grants access the API would deny, so a stale/edited role only
  affects menu visibility, not security.
- **Reassign without a trip picker**: CS entering a trip id is a stopgap; the risk is a wrong id
  → the backend 409s ("target trip is not open"), which is surfaced. A proper picker is a small
  follow-up endpoint (list a route's open trips) noted for V2.
- **Attachment viewing** (the one integration point to verify early): review dialogs must load
  images as authenticated blobs via `AuthImage` (§6.1), because `<img src>` cannot carry the
  bearer token. The admin session's `/api/admin` JWT must be accepted by the H5 uploads endpoint's
  `get_principal` — it accepts admin tokens (Plan 1), so no new route is expected; the plan's
  first attachment-related task verifies an admin can actually GET `/api/lg/uploads/{id}` and, if
  not, adds an `/api/admin/lg/uploads/{id}` proxy route before building the review dialogs.
- **SPA size**: nine new views. Keeping each view focused (and extracting `ReviewDialog`) keeps
  files small and reviewable.

---

## 11. Out of scope (recap)

Deployment/nginx/upload-volume + the MySQL `role` migration (Plan 6), trip-picker for reassign,
bulk actions/export, admin i18n, online payment/payout, and any H5 change. The manual
capacity-adjust and one-off-trip driver features live in the H5 (Plan 4), not here.
