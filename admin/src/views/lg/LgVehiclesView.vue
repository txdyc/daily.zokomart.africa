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
        v-for="s in LG_VEHICLE_STATUSES"
        :key="s.value"
        :value="s.value"
        :label="s.label"
      />
    </el-select>
    <el-button :loading="loading" @click="load">查询</el-button>
  </div>

  <el-table v-loading="loading" :data="rows" @row-click="openReview">
    <el-table-column prop="id" label="ID" width="70" />
    <el-table-column prop="plate_number" label="车牌号" width="130" />
    <el-table-column prop="vehicle_type" label="车型" width="110" />
    <el-table-column prop="brand_model" label="品牌/型号" min-width="150" />
    <el-table-column label="载重/容积" width="150">
      <template #default="{ row }">
        <div>{{ row.max_load_kg }} kg</div>
        <div class="muted">{{ row.max_volume_m3 }} m³</div>
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
    :title="current ? `车辆审核 · ${current.plate_number}` : '车辆审核'"
    width="820px"
    top="4vh"
  >
    <div v-if="current" v-loading="acting" class="profile">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="车牌号">{{ current.plate_number }}</el-descriptions-item>
        <el-descriptions-item label="品牌/型号">{{ current.brand_model }}</el-descriptions-item>
        <el-descriptions-item label="车型">{{ current.vehicle_type }}</el-descriptions-item>
        <el-descriptions-item label="年份">{{ current.year }}</el-descriptions-item>
        <el-descriptions-item label="VIN">{{ current.vin }}</el-descriptions-item>
        <el-descriptions-item label="司机ID">{{ current.driver_id }}</el-descriptions-item>
        <el-descriptions-item label="货厢尺寸 (m)">
          {{ current.cargo_length_m }} × {{ current.cargo_width_m }} × {{ current.cargo_height_m }}
        </el-descriptions-item>
        <el-descriptions-item label="最大载重/容积">
          {{ current.max_load_kg }} kg / {{ current.max_volume_m3 }} m³
        </el-descriptions-item>
        <el-descriptions-item label="行驶证到期">{{ current.roadworthy_expiry }}</el-descriptions-item>
        <el-descriptions-item label="保险到期">{{ current.insurance_expiry }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTag(current.status)">{{ statusLabel(current.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item v-if="current.review_remark" label="审核备注" :span="2">
          {{ current.review_remark }}
        </el-descriptions-item>
      </el-descriptions>

      <div class="section-title">车辆照片</div>
      <div class="gallery">
        <div v-for="p in photos" :key="p.key" class="gallery-item">
          <div class="gallery-label">{{ p.label }}</div>
          <div class="thumb-wrap"><AuthImage :id="p.id(current)" /></div>
        </div>
      </div>

      <div class="section-title">证件文件</div>
      <div class="gallery">
        <div v-for="d in docs" :key="d.key" class="gallery-item">
          <div class="gallery-label">{{ d.label }}</div>
          <div class="thumb-wrap"><AuthImage :id="d.id(current)" /></div>
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
      <el-button @click="reviewDialog = false">关闭</el-button>
      <template v-if="canReview">
        <el-button type="danger" :loading="acting" @click="submit('reject')">驳回</el-button>
        <el-button type="primary" :loading="acting" @click="submit('approve')">通过</el-button>
      </template>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import AuthImage from "../../components/AuthImage.vue";
import { lgReviewVehicle, lgVehicles } from "../../api/endpoints";
import { LG_VEHICLE_STATUSES, type LgVehicle } from "../../api/types";

const loading = ref(false);
const acting = ref(false);
const rows = ref<LgVehicle[]>([]);
const total = ref(0);

const filters = reactive({
  status: undefined as string | undefined,
  page: 1,
  page_size: 20,
});

const reviewDialog = ref(false);
const current = ref<LgVehicle | null>(null);
const reason = ref("");
const action = ref<"approve" | "reject">("approve");

const photos = [
  { key: "front", label: "正面", id: (v: LgVehicle) => v.photo_front_id },
  { key: "left", label: "左侧", id: (v: LgVehicle) => v.photo_left_id },
  { key: "right", label: "右侧", id: (v: LgVehicle) => v.photo_right_id },
  { key: "rear", label: "尾部", id: (v: LgVehicle) => v.photo_rear_id },
  { key: "interior", label: "车厢内部", id: (v: LgVehicle) => v.photo_interior_id },
];

const docs = [
  { key: "reg", label: "登记证书", id: (v: LgVehicle) => v.reg_cert_id },
  { key: "roadworthy", label: "行驶证", id: (v: LgVehicle) => v.roadworthy_cert_id },
  { key: "insurance", label: "保险单", id: (v: LgVehicle) => v.insurance_cert_id },
];

const canReview = computed(() => current.value?.status === "pending_review");

function statusLabel(v: string): string {
  return LG_VEHICLE_STATUSES.find((d) => d.value === v)?.label ?? v;
}
function statusTag(v: string): string {
  return LG_VEHICLE_STATUSES.find((d) => d.value === v)?.tag ?? "info";
}

onMounted(load);

async function load() {
  loading.value = true;
  try {
    const data = await lgVehicles({ ...filters });
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

function openReview(row: LgVehicle) {
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
    const updated = await lgReviewVehicle(row.id, act, reason.value.trim());
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
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-top: 4px;
}
.gallery {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.gallery-item {
  width: 180px;
}
.gallery-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.thumb-wrap {
  width: 180px;
  height: 120px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  overflow: hidden;
  background: #fafafa;
}
.review-form {
  margin-top: 4px;
}
</style>
