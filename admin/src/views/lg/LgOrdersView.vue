<template>
  <div class="filters">
    <el-select
      v-model="filters.status"
      placeholder="全部状态"
      clearable
      class="filter"
      @change="resetAndLoad"
    >
      <el-option
        v-for="s in LG_ORDER_STATUSES"
        :key="s.value"
        :value="s.value"
        :label="s.label"
      />
    </el-select>
    <el-button :loading="loading" @click="load">查询</el-button>
  </div>

  <el-table v-loading="loading" :data="rows" @row-click="openDetail">
    <el-table-column prop="id" label="ID" width="70" />
    <el-table-column label="线路" min-width="160">
      <template #default="{ row }">{{ row.origin_town }} → {{ row.dest_town }}</template>
    </el-table-column>
    <el-table-column label="货物" min-width="160">
      <template #default="{ row }">
        <div>{{ row.cargo_name }}</div>
        <div class="muted">{{ row.weight_kg }} kg · {{ row.pieces }} 件</div>
      </template>
    </el-table-column>
    <el-table-column label="状态" width="100">
      <template #default="{ row }">
        <el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="运费" width="100">
      <template #default="{ row }">
        {{ row.freight_ghs !== null ? `GHS ${row.freight_ghs}` : "—" }}
      </template>
    </el-table-column>
    <el-table-column label="发车日期" width="120">
      <template #default="{ row }">
        <div>{{ row.depart_date }}</div>
        <div class="muted">{{ row.depart_time }}</div>
      </template>
    </el-table-column>
    <el-table-column label="创建时间" width="160">
      <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
    </el-table-column>
    <el-table-column label="操作" width="100" fixed="right">
      <template #default="{ row }">
        <el-button link type="primary" @click.stop="openDetail(row)">详情</el-button>
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

  <el-drawer
    v-model="detailDrawer"
    :title="current ? `订单 #${current.id} · ${statusLabel(current.status)}` : '订单详情'"
    direction="rtl"
    size="640px"
  >
    <div v-if="current" v-loading="acting" class="detail">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="订单ID">{{ current.id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTag(current.status)">{{ statusLabel(current.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="线路">
          {{ current.origin_town }} → {{ current.dest_town }}
        </el-descriptions-item>
        <el-descriptions-item label="发车">
          {{ current.depart_date }} {{ current.depart_time }}
        </el-descriptions-item>
        <el-descriptions-item label="货物名称">{{ current.cargo_name }}</el-descriptions-item>
        <el-descriptions-item label="货物类别">{{ current.cargo_category }}</el-descriptions-item>
        <el-descriptions-item label="包装">{{ current.packaging }}</el-descriptions-item>
        <el-descriptions-item label="件数">{{ current.pieces }}</el-descriptions-item>
        <el-descriptions-item label="重量">{{ current.weight_kg }} kg</el-descriptions-item>
        <el-descriptions-item label="体积">{{ current.volume_m3 }} m³</el-descriptions-item>
        <el-descriptions-item label="易碎">{{ current.fragile ? "是" : "否" }}</el-descriptions-item>
        <el-descriptions-item label="需装货">{{ current.needs_loading ? "是" : "否" }}</el-descriptions-item>
        <el-descriptions-item label="需取货">{{ current.needs_pickup ? "是" : "否" }}</el-descriptions-item>
        <el-descriptions-item label="取货窗口">{{ current.pickup_window || "—" }}</el-descriptions-item>
        <el-descriptions-item label="取货城市">{{ current.pickup_town || "—" }}</el-descriptions-item>
        <el-descriptions-item label="送达城市">{{ current.delivery_town || "—" }}</el-descriptions-item>
        <el-descriptions-item label="运费 (GHS)">
          {{ current.freight_ghs !== null ? current.freight_ghs : "—" }}
        </el-descriptions-item>
        <el-descriptions-item label="佣金 (GHS)">
          {{ current.commission_ghs !== null ? current.commission_ghs : "—" }}
        </el-descriptions-item>
        <el-descriptions-item label="取货时间">{{ current.pickup_time || "—" }}</el-descriptions-item>
        <el-descriptions-item label="Trip ID">{{ current.trip_id }}</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ formatTime(current.created_at) }}</el-descriptions-item>
        <el-descriptions-item v-if="current.cancel_reason" label="取消/关闭原因" :span="2">
          {{ current.cancel_reason }}
        </el-descriptions-item>
      </el-descriptions>

      <div class="contacts">
        <el-card shadow="never" class="contact-card">
          <template #header>司机信息</template>
          <template v-if="current.driver">
            <p>{{ current.driver.full_name }}</p>
            <p>车牌: {{ current.driver.plate_number }}</p>
            <p>电话: {{ current.driver.phone }}</p>
          </template>
          <p v-else class="muted">暂不可见（待取货阶段后披露）</p>
        </el-card>
        <el-card shadow="never" class="contact-card">
          <template #header>货主信息</template>
          <template v-if="current.shipper">
            <p>联系人: {{ current.shipper.contact_name || "—" }}</p>
            <p>电话: {{ current.shipper.contact_phone || "—" }}</p>
            <p>取货详情: {{ current.shipper.pickup_details || "—" }}</p>
            <p>送达详情: {{ current.shipper.delivery_details || "—" }}</p>
            <p>收货人: {{ current.shipper.consignee_name || "—" }} / {{ current.shipper.consignee_phone || "—" }}</p>
          </template>
          <p v-else class="muted">暂不可见</p>
        </el-card>
      </div>

      <div class="section-title">
        CS 备注
        <el-tag v-if="current.reject_count" size="small" type="danger" class="reject-tag">
          驳回 {{ current.reject_count }} 次
        </el-tag>
      </div>
      <el-timeline v-if="current.remarks_timeline?.length" class="timeline">
        <el-timeline-item
          v-for="(r, i) in current.remarks_timeline"
          :key="i"
          :timestamp="formatTime(r.created_at)"
          placement="top"
        >
          <div class="remark-author">{{ r.author }}</div>
          <div>{{ r.body }}</div>
        </el-timeline-item>
      </el-timeline>
      <p v-else class="muted">暂无备注</p>

      <div class="section-title">操作</div>
      <div class="actions">
        <el-button
          v-if="canConfirmPrice"
          type="primary"
          @click="openConfirmPrice"
        >确认价格</el-button>
        <el-button
          v-if="current.status === 'submitted'"
          @click="openReassign"
        >改派</el-button>
        <el-button
          v-if="current.status === 'delivered'"
          type="success"
          @click="complete"
        >完成</el-button>
        <el-button
          v-if="canClose"
          type="warning"
          @click="openExceptionClose"
        >异常关闭</el-button>
        <el-button
          v-if="canCancel"
          type="danger"
          @click="openCancel"
        >取消</el-button>
        <el-button @click="openRemark">添加备注</el-button>
      </div>
    </div>
  </el-drawer>

  <!-- 确认价格 -->
  <el-dialog v-model="confirmPriceDialog" title="确认价格" width="500px">
    <el-form label-width="110px">
      <el-form-item label="运费 (GHS)">
        <el-input-number v-model="confirmForm.freight_ghs" :min="0" :precision="2" />
      </el-form-item>
      <el-form-item label="取货时间">
        <el-input v-model="confirmForm.pickup_time" placeholder="如: 2026-07-15 10:00" />
      </el-form-item>
      <el-form-item label="佣金 (GHS)">
        <el-input-number
          v-model="confirmForm.commission_ghs"
          :min="0"
          :precision="2"
          :placeholder="autoCommission"
        />
        <div class="muted">留空则按费率 {{ commissionRate }} 自动计算: {{ autoCommission }}</div>
      </el-form-item>
      <el-form-item v-if="confirmForm.commission_ghs !== null" label="覆盖原因">
        <el-input
          v-model="confirmForm.override_reason"
          type="textarea"
          :rows="2"
          placeholder="覆盖佣金费率时必填"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="confirmPriceDialog = false">取消</el-button>
      <el-button type="primary" :loading="acting" @click="submitConfirmPrice">确认</el-button>
    </template>
  </el-dialog>

  <!-- 改派 -->
  <el-dialog v-model="reassignDialog" title="改派订单" width="420px">
    <el-form label-width="90px">
      <el-form-item label="目标 Trip">
        <el-input-number v-model="reassignForm.trip_id" :min="1" />
        <div class="muted">输入目标行程 ID（需为开放状态且发车日期未过）</div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="reassignDialog = false">取消</el-button>
      <el-button type="primary" :loading="acting" @click="submitReassign">确认改派</el-button>
    </template>
  </el-dialog>

  <!-- 取消 -->
  <el-dialog v-model="cancelDialog" title="取消订单" width="420px">
    <el-form label-width="90px">
      <el-form-item label="取消原因">
        <el-input v-model="cancelReason" type="textarea" :rows="3" placeholder="取消原因（必填）" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="cancelDialog = false">取消</el-button>
      <el-button type="danger" :loading="acting" @click="submitCancel">确认取消</el-button>
    </template>
  </el-dialog>

  <!-- 异常关闭 -->
  <el-dialog v-model="exceptionDialog" title="异常关闭" width="420px">
    <el-form label-width="90px">
      <el-form-item label="处理说明">
        <el-input v-model="exceptionReason" type="textarea" :rows="3" placeholder="处理说明（必填）" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="exceptionDialog = false">取消</el-button>
      <el-button type="warning" :loading="acting" @click="submitExceptionClose">确认关闭</el-button>
    </template>
  </el-dialog>

  <!-- 添加备注 -->
  <el-dialog v-model="remarkDialog" title="添加 CS 备注" width="420px">
    <el-form label-width="90px">
      <el-form-item label="备注内容">
        <el-input v-model="remarkBody" type="textarea" :rows="3" placeholder="备注内容" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="remarkDialog = false">取消</el-button>
      <el-button type="primary" :loading="acting" @click="submitRemark">提交</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import {
  lgAddRemark,
  lgCancelOrder,
  lgCompleteOrder,
  lgConfig,
  lgConfirmPrice,
  lgExceptionClose,
  lgOrder,
  lgOrders,
  lgReassign,
} from "../../api/endpoints";
import { LG_ORDER_STATUSES, type LgOrder } from "../../api/types";

