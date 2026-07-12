# ZokoDaily LTL Logistics — Enterprise QA & Security Assessment

**Report date:** 2026-07-12
**Assessor:** Senior QA / Test Architect / Security Engineer (combined roles)
**Software under test:** ZokoDaily — Logistics ("物流") module (LTL freight-matching add-on to the news aggregation platform)
**Version / branch:** `ltl-plan-5` (backend Plans 1–2, H5 shipper Plan 3, H5 driver Plan 4, admin Plan 5; deployment Plan 6 planned, not yet implemented)

---

## 1. Software information

| Field | Value |
|---|---|
| Software name | ZokoDaily Logistics module |
| Software type | Web platform — mobile H5 (shipper + driver), admin SPA, REST backend |
| Backend | FastAPI (Python 3.12), SQLAlchemy 2.0 (sync), Pydantic v2, PyJWT, bcrypt, APScheduler, Crawl4AI/Playwright |
| H5 frontend | Vue 3 + `<script setup>` + TypeScript, Vant, Pinia, vue-router, vue-i18n, axios |
| Admin frontend | Vue 3 + TypeScript, Element Plus, Pinia, vue-router, axios |
| Database | MySQL 8 in production; SQLite in the automated test suite |
| Deployment | Docker Compose: mysql + single backend replica + nginx (builds both SPAs, reverse-proxies `/api`) |
| Operating platform | Linux containers; H5 targets mobile browsers; admin targets desktop |
| Application URL | Not deployed to a public URL during assessment (local docker/dev only) |
| Test / admin account | Seeded default `admin` / `admin123`; H5 users via phone+OTP |
| API docs | FastAPI OpenAPI (`/docs`) + the design specs/plans under `docs/superpowers/` |
| Source code | Provided (full repository) |

### 1.1 Assessment basis

- **White-box static review** of the complete source tree.
- **Automated suites executed:** 178 backend pytest cases, 110 H5 Vitest cases — all passing.
- **Live end-to-end runs executed this session (headless):** backend API (46 checks), H5 shipper journey (14 checks), H5 driver journey (12 checks), admin journey (12 checks) — all passing.
- **NOT dynamically exercised (see §9 for what is needed):** real load/concurrency (100–10,000 users), cross-browser matrix, mobile device matrix, automated accessibility audit, TLS/production edge configuration (not present in repo), and live-instance penetration testing.

---

## 2. Executive summary

The **functional core is strong and genuinely well-tested.** Static review found no SQL-injection surface, no mass-assignment, and consistently enforced server-side authorization; the live E2E runs passed end to end across all four surfaces. Test discipline is above average for a project this size.

However, there is a **cluster of authentication, secrets, and transport-security weaknesses** that, while individually inexpensive to fix, collectively **block a clean production launch.** None are exotic; all are located with file/line evidence in §5.

**Overall deployment risk: HIGH** until the five HIGH findings (H-1…H-5) are remediated; **Medium** thereafter.

### 2.1 Quality scorecard (0–100)

| Dimension | Score | Basis |
|---|---:|---|
| Functional quality | 88 | Flows verified end-to-end; strong coverage |
| Stability | 82 | Good error handling; concurrency lightly proven (SQLite only) |
| **Security** | **55** | OTP RNG, default creds, rate-limiter bypass, plaintext secrets, no headers/TLS |
| Performance | 70 | No load testing performed; float money; some N+1 potential |
| UI quality | 80 | Clean, consistent; not tested cross-browser/mobile |
| UX quality | 78 | Sensible flows; minor rough edges |
| Maintainability | 85 | Small focused modules, typed, well-documented |
| Scalability | 62 | Single-replica constraint; in-memory rate limiter; local-disk uploads |
| Reliability | 78 | Retrying entrypoint, healthchecks, idempotent seed |
| **Production readiness** | **60** | Blocked by HIGH findings |

**Recommended release gate:** fix H-1 through H-5 (and ideally M-1, M-2, M-4) before any internet-facing deployment.

---

