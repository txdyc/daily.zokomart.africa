# ZokoDaily 物流管理后台（LTL Plan 5）企业级测试报告

## 测试说明

- **测试方法**：静态代码审查（无运行环境，无法进行动态运行时测试）
- **测试范围**：Plan 5 物流管理后台前端（9 个视图 + AuthImage 组件 + 路由 + 认证）及关联后端 API
- **测试日期**：2026-07-13
- **测试版本**：`ltl-plan-5` 分支，commit 2974491
- **测试角色**：QA Lead / 安全工程师 / 性能测试专家 / 产品经理 / UX 设计师

---

## 一、Bug 报告（按严重程度排序）

### BUG-001 ★ Critical — 前端角色守卫可导致无限重定向循环

**文件**：`admin/src/router.ts` L69-L80

**复现步骤**：
1. 用户在 Plan 5 之前已登录（token 存在，但 localStorage 中无 `zoko-admin-role`）
2. 用户刷新页面或直接访问任意 `/lg/*` 路由

**实际结果**：
- `beforeEach` 检查 token 存在（通过）
- 角色守卫读取 `localStorage.getItem("zoko-admin-role")` → `null` → `role = ""`
- `roles.includes("")` → `false` → 重定向到 `lg-dashboard`
- `lg-dashboard` 的 `meta.roles = ["admin", "auditor", "cs"]`，`roles.includes("")` 仍为 `false`
- **无限重定向循环**，浏览器卡死

**预期结果**：应检测 role 为空时跳转到无角色限制的页面

**修复建议**：role 为空或权限不足时回退到 `articles` 页（无角色限制）。

---

### BUG-002 ★ High — 订单取消按钮对 `in_transit` 和 `delivered` 状态错误显示

**文件**：`admin/src/views/lg/LgOrdersView.vue` — `canCancel` computed

**复现步骤**：
1. 打开一个 `in_transit` 或 `delivered` 状态的订单详情
2. 观察"取消"按钮

**实际结果**：`canCancel` 逻辑为 `s && !["completed", "cancelled", "exception_closed"].includes(s)`，对 `in_transit` 和 `delivered` 返回 `true`，显示取消按钮。点击后后端返回 409。

**预期结果**：取消按钮应仅在 `submitted`、`price_confirmed`、`awaiting_pickup` 状态显示

**原因分析**：后端 `ALLOWED` 映射中 `in_transit` 只能转 `delivered` 或 `exception`，`delivered` 只能转 `completed` 或 `exception`，均不允许 `cancelled`。

---

### BUG-003 ★ High — 审核按钮对 `rejected` 状态的司机/车辆/线路错误显示

**文件**：
- `admin/src/views/lg/LgDriversView.vue` — `canReview`
- `admin/src/views/lg/LgVehiclesView.vue` — `canReview`
- `admin/src/views/lg/LgRoutesView.vue` — `canReview`

**复现步骤**：
1. 打开一个 `rejected` 状态的司机/车辆/线路审核弹窗
2. 观察"通过/驳回"按钮

**实际结果**：`canReview` 返回 `s === "pending_review" || s === "rejected"`，对 `rejected` 状态显示审核按钮。后端只允许审核 `pending_review` 状态，点击后返回 409。

**预期结果**：审核按钮应仅在 `pending_review` 状态显示。

---

### BUG-004 ★ High — 订单详情丢失货主原始备注

**文件**：`backend/app/logistics/api/admin/orders.py` L83-L87 + `admin/src/api/endpoints.ts` L190-L198

**复现步骤**：
1. 打开任意订单详情抽屉
2. 查看货主备注信息

**实际结果**：后端 detail 端点将 `remarks` 字段（原始为货主备注字符串）覆盖为 CS 备注时间线数组。前端 `lgOrder()` 将时间线映射到 `remarks_timeline`，并将 `remarks` 设为空字符串。**货主提交的原始备注在详情页不可见**。

**预期结果**：货主原始备注应保留并单独展示

**修复建议**：后端 detail 端点应使用独立字段名 `remarks_timeline` 而非覆盖 `remarks`。

---

### BUG-005 ★ High — 并发确认价格可导致容量双重预留

**文件**：`backend/app/logistics/api/admin/orders.py` L104-L110

**复现步骤**：
1. 订单处于 `price_confirmed` 状态（已有容量预留）
2. 两个 CS 人员同时点击"确认价格"（重新报价）

**实际结果**：无行级锁，两个请求可能交错执行 release/reserve，导致容量数据不一致。

**修复建议**：使用 `with_for_update()` 行锁。

---

### BUG-006 ★ High — 并发佣金结算可导致重复结算

**文件**：`backend/app/logistics/api/admin/commissions.py` L57-L67

**复现步骤**：
1. 佣金记录处于 `pending` 状态
2. 两个 CS 人员同时点击"结算"

**实际结果**：两个请求同时读取 `rec.status == "pending"`（通过），同时设置 `settled`，两个请求都返回成功。

**修复建议**：使用 `with_for_update()` 行锁。

---

### BUG-007 ★ Medium — AuthImage 无加载占位和错误提示

**文件**：`admin/src/components/AuthImage.vue`

**实际结果**：图片加载期间显示空白；加载失败时静默设为空字符串。

---

### BUG-008 ★ Medium — 改派功能要求手动输入 Trip ID

**文件**：`admin/src/views/lg/LgOrdersView.vue` — 改派弹窗

**实际结果**：用户无法知道哪些 Trip 可用，必须事先查好 ID。

---

### BUG-009 ★ Medium — 列表接口无 page_size 上限

**文件**：所有后端列表端点

**实际结果**：客户端可传 `page_size=1000000`，导致服务器加载全部记录到内存。

