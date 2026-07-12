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
        v-for="s in LG_COMMISSION_STATUSES"
        :key="s.value"
        :value="s.value"
        :label="s.label"
      />
    </el-select>
    <el-input
      v-model="driverIdInput"
      placeholder="司机 ID"
      clearable
      class="filter"
      @change="resetAndLoad"
    />
    <el-button :loading="loading" @click="load">查询</el-button>
  </div>

  <el-table v-loading="loading" :data="rows">
    <el-table-column prop="id" label="ID" width="70" />
    <el-table-column prop="order_id" label="订单" width="80" />
    <el-table-column prop="driver_id" label="司机" width="80" />
    <el-table-column label="运费 (GHS)" width="110">
      <template #default="{ row }">{{ row.freight_ghs }}</template>
    </el-table-column>
    <el-table-column label="费率" width="90">
      <template #default="{ row }">{{ (row.rate * 100).toFixed(1) }}%</template>
    </el-table-column>
    <el-table-column label="佣金 (GHS)" width="110">
      <template #default="{ row }">{{ row.amount_ghs }}</template>
    </el-table-column>
    <el-table-column label="状态" width="100">
      <template #default="{ row }">
        <el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="结算方式" width="100">
      <template #default="{ row }">{{ row.method || "—" }}</template>
    </el-table-column>
    <el-table-column label="结算凭证" min-width="140">
      <template #default="{ row }">{{ row.reference || "—" }}</template>
    </el-table-column>
    <el-table-column label="操作" width="160" fixed="right">
      <template #default="{ row }">
        <el-button
          v-if="row.status === 'pending'"
          link
          type="primary"
          @click="openSettle(row)"
        >结算</el-button>
        <el-button
          v-if="row.status === 'pending' && auth.role === 'admin'"
          link
          type="warning"
          @click="openWaive(row)"
        >豁免</el-button>
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

  <!-- 结算 -->
  <el-dialog v-model="settleDialog" title="结算佣金" width="460px">
    <el-form label-width="90px">
      <el-form-item label="佣金金额">
        <span class="amount">GHS {{ current?.amount_ghs ?? 0 }}</span>
      </el-form-item>
      <el-form-item label="结算方式">
        <el-select v-model="settleForm.method" placeholder="选择结算方式">
          <el-option value="momo" label="Mobile Money" />
          <el-option value="bank" label="银行转账" />
          <el-option value="cash" label="现金" />
        </el-select>
      </el-form-item>
      <el-form-item label="结算凭证">
        <el-input
          v-model="settleForm.reference"
          placeholder="交易流水号 / 收据号"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="settleDialog = false">取消</el-button>
      <el-button type="primary" :loading="acting" @click="submitSettle">确认结算</el-button>
    </template>
  </el-dialog>

  <!-- 豁免 -->
  <el-dialog v-model="waiveDialog" title="豁免佣金" width="420px">
    <el-form label-width="90px">
      <el-form-item label="豁免原因">
        <el-input
          v-model="waiveReason"
          type="textarea"
          :rows="3"
          placeholder="豁免原因（必填）"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="waiveDialog = false">取消</el-button>
      <el-button type="warning" :loading="acting" @click="submitWaive">确认豁免</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import { onMounted, reactive, ref } from "vue";

import {
  lgCommissions,
  lgSettleCommission,
  lgWaiveCommission,
} from "../../api/endpoints";
import { LG_COMMISSION_STATUSES, type LgCommission } from "../../api/types";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();

const loading = ref(false);
const acting = ref(false);
const rows = ref<LgCommission[]>([]);
const total = ref(0);
const driverIdInput = ref("");

const filters = reactive({
  status: undefined as string | undefined,
  driver_id: undefined as number | undefined,
  page: 1,
  page_size: 20,
});

const settleDialog = ref(false);
const current = ref<LgCommission | null>(null);
const settleForm = reactive({ method: "momo", reference: "" });

const waiveDialog = ref(false);
const waiveReason = ref("");

function statusLabel(v: string): string {
  return LG_COMMISSION_STATUSES.find((s) => s.value === v)?.label ?? v;
}
function statusTag(v: string): string {
  return LG_COMMISSION_STATUSES.find((s) => s.value === v)?.tag ?? "info";
}

onMounted(load);

async function load() {
  loading.value = true;
  try {
    const driverId = driverIdInput.value ? Number(driverIdInput.value) : undefined;
    filters.driver_id = driverId && !Number.isNaN(driverId) ? driverId : undefined;
    const data = await lgCommissions({ ...filters });
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

function openSettle(row: LgCommission) {
  current.value = row;
  settleForm.method = "momo";
  settleForm.reference = "";
  settleDialog.value = true;
}

async function submitSettle() {
  const row = current.value;
  if (!row) return;
  if (!settleForm.method) {
    ElMessage.warning("请选择结算方式");
    return;
  }
  acting.value = true;
  try {
    const updated = await lgSettleCommission(
      row.id,
      settleForm.method,
      settleForm.reference.trim(),
    );
    Object.assign(row, updated);
    ElMessage.success("已结算");
    settleDialog.value = false;
    await load();
  } catch {
    /* interceptor toasted */
  } finally {
    acting.value = false;
  }
}

function openWaive(row: LgCommission) {
  current.value = row;
  waiveReason.value = "";
  waiveDialog.value = true;
}

async function submitWaive() {
  const row = current.value;
  if (!row) return;
  if (!waiveReason.value.trim()) {
    ElMessage.warning("豁免原因必填");
    return;
  }
  acting.value = true;
  try {
    const updated = await lgWaiveCommission(row.id, waiveReason.value.trim());
    Object.assign(row, updated);
    ElMessage.success("已豁免");
    waiveDialog.value = false;
    await load();
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
.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
.amount {
  font-size: 16px;
  font-weight: 600;
  color: #e24b4a;
}
</style>