const loading = ref(false);
const acting = ref(false);
const rows = ref<LgOrder[]>([]);
const total = ref(0);

const filters = reactive({
  status: undefined as string | undefined,
  page: 1,
  page_size: 20,
});

const detailDrawer = ref(false);
const current = ref<LgOrder | null>(null);
const commissionRate = ref("0.08");

const confirmPriceDialog = ref(false);
const confirmForm = reactive({
  freight_ghs: 0,
  pickup_time: "",
  commission_ghs: null as number | null,
  override_reason: "",
});

const reassignDialog = ref(false);
const reassignForm = reactive({ trip_id: 1 });

const cancelDialog = ref(false);
const cancelReason = ref("");

const exceptionDialog = ref(false);
const exceptionReason = ref("");

const remarkDialog = ref(false);
const remarkBody = ref("");

const canConfirmPrice = computed(() => {
  const s = current.value?.status;
  return s === "submitted" || s === "price_confirmed";
});
const canCancel = computed(() => {
  const s = current.value?.status;
  return s && !["completed", "cancelled", "exception_closed"].includes(s);
});
const canClose = computed(() => {
  const s = current.value?.status;
  return s && !["completed", "cancelled", "exception_closed"].includes(s);
});

const autoCommission = computed(() => {
  const rate = parseFloat(commissionRate.value) || 0;
  return (confirmForm.freight_ghs * rate).toFixed(2);
});

