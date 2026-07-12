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
        v-for="s in LG_ROUTE_STATUSES"
        :key="s.value"
        :value="s.value"
        :label="s.label"
      />
    </el-select>
    <el-button :loading="loading" @click="load">查询</el-button>
  </div>

  <el-table v-loading="loading" :data="rows" @row-click="openReview">
    <el-table-column prop="id" label="ID" width="70" />
    <el-table-column label="线路" min-width="180">
      <template #default="{ row }">
        {{ row.origin_town }} → {{ row.dest_town }}
      </template>
    </el-table-column>
    <el-table-column prop="frequency" label="频次" width="110" />
    <el-table-column label="定价 (GHS)" width="180">
      <template #default="{ row }">
        <div v-if="row.rate_per_ton !== null">{{ row.rate_per_ton }}/吨</div>
        <div v-if="row.rate_per_m3 !== null" class="muted">{{ row.rate_per_m3 }}/m³</div>
        <div v-if="row.min_charge !== null" class="muted">最低: {{ row.min_charge }}</div>
      </template>
    </el-table-column>
    <el-table-column label="发车时间" width="120">
      <template #default="{ row }">
        <div>{{ row.depart_time }}</div>
        <div class="muted">约 {{ row.est_duration_hours }}h</div>
      </template>
    </el-table-column>
    <el-table-column label="状态" width="100">
      <template #default="{ row }">
        <el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="120" fixed="right">
      <template #default="{ row }">
        <el-button link type="primary" @click.stop="openReview(row)">审核</el-button>
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

  <el-dialog
    v-model="reviewDialog"
    :title="`线路审核 · ${current ? laneText(current) : ''}`"
    width="780px"
    top="4vh"
  >
    <div v-if="current" v-loading="acting" class="profile">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="起点">
          {{ current.origin_region }} / {{ current.origin_town }}
        </el-descriptions-item>
        <el-descriptions-item label="终点">
          {{ current.dest_region }} / {{ current.dest_town }}
        </el-descriptions-item>
        <el-descriptions-item label="途经" :span="2">
          {{ current.via_towns.length ? current.via_towns.join(" → ") : "—" }}
        </el-descriptions-item>
        <el-descriptions-item label="频次">{{ current.frequency }}</el-descriptions-item>
        <el-descriptions-item label="工作日">
          {{ current.weekdays.length ? weekdayText(current.weekdays) : "—" }}
        </el-descriptions-item>
        <el-descriptions-item label="一次性日期">
          {{ current.once_date ?? "—" }}
        </el-descriptions-item>
        <el-descriptions-item label="发车时间">{{ current.depart_time }}</el-descriptions-item>
        <el-descriptions-item label="预计时长">{{ current.est_duration_hours }} 小时</el-descriptions-item>
        <el-descriptions-item label="默认车辆ID">{{ current.default_vehicle_id }}</el-descriptions-item>
        <el-descriptions-item label="货物类型" :span="2">
          {{ current.cargo_types.length ? current.cargo_types.join("、") : "不限" }}
        </el-descriptions-item>
        <el-descriptions-item label="禁运说明" :span="2">
          {{ current.prohibited_notes || "—" }}
        </el-descriptions-item>
        <el-descriptions-item label="定价">
          <span v-if="current.rate_per_ton !== null">{{ current.rate_per_ton }}/吨 ·</span>
          <span v-if="current.rate_per_m3 !== null">{{ current.rate_per_m3 }}/m³ ·</span>
          <span v-if="current.min_charge !== null">最低 {{ current.min_charge }}</span>
          <span v-if="!current.negotiable" class="muted">（一口价）</span>
        </el-descriptions-item>
        <el-descriptions-item label="司机ID">{{ current.driver_id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTag(current.status)">{{ statusLabel(current.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item v-if="current.review_remark" label="审核备注" :span="2">
          {{ current.review_remark }}
        </el-descriptions-item>
      </el-descriptions>

      <el-form label-width="90px" class="review-form">
        <el-form-item label="审核备注">
          <el-input
            v-model="reason"
            type="textarea"
            :rows="2"
            :placeholder="action === 'reject' ? '驳回原因（必填）' : '通过备注（可选）'"
          />
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <span v-if="current && auth.role === 'admin'" class="admin-actions">
        <el-button
          v-if="current.status === 'approved'"
          type="warning"
          :loading="acting"
          @click="suspend"
        >暂停</el-button>
        <el-button
          v-if="current.status === 'suspended'"
          type="success"
          :loading="acting"
          @click="resume"
        >恢复</el-button>
      </span>
      <el-button @click="reviewDialog = false">关闭</el-button>
      <template v-if="canReview">
        <el-button type="danger" :loading="acting" @click="submit('reject')">驳回</el-button>
        <el-button type="primary" :loading="acting" @click="submit('approve')">通过</el-button>
      </template>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import {
  lgResumeRoute,
  lgReviewRoute,
  lgRoutes,
  lgSuspendRoute,
} from "../../api/endpoints";
import { LG_ROUTE_STATUSES, type LgRoute } from "../../api/types";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();

const WEEKDAY_LABELS = ["日", "一", "二", "三", "四", "五", "六"];

const loading = ref(false);
const acting = ref(false);
const rows = ref<LgRoute[]>([]);
const total = ref(0);

const filters = reactive({
  status: undefined as string | undefined,
  page: 1,
  page_size: 20,
});

const reviewDialog = ref(false);
const current = ref<LgRoute | null>(null);
const reason = ref("");
const action = ref<"approve" | "reject">("approve");

const canReview = computed(() => current.value?.status === "pending_review");

function statusLabel(v: string): string {
  return LG_ROUTE_STATUSES.find((d) => d.value === v)?.label ?? v;
}
function statusTag(v: string): string {
  return LG_ROUTE_STATUSES.find((d) => d.value === v)?.tag ?? "info";
}
function laneText(r: LgRoute): string {
  return `${r.origin_town} → ${r.dest_town}`;
}
function weekdayText(days: number[]): string {
  return days.map((d) => `周${WEEKDAY_LABELS[d] ?? d}`).join("、");
}

onMounted(load);

async function load() {
  loading.value = true;
  try {
    const data = await lgRoutes({ ...filters });
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

function openReview(row: LgRoute) {
  current.value = row;
  reason.value = "";
  action.value = "approve";
  reviewDialog.value = true;
}

async function submit(act: "approve" | "reject") {
  const row = current.value;
  if (!row) return;
  if (act === "reject" && !reason.value.trim()) {
    ElMessage.warning("驳回原因必填");
    return;
  }
  acting.value = true;
  try {
    const updated = await lgReviewRoute(row.id, act, reason.value.trim());
    Object.assign(row, updated);
    ElMessage.success(act === "approve" ? "已通过" : "已驳回");
    reviewDialog.value = false;
    await load();
  } catch {
    /* interceptor toasted */
  } finally {
    acting.value = false;
  }
}

async function suspend() {
  const row = current.value;
  if (!row) return;
  const { value } = await ElMessageBox.prompt("请输入暂停原因", "暂停线路", {
    type: "warning",
    inputPlaceholder: "暂停原因（必填）",
    inputValidator: (v) => (v && v.trim() ? true : "请输入暂停原因"),
  });
  acting.value = true;
  try {
    const updated = await lgSuspendRoute(row.id, value.trim());
    Object.assign(row, updated);
    ElMessage.success("已暂停");
    await load();
  } catch {
    /* interceptor toasted */
  } finally {
    acting.value = false;
  }
}

async function resume() {
  const row = current.value;
  if (!row) return;
  await ElMessageBox.confirm(`确定恢复「${laneText(row)}」？`, "恢复确认", { type: "info" });
  acting.value = true;
  try {
    const updated = await lgResumeRoute(row.id);
    Object.assign(row, updated);
    ElMessage.success("已恢复");
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
.muted {
  color: #909399;
  font-size: 12px;
}
.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
.profile {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.review-form {
  margin-top: 4px;
}
.admin-actions {
  margin-right: auto;
}
</style>
