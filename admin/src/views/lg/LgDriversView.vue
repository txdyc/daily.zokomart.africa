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
        v-for="s in LG_DRIVER_STATUSES"
        :key="s.value"
        :value="s.value"
        :label="s.label"
      />
    </el-select>
    <el-button :loading="loading" @click="load">查询</el-button>
  </div>

  <el-table v-loading="loading" :data="rows" @row-click="openReview">
    <el-table-column prop="id" label="ID" width="70" />
    <el-table-column prop="full_name" label="姓名" width="120" />
    <el-table-column prop="phone" label="手机号" width="130" />
    <el-table-column prop="ghana_card_number" label="Ghana Card" width="160" />
    <el-table-column label="驾照" width="160">
      <template #default="{ row }">
        <div>{{ row.licence_class }} · {{ row.licence_number }}</div>
        <div class="muted">到期: {{ row.licence_expiry || "—" }}</div>
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
    :title="current ? `司机审核 · ${current.full_name}` : '司机审核'"
    width="780px"
    top="4vh"
  >
    <div v-if="current" v-loading="acting" class="profile">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="姓名">{{ current.full_name }}</el-descriptions-item>
        <el-descriptions-item label="手机号">{{ current.phone }}</el-descriptions-item>
        <el-descriptions-item label="性别">{{ current.gender }}</el-descriptions-item>
        <el-descriptions-item label="出生日期">{{ current.date_of_birth }}</el-descriptions-item>
        <el-descriptions-item label="Ghana Card">{{ current.ghana_card_number }}</el-descriptions-item>
        <el-descriptions-item label="驾照号">{{ current.licence_number }}</el-descriptions-item>
        <el-descriptions-item label="准驾类别">{{ current.licence_class }}</el-descriptions-item>
        <el-descriptions-item label="驾照到期">{{ current.licence_expiry }}</el-descriptions-item>
        <el-descriptions-item label="紧急联系人">{{ current.emergency_contact_name }}</el-descriptions-item>
        <el-descriptions-item label="紧急联系电话">{{ current.emergency_contact_phone }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTag(current.status)">{{ statusLabel(current.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="可用时段">{{ current.availability }}</el-descriptions-item>
        <el-descriptions-item v-if="current.review_remark" label="审核备注" :span="2">
          {{ current.review_remark }}
        </el-descriptions-item>
      </el-descriptions>

      <div class="gallery">
        <div class="gallery-item">
          <div class="gallery-label">Ghana Card 正面</div>
          <div class="thumb-wrap"><AuthImage :id="current.ghana_card_front_id" /></div>
        </div>
        <div class="gallery-item">
          <div class="gallery-label">Ghana Card 背面</div>
          <div class="thumb-wrap"><AuthImage :id="current.ghana_card_back_id" /></div>
        </div>
        <div class="gallery-item">
          <div class="gallery-label">驾照照片</div>
          <div class="thumb-wrap"><AuthImage :id="current.licence_photo_id" /></div>
        </div>
      </div>

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
      <span
        v-if="current && (current.status === 'approved' || current.status === 'frozen') && auth.role === 'admin'"
        class="admin-actions"
      >
        <el-button
          v-if="current.status === 'approved'"
          type="warning"
          :loading="acting"
          @click="freeze"
        >冻结</el-button>
        <el-button
          v-if="current.status === 'frozen'"
          type="success"
          :loading="acting"
          @click="unfreeze"
        >解冻</el-button>
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

import AuthImage from "../../components/AuthImage.vue";
import {
  lgDrivers,
  lgFreezeDriver,
  lgReviewDriver,
  lgUnfreezeDriver,
} from "../../api/endpoints";
import { LG_DRIVER_STATUSES, type LgDriver } from "../../api/types";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();

const loading = ref(false);
const acting = ref(false);
const rows = ref<LgDriver[]>([]);
const total = ref(0);

const filters = reactive({
  status: undefined as string | undefined,
  page: 1,
  page_size: 20,
});

const reviewDialog = ref(false);
const current = ref<LgDriver | null>(null);
const reason = ref("");
const action = ref<"approve" | "reject">("approve");

const canReview = computed(() => current.value?.status === "pending_review");

function statusLabel(v: string): string {
  return LG_DRIVER_STATUSES.find((d) => d.value === v)?.label ?? v;
}
function statusTag(v: string): string {
  return LG_DRIVER_STATUSES.find((d) => d.value === v)?.tag ?? "info";
}

onMounted(load);

async function load() {
  loading.value = true;
  try {
    const data = await lgDrivers({ ...filters });
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

function openReview(row: LgDriver) {
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
    const updated = await lgReviewDriver(row.id, act, reason.value.trim());
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

async function freeze() {
  const row = current.value;
  if (!row) return;
  const { value } = await ElMessageBox.prompt("请输入冻结原因", "冻结司机", {
    type: "warning",
    inputPlaceholder: "冻结原因（必填）",
    inputValidator: (v) => (v && v.trim() ? true : "请输入冻结原因"),
  });
  acting.value = true;
  try {
    const updated = await lgFreezeDriver(row.id, value.trim());
    Object.assign(row, updated);
    ElMessage.success("已冻结");
    await load();
  } catch {
    /* interceptor toasted */
  } finally {
    acting.value = false;
  }
}

async function unfreeze() {
  const row = current.value;
  if (!row) return;
  await ElMessageBox.confirm(`确定解冻「${row.full_name}」？`, "解冻确认", { type: "info" });
  acting.value = true;
  try {
    const updated = await lgUnfreezeDriver(row.id);
    Object.assign(row, updated);
    ElMessage.success("已解冻");
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
  gap: 16px;
}
.gallery {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.gallery-item {
  width: 200px;
}
.gallery-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.thumb-wrap {
  width: 200px;
  height: 130px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  overflow: hidden;
  background: #fafafa;
}
.review-form {
  margin-top: 4px;
}
.admin-actions {
  margin-right: auto;
}
</style>