function statusLabel(v: string): string {
  return LG_ORDER_STATUSES.find((s) => s.value === v)?.label ?? v;
}
function statusTag(v: string): string {
  return LG_ORDER_STATUSES.find((s) => s.value === v)?.tag ?? "info";
}
function formatTime(iso: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return iso;
  }
}

onMounted(async () => {
  try {
    const cfg = await lgConfig();
    commissionRate.value = cfg.lg_commission_rate || "0.08";
  } catch {
    /* default rate */
  }
  await load();
});

async function load() {
  loading.value = true;
  try {
    const data = await lgOrders({ ...filters });
    rows.value = data.items;
    total.value = data.total;
  } finally {
    loading.value = false;
  }
}

function resetAndLoad() {
  filters.page = 1;
  load();
}

async function openDetail(row: LgOrder) {
  current.value = row;
  detailDrawer.value = true;
  await refreshCurrent(row.id);
}

async function refreshCurrent(id: number) {
  acting.value = true;
  try {
    const detail = await lgOrder(id);
    if (current.value) {
      Object.assign(current.value, detail);
      const idx = rows.value.findIndex((r) => r.id === id);
      if (idx >= 0) Object.assign(rows.value[idx], detail);
    }
  } finally {
    acting.value = false;
  }
}

function openConfirmPrice() {
  confirmForm.freight_ghs = current.value?.freight_ghs ?? 0;
  confirmForm.pickup_time = current.value?.pickup_time ?? "";
  confirmForm.commission_ghs = null;
  confirmForm.override_reason = "";
  confirmPriceDialog.value = true;
}