## 3. Findings summary

| ID | Severity | Title | Location |
|---|---|---|---|
| H-1 | High | OTP generated with non-cryptographic RNG | `backend/app/logistics/otp.py:50` |
| H-2 | High | Shipped default admin creds + weak default JWT secret | `backend/app/seed.py`, `backend/app/config.py` |
| H-3 | High | Login rate limiter keys on proxy IP, not client | `backend/app/api/admin/auth.py:38` |
| H-4 | High | OTP/SMS secrets stored in plaintext, never purged | `backend/app/logistics/sms.py:34`, `models.py` |
| H-5 | High | No TLS / no security headers at the edge | `deploy/nginx/nginx.conf` |
| M-1 | Medium | No server-side password policy for staff | `backend/app/logistics/schemas.py` (`StaffIn`) |
| M-2 | Medium | Long-lived, non-revocable JWTs | `backend/app/config.py`, `backend/app/security.py` |
| M-3 | Medium | Unbounded upload storage per user | `backend/app/logistics/storage.py` |
| M-4 | Medium | Money stored as floating point | `backend/app/logistics/models.py` |
| M-5 | Medium | Upload content-type trusted from client | `backend/app/logistics/storage.py` |
| M-6 | Medium | Concurrency/row-lock correctness unproven (SQLite tests) | `backend/app/logistics/capacity.py` |
| L-1 | Low | Order reassignment takes a raw trip id | `backend/app/logistics/api/admin/orders.py` |
| L-2 | Low | Admin Vite dev server unusable (base not stripped) | `admin/` dev config (env-specific) |
| L-3 | Low | Blocked-role redirect lands on news admin | `admin/src/router.ts` |
| L-4 | Low | News `main_image_url` hot-linked from third parties | `h5` article rendering |
| L-5 | Low | No explicit CORS policy | `backend/app/main.py` |

---

## 4. Detailed bug reports — HIGH

### H-1 — OTP generated with a non-cryptographic RNG
- **Severity:** High **Priority:** P1 **Module:** H5 authentication (phone+OTP)
- **Location:** `backend/app/logistics/otp.py:50` — `code = f"{random.randint(0, 999999):06d}"`
- **Reproduction:** Register/log in as any H5 user via `POST /api/lg/auth/request-otp`; the code is produced by Python's `random` module.
- **Expected:** Authentication secrets are generated with a cryptographically secure RNG.
- **Actual:** `random` is a Mersenne-Twister PRNG (deterministic given internal state); it is not suitable for security tokens.
- **Root cause:** Use of `random` instead of `secrets`.
- **Fix:** `import secrets` → `code = f"{secrets.randbelow(1_000_000):06d}"`. Combine with hashing at rest (H-4).
- **Risk:** Predictable OTPs enable driver/shipper account takeover, which is the sole gate on all logistics user actions.

### H-2 — Shipped default admin credentials + weak default JWT secret
- **Severity:** High **Priority:** P1 **Module:** Auth / configuration
- **Location:** `backend/app/seed.py` (`DEFAULT_ADMIN = ("admin", "admin123")`); `backend/app/config.py` (`jwt_secret="change-me-in-production"`, 23 bytes → `InsecureKeyLengthWarning` observed in every test run).
- **Reproduction:** Deploy without overriding `JWT_SECRET` / rotating the admin password; log in with `admin/admin123`; note tokens are signed with a guessable secret shared by admin **and** H5 audiences.
- **Expected:** No usable default credentials; a strong, mandatory signing secret.
- **Actual:** Both are present as insecure defaults; nothing enforces a change.
- **Root cause:** Convenience defaults never gated for production.
- **Fix:** Fail fast on startup if `JWT_SECRET` is the default or < 32 bytes; require an admin password change on first login (or seed a random password printed once).
- **Risk:** Full administrative compromise + token forgery for all users.