---

### BUG-010 ★ Medium — 佣金费率输入为自由文本

**文件**：`admin/src/views/lg/LgConfigView.vue`

**实际结果**：佣金费率使用 `el-input`，用户可输入任意字符串。

---

### BUG-011 ★ Low — 审核通过操作无确认弹窗

**文件**：LgDriversView / LgVehiclesView / LgRoutesView

**实际结果**：点击"通过"按钮直接提交，无确认弹窗。

---

### BUG-012 ★ Low — 黑名单值无格式校验

**文件**：`admin/src/views/lg/LgBlacklistView.vue` + `backend/app/logistics/schemas.py`

---

## 二、安全测试

### SEC-001 ★ Critical — JWT 密钥使用硬编码默认值

**文件**：`backend/app/config.py` L8

**风险**：`jwt_secret: str = "change-me-in-production"` — 若生产环境未配置 `.env`，攻击者可伪造任意 admin JWT token。

**修复**：启动时强制校验。

---

### SEC-002 ★ High — Admin 登录无速率限制/暴力破解防护

**文件**：`backend/app/api/admin/auth.py` L12-L17

**风险**：登录接口无速率限制、无验证码、无账户锁定。

**修复**：添加内存速率限制中间件。

---

### SEC-003 ★ High — 附件下载端点缺少访问日志

**文件**：`backend/app/logistics/api/h5_uploads.py` L23-L34

**风险**：admin token 可下载任意用户上传的敏感证件，但无访问日志。

---

### SEC-004 ★ Medium — Token 存储在 localStorage（XSS 风险）

**文件**：`admin/src/api/client.ts` L4

---

### SEC-005 ★ Medium — Config 更新无审计日志

**文件**：`backend/app/logistics/api/admin/config.py` L30-L47

---

### SEC-006 ★ Medium — StaffIn 无密码强度要求

**文件**：`backend/app/logistics/schemas.py` L29-L33

---

### SEC-007 ★ Low — 角色存储在 localStorage 可被篡改

**文件**：`admin/src/api/client.ts` L6

**说明**：后端 `require_roles` 提供真实拦截，仅 UI 层面绕过。

---

## 三、性能测试

### PERF-001 ★ Medium — 司机列表 N+1 查询

**文件**：`backend/app/logistics/api/admin/drivers.py` L52

**问题**：`_out(db, d)` 对每个司机调用 `db.get(UserAccount, driver.user_id)`。20 条/页 = 20 次额外查询。

---

### PERF-002 ★ Medium — 订单列表 N+1 查询（5 层）

**文件**：`backend/app/logistics/api/admin/orders.py` L71

**问题**：`order_out()` 对每个订单查询 Trip → Route → Vehicle → Driver → UserAccount。20 条/页 = 100 次额外查询。

---

### PERF-003 ★ Low — AuthImage 每张图片单独 fetch

**文件**：`admin/src/components/AuthImage.vue`

---

## 四、数据一致性测试

### DATA-001 ★ Medium — 并发完成订单可触发唯一约束异常

**文件**：`backend/app/logistics/api/admin/orders.py` L210-L226

**问题**：两个并发请求可能都通过 `status != ORDER_DELIVERED` 检查，第二个插入触发 `order_id` 唯一约束，返回未处理的 500 错误。

---

### DATA-002 ★ Low — 订单详情 API 字段类型不一致

**文件**：`backend/app/logistics/api/admin/orders.py` L83

**问题**：列表端点返回 `remarks: string`，详情端点返回 `remarks: array`。已在 BUG-004 中提出修复方案。

---

## 五、权限测试

| 测试场景 | 前端守卫 | 后端拦截 | 结果 |
|----------|----------|----------|------|
| CS 访问 `/lg/drivers` | ✅ 重定向 | ✅ 403 | 双重保护 ✓ |
| CS 访问 `/lg/config` | ✅ 重定向 | ✅ 403 | 双重保护 ✓ |
| Auditor 访问 `/lg/orders` | ✅ 重定向 | ✅ 403 | 双重保护 ✓ |
| 篡改 localStorage role | ❌ 可绕过前端 | ✅ 403 | 后端兜底 ✓ |
| H5 token 访问 admin API | — | ✅ 401 | 安全 ✓ |

**结论**：权限架构设计良好，后端 `require_roles` 提供真实拦截。

---

## 六、边界测试

| 编号 | 输入 | 结果 | 严重度 |
|------|------|------|--------|
| B-001 | `page_size=0` | 返回空列表 | Low |
| B-002 | `page_size=-1` | 可能 500 | Medium |
| B-003 | `page=0` | 可能 500 | Medium |
| B-004 | 黑名单 value 含 SQL 注入 | 参数化查询，安全 | — |
| B-005 | 备注含 `<script>` | Vue 自动转义，安全 | — |
| B-006 | 超长备注 | 后端无长度限制 | Low |
| B-007 | 佣金费率 `"abc"` | 后端 400 | — |

---

## 七、风险评估

### 质量评分

| 维度 | 评分 (100) |
|------|-----------|
| 稳定性 | 65 |
| 安全性 | 55 |
| 性能 | 70 |
| UI | 80 |
| UX | 65 |
| 代码质量 | 75 |
| 可维护性 | 80 |
| **综合** | **70** |

### 上线风险等级：**中高**

**不能直接上线的原因**：
1. BUG-001（Critical）：旧用户刷新页面会卡死
2. SEC-001（Critical）：JWT 默认密钥必须确认已修改
3. BUG-002/003（High）：取消和审核按钮错误显示
4. BUG-005/006（High）：并发问题可导致资金数据不一致