async function submitConfirmPrice() {
  const row = current.value;
  if (!row) return;
  if (!confirmForm.freight_ghs || confirmForm.freight_ghs <= 0) {
    ElMessage.warning("运费必须大于 0");
    return;
  }
  if (!confirmForm.pickup_time.trim()) {
    ElMessage.warning("取货时间必填");
    return;
  }
  if (confirmForm.commission_ghs !== null && !confirmForm.override_reason.trim()) {
    ElMessage.warning("覆盖佣金费率时需填写原因");
    return;
  }
  acting.value = true;
  try {
    const body: {
      freight_ghs: number;
      pickup_time: string;
      commission_ghs?: number | null;
      override_reason?: string;
    } = {
      freight_ghs: confirmForm.freight_ghs,
      pickup_time: confirmForm.pickup_time.trim(),
    };
    if (confirmForm.commission_ghs !== null) {
      body.commission_ghs = confirmForm.commission_ghs;
      body.override_reason = confirmForm.override_reason.trim();
    }
    await lgConfirmPrice(row.id, body);
    ElMessage.success("价格已确认");
    confirmPriceDialog.value = false;
    await refreshCurrent(row.id);
    await load();
  } catch {
    /* interceptor toasted */
  } finally {
    acting.value = false;
  }
}

function openReassign() {
  reassignForm.trip_id = current.value?.trip_id ?? 1;
  reassignDialog.value = true;
}

async function submitReassign() {
  const row = current.value;
  if (!row) return;
  if (!reassignForm.trip_id) {
    ElMessage.warning("请输入目标 Trip ID");
    return;
  }
  acting.value = true;
  try {
    await lgReassign(row.id, reassignForm.trip_id);
    ElMessage.success("已改派");
    reassignDialog.value = false;
    await refreshCurrent(row.id);
    await load();
  } catch {
    /* interceptor toasted */
  } finally {
    acting.value = false;
  }
}

function openCancel() {
  cancelReason.value = "";
  cancelDialog.value = true;
}

async function submitCancel() {
  const row = current.value;
  if (!row) return;
  if (!cancelReason.value.trim()) {
    ElMessage.warning("取消原因必填");
    return;
  }
  acting.value = true;
  try {
    await lgCancelOrder(row.id, cancelReason.value.trim());
    ElMessage.success("已取消");
    cancelDialog.value = false;
    await refreshCurrent(row.id);
    await load();
  } catch {
    /* interceptor toasted */
  } finally {
    acting.value = false;
  }
}

function openExceptionClose() {
  exceptionReason.value = "";
  exceptionDialog.value = true;
}

async function submitExceptionClose() {
  const row = current.value;
  if (!row) return;
  if (!exceptionReason.value.trim()) {
    ElMessage.warning("处理说明必填");
    return;
  }
  acting.value = true;
  try {
    await lgExceptionClose(row.id, exceptionReason.value.trim());
    ElMessage.success("已异常关闭");
    exceptionDialog.value = false;
    await refreshCurrent(row.id);
    await load();
  } catch {
    /* interceptor toasted */
  } finally {
    acting.value = false;
  }
}

async function complete() {
  const row = current.value;
  if (!row) return;
  await ElMessageBox.confirm(`确认完成订单 #${row.id}？将生成佣金记录。`, "完成订单", {
    type: "warning",
  });
  acting.value = true;
  try {
    await lgCompleteOrder(row.id);
    ElMessage.success("已完成");
    await refreshCurrent(row.id);
    await load();
  } catch {
    /* interceptor toasted */
  } finally {
    acting.value = false;
  }
}

function openRemark() {
  remarkBody.value = "";
  remarkDialog.value = true;
}

async function submitRemark() {
  const row = current.value;
  if (!row) return;
  if (!remarkBody.value.trim()) {
    ElMessage.warning("备注内容必填");
    return;
  }
  acting.value = true;
  try {
    await lgAddRemark(row.id, remarkBody.value.trim());
    ElMessage.success("备注已添加");
    remarkDialog.value = false;
    await refreshCurrent(row.id);
  } catch {
    /* interceptor toasted */
  } finally {
    acting.value = false;
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
  width: 160px;
}
.muted {
  color: #909399;
  font-size: 12px;
}
.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
.detail {
  padding: 0 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.contacts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.contact-card :deep(.el-card__header) {
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
}
.contact-card p {
  margin: 4px 0;
  font-size: 13px;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 8px;
}
.reject-tag {
  margin-left: 4px;
}
.timeline {
  padding-left: 0;
}
.remark-author {
  font-size: 12px;
  color: #909399;
  margin-bottom: 2px;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