### H-3 — Login rate limiter keys on the proxy IP, not the real client
- **Severity:** High **Priority:** P1 **Module:** Admin auth (rate limiting)
- **Location:** `backend/app/api/admin/auth.py:24-39` — `client_ip = request.client.host`.
- **Reproduction:** Behind nginx, `request.client.host` resolves to nginx's network peer, not the browser. All clients collapse into one bucket (`_RATE_MAX_ATTEMPTS = 10 / 60s`).
- **Expected:** Throttle per real client (and ideally per username); one attacker must not affect others.
- **Actual:** (a) per-attacker throttling is bypassed (attempts from many IPs share/rotate against one bucket keyed on the proxy); (b) **DoS** — 10 attempts/minute from anyone 429s *all* admin logins.
- **Root cause:** Client IP not derived from `X-Forwarded-For`; uvicorn not configured with proxy headers.
- **Fix:** Run uvicorn with `--proxy-headers` (+ trusted hosts) or add `ProxyHeadersMiddleware`; parse the client IP from `X-Forwarded-For`; add per-username throttling; use a shared store (Redis) if the backend ever scales beyond one process.
- **Risk:** Admin brute-force feasibility + denial of service.

### H-4 — Secrets stored in plaintext at rest and never purged
- **Severity:** High **Priority:** P1 **Module:** OTP / SMS / data retention
- **Location:** `backend/app/logistics/sms.py:34` (persists full SMS `body`, which for OTP messages contains the live code); `lg_otp_code.code` stores the code in plaintext; neither table is purged.
- **Reproduction:** Trigger any OTP; inspect `lg_sms_log.body` and `lg_otp_code.code` — both contain the code in cleartext, retained indefinitely.
- **Expected:** OTP secrets not written to logs; codes hashed; retention limited.
- **Actual:** Cleartext OTPs accumulate in two tables forever.
- **Root cause:** Logging the raw message body; storing raw codes.
- **Fix:** Log a redacted template + `kind` only (never the code); hash `lg_otp_code.code` (compare hashes in `verify_code`); add a scheduled purge of used/expired OTPs and aged SMS logs.
- **Risk:** Sensitive-data exposure via DB access or backups; conflicts with the PRD's Ghana Data Protection Act claim.

### H-5 — No TLS and no browser security headers at the edge
- **Severity:** High **Priority:** P1 **Module:** Deployment / nginx
- **Location:** `deploy/nginx/nginx.conf` — `listen 80;` only; the only `add_header` directives are `Cache-Control`.
- **Reproduction:** Inspect response headers from the served app — no `Strict-Transport-Security`, `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`; traffic is HTTP.
- **Expected:** HTTPS end-to-end (PRD: "Full HTTPS throughout") + a standard security-header set.
- **Actual:** Plaintext HTTP; clickjacking/MIME-sniffing exposed.
- **Root cause:** Edge hardening not implemented; TLS assumed external but undocumented.
- **Fix:** Terminate TLS (or explicitly document/verify the upstream terminator + force HTTPS redirect); add the security-header set; `SameSite`/`Secure` on any future cookies.
- **Risk:** Token/OTP theft via MITM; clickjacking of the admin console.

---

## 5. Detailed bug reports — MEDIUM

### M-1 — No server-side password policy for staff
- **Module:** Admin staff management. `StaffIn.password: str` has no length/complexity constraint; only the SPA enforces ≥6 chars. The API accepts weak/short passwords.
- **Fix:** Enforce minimum length + complexity in the Pydantic schema; reject common passwords.

### M-2 — Long-lived, non-revocable tokens
- **Module:** Auth. `jwt_expire_minutes=1440` (24h) for both audiences; no refresh flow, no server-side revocation/denylist, no logout invalidation. A deleted admin's token still satisfies `get_current_admin` until expiry; a frozen driver's token still authenticates as an H5 user.
- **Fix:** Shorter access tokens + refresh, or a token-version/denylist checked per request; re-check account status (frozen/deleted) in the auth dependencies.

### M-3 — Unbounded upload storage per user
- **Module:** Uploads. `storage.py` caps each file at 8 MB but sets no per-user count/total-size quota; orphaned attachments (from abandoned forms) are never garbage-collected.
- **Fix:** Per-user quota + a background sweep for unreferenced attachments.

