<template>
  <div v-loading="loading">
    <div class="toolbar">
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        @change="fetch"
      />
    </div>

    <el-row :gutter="12" class="kpi-row">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="kpi-label">司机总数</div>
          <div class="kpi-value">{{ totalDrivers }}</div>
          <div class="kpi-sub">
            <el-tag v-for="(n, s) in stats.drivers" :key="s" size="small" class="tag">
              {{ driverStatusLabel(s) }}: {{ n }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="kpi-label">车辆 / 活跃线路</div>
          <div class="kpi-value">{{ stats.vehicles }} / {{ stats.routes_active }}</div>
          <div class="kpi-sub">即将发车: {{ stats.trips_upcoming }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="kpi-label">订单总数</div>
          <div class="kpi-value">{{ stats.orders_total }}</div>
          <div class="kpi-sub">
            完成率: {{ (stats.completion_rate * 100).toFixed(1) }}% /
            取消率: {{ (stats.cancellation_rate * 100).toFixed(1) }}%
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="kpi-label">GMV (GHS)</div>
          <div class="kpi-value">{{ stats.gmv_ghs.toFixed(2) }}</div>
          <div class="kpi-sub">
            佣金待结: {{ stats.commission.pending_ghs.toFixed(2) }} /
            已结: {{ stats.commission.settled_ghs.toFixed(2) }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="12" class="kpi-row">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>订单状态分布</template>
          <el-tag v-for="(n, s) in stats.orders" :key="s" class="tag" :type="orderTagType(s)">
            {{ orderStatusLabel(s) }}: {{ n }}
          </el-tag>
          <div class="kpi-sub">运力利用率: {{ (stats.capacity_utilization * 100).toFixed(1) }}%</div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>热门线路 (Top 5)</template>
          <el-table :data="stats.top_lanes" size="small" stripe>
            <el-table-column prop="lane" label="线路" />
            <el-table-column prop="orders" label="订单数" width="100" />
          </el-table>
          <p v-if="!stats.top_lanes.length" class="empty-hint">暂无数据</p>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { lgStats } from "../../api/endpoints";
import {
  LG_DRIVER_STATUSES,
  LG_ORDER_STATUSES,
  type StatsOverview,
} from "../../api/types";

const stats = ref<StatsOverview>({
  drivers: {},
  vehicles: 0,
  routes_active: 0,
  trips_upcoming: 0,
  orders: {},
  orders_total: 0,
  gmv_ghs: 0,
  commission: { pending_ghs: 0, settled_ghs: 0 },
  top_lanes: [],
  completion_rate: 0,
  cancellation_rate: 0,
  capacity_utilization: 0,
});

const loading = ref(false);
const dateRange = ref<[string, string] | null>(null);

const totalDrivers = computed(() =>
  Object.values(stats.value.drivers).reduce((a, b) => a + b, 0),
);

function driverStatusLabel(s: string): string {
  return LG_DRIVER_STATUSES.find((d) => d.value === s)?.label ?? s;
}
function orderStatusLabel(s: string): string {
  return LG_ORDER_STATUSES.find((o) => o.value === s)?.label ?? s;
}
function orderTagType(s: string): string {
  return LG_ORDER_STATUSES.find((o) => o.value === s)?.tag ?? "info";
}

async function fetch() {
  loading.value = true;
  try {
    const params: { start?: string; end?: string } = {};
    if (dateRange.value) {
      params.start = dateRange.value[0];
      params.end = dateRange.value[1];
    }
    stats.value = await lgStats(params);
  } finally {
    loading.value = false;
  }
}

onMounted(fetch);
</script>

<style scoped>
.toolbar {
  margin-bottom: 12px;
}
.kpi-row {
  margin-bottom: 12px;
}
.kpi-label {
  font-size: 13px;
  color: #909399;
}
.kpi-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  margin: 4px 0;
}
.kpi-sub {
  font-size: 12px;
  color: #909399;
}
.tag {
  margin: 2px 4px 2px 0;
}
.empty-hint {
  text-align: center;
  color: #c0c4cc;
  font-size: 13px;
  padding: 16px 0;
}
</style>