### M-4 — Money stored as floating point
- **Module:** Orders / commissions. `freight_ghs`, `commission_ghs`, `amount_ghs`, `rate` are `Float`. Dashboard GMV/commission totals sum floats, accumulating rounding error.
- **Fix:** Store integer pesewas or `DECIMAL`. (Spec defers to V2, but it is a live data-integrity concern for financial records.)

### M-5 — Upload content-type trusted from the client
- **Module:** Uploads. `storage.py` validates the client-supplied `file.content_type` against an allowlist but never checks magic bytes; a non-image payload can be stored under an image type. Risk is limited (SVG excluded; files served with the declared type), but a defense-in-depth gap.
- **Fix:** Validate/sniff magic bytes or re-encode images server-side.

### M-6 — Concurrency / row-lock correctness unproven
- **Module:** Capacity ledger. `reserve()`/`release()` use `with_for_update()` (`SELECT … FOR UPDATE`), which is a **no-op on SQLite** — the entire suite runs on SQLite, so the overbooking guard's locking is never exercised. Production MySQL behaves correctly, but there is no automated proof under concurrency.
- **Fix:** Add an integration test against MySQL exercising concurrent `confirm-price` on the last capacity slot.

---

## 6. Detailed bug reports — LOW

- **L-1 — Reassignment takes a raw trip id** from CS with minimal validation (no trip-picker); a wrong id returns 409 but is error-prone. (Design-acknowledged; V2 improvement.)
- **L-2 — Admin Vite dev server unusable in this environment:** vue-router does not strip the `/admin/` base under `vite dev` (blank app, "No match" for every route); only the `preview`/production build routes correctly. Dev-experience issue.
- **L-3 — Blocked-role redirect lands logistics staff on the news admin** (`/articles`) rather than `/lg/dashboard` — mildly confusing UX for auditor/cs.
- **L-4 — News `main_image_url` is hot-linked** from third-party source sites via `<img :src>` in the H5, creating availability, mixed-content, and third-party-tracking exposure.
- **L-5 — No explicit CORS policy** in `main.py` (acceptable while strictly same-origin via nginx, but undocumented).

---

## 7. What is working well (verified, not assumed)

- **No SQL-injection surface found.** All queries use the SQLAlchemy ORM with bound parameters; `ilike(f"%{x}%")` binds the entire string as a parameter value; `migrate.py` uses static DDL with no user input.
- **No mass-assignment.** All writes flow through Pydantic schemas; `status`, `id`, and ownership fields cannot be set by clients (`CustomerOrder(shipper_user_id=user.id, **body.model_dump())` where `body` is a constrained schema).
- **Authorization enforced server-side.** Order access (`_visible_order`), attachment ownership (`get_principal` — admin tokens accepted by design, verified), notification ownership, and role gating (`require_roles`) are all backend-enforced. Admin UI role menus are UX over an enforced backend (auditor/cs blocked from forbidden routes — verified in the admin E2E).
- **Business-rule integrity.** Blacklist + Ghana-Card/plate duplicate checks; capacity reserve-on-confirm / release-on-reject (verified 400→200 kg in the Plan 2 E2E); commission snapshot at confirmation; contact disclosure gated to `awaiting_pickup`+; immutable `AuditRecord`; token scope separation (H5 vs admin).
- **Test depth.** 178 backend + 110 frontend tests passing; live E2E for all four surfaces passed this session with zero console/server errors.

---

## 8. Sample generated test cases (high-value subset)

| ID | Module | Type | Preconditions | Steps | Expected | Priority | Auto? |
|---|---|---|---|---|---|---|---|
| SEC-01 | H5 auth | Security | — | Request OTP; attempt to predict/replay the next code | Codes CS-random & single-use | Critical | Yes |
| SEC-02 | Admin auth | Security | Behind nginx | 11 bad logins/min from 2 distinct client IPs (via XFF) | Each IP throttled independently | High | Yes |
| SEC-03 | Uploads | Security | Logged-in user | Upload 200 × 8 MB files | Rejected past a quota; disk safe | High | Yes |
| SEC-04 | Transport | Security | Deployed edge | Curl over HTTP; inspect headers | HSTS/CSP/XFO/XCTO present; HTTP→HTTPS | High | Yes |
| SEC-05 | Data retention | Security/Privacy | OTP issued | Query `lg_otp_code`, `lg_sms_log` | No cleartext codes retained | High | Yes |
| BND-01 | Order form | Boundary | Live trip | weight=0 / negative / 1e12 / emoji cargo | 422, never 500 | High | Yes |
| CON-01 | Capacity | Concurrency | MySQL, near-full trip | 2 simultaneous `confirm-price` on last slot | Exactly one succeeds | High | Yes |
| AUTHZ-01 | Orders | AuthZ | 2 shippers | Shipper A GETs B's order id | 404 | High | Yes |
| AUTHZ-02 | Driver freeze | AuthZ | Approved driver w/ token | Freeze driver; reuse old JWT | Frozen driver cannot act | Medium | Yes |
| DATA-01 | Commission | Data integrity | — | Sum 1,000 commissions of 33.33 | Exact total, no float drift | Medium | Yes |
| API-01 | List endpoints | API | — | page=0 / -1 / page_size=100000 | Sane bounds, no 500/timeout | Medium | Yes |
| FUNC-01 | Order lifecycle | Functional | Delivered order | Complete → settle commission | Commission created & settled | High | Yes (done) |
| RESIL-01 | H5 pull-refresh | Reliability | News list | Pull to refresh repeatedly/offline | No stuck "Loading"; graceful error | Medium | Yes (fixed) |

---

## 9. Coverage gaps — information/environment required

| Area (prompt §) | Blocker | Needed to complete |
|---|---|---|
| Load & concurrency (§11) | No target host/MySQL; SQLite can't prove locking | Staging host + MySQL + permission to run k6/Locust at 100/1k/10k |
| Cross-browser (§13) | Admin dev server broken locally; no deployed URL | Built/deployed URL + BrowserStack (Chrome/Edge/Firefox/Safari) |
| Mobile (§14) | No device lab | Deployed URL + Android/iOS/tablet/foldable matrix |
| Accessibility (§15) | Not assessable from source | Rendered pages + axe/Lighthouse/screen-reader pass |
| TLS/prod infra (§7) | Repo edge terminates on `:80` only | Production nginx/ingress config to verify HTTPS |
| Live pen-test (§7) | Static review only | Authorized staging URL + test accounts |

---

## 10. Remediation roadmap

**Release-blocking (do before any internet-facing deploy):**
1. H-1 — cryptographic OTP (`secrets`).
2. H-2 — enforce strong `JWT_SECRET`; remove/rotate default admin.
3. H-3 — correct client-IP rate limiting (proxy headers + per-username).
4. H-4 — stop persisting OTP secrets; hash codes; add purge job.
5. H-5 — TLS + security headers.

**Fast follow (next sprint):**
6. M-1 server-side password policy · M-2 token lifetime/revocation · M-4 money as integer/decimal.

**Hardening / debt:**
7. M-3 upload quotas + orphan cleanup · M-5 magic-byte validation · M-6 MySQL concurrency test · L-1…L-5.

---

## 11. Final verdict

**Not production-ready as-is.** Functionality and test discipline are strong, but five standard, cheap-to-fix HIGH security issues gate the release. After H-1…H-5 (plus M-1/M-2/M-4), the module moves to **Medium** risk and a defensible launch.

**Overall deployment risk: HIGH** (→ Medium after the blocking fixes).

---

*Prepared from white-box source review plus the automated and live end-to-end runs executed on 2026-07-12. Dynamic load, browser/mobile, accessibility, TLS, and live-instance penetration testing remain outstanding and require the environment/access listed in §9.*
