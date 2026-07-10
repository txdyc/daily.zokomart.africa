<template>
  <h3>抓取记录</h3>
  <div class="toolbar">
    <el-select v-model="siteId" placeholder="全部站点" clearable class="filter-wide" @change="loadRuns">
      <el-option v-for="s in sites" :key="s.id" :value="s.id" :label="s.name" />
    </el-select>
    <el-button :loading="loadingRuns" @click="loadRuns">刷新</el-button>
    <el-switch v-model="autoRefresh" active-text="自动刷新（10 秒）" />
  </div>
  <el-table v-loading="loadingRuns" :data="runs">
    <el-table-column type="expand">
      <template #default="{ row }">
        <div class="expand">{{ row.error || "无错误" }}</div>
      </template>
    </el-table-column>
    <el-table-column prop="id" label="ID" width="70" />
    <el-table-column prop="site_name" label="站点" min-width="130" />
    <el-table-column label="开始时间" width="150">
      <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
    </el-table-column>
    <el-table-column label="结束时间" width="150">
      <template #default="{ row }">{{ formatTime(row.finished_at) }}</template>
    </el-table-column>
    <el-table-column label="状态" width="90">
      <template #default="{ row }">
        <el-tag :type="runTag(row.status)">{{ runLabel(row.status) }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="articles_found" label="发现" width="70" />
    <el-table-column prop="articles_new" label="新增" width="70" />
  </el-table>
  <el-pagination
    v-model:current-page="page"
    :page-size="pageSize"
    :total="totalRuns"
    layout="prev, pager, next, total"
    class="pager"
    @current-change="loadRuns"
  />

  <h3 class="section">翻译失败</h3>
  <div class="toolbar">
    <el-button :loading="loadingFailed" @click="loadFailed">刷新</el-button>
    <el-button type="primary" :disabled="failed.length === 0" :loading="retrying" @click="retryAll">
      全部重试（{{ failed.length }}）
    </el-button>
  </div>
  <el-table v-loading="loadingFailed" :data="failed">
    <el-table-column prop="id" label="ID" width="70" />
    <el-table-column prop="title" label="标题" min-width="220" />
    <el-table-column prop="site_name" label="站点" width="130" />
    <el-table-column prop="translation_error" label="错误" min-width="220" show-overflow-tooltip />
    <el-table-column label="操作" width="100" fixed="right">
      <template #default="{ row }">
        <el-button link type="primary" @click="retryOne(row)">重试</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import { onMounted, onUnmounted, ref, watch } from "vue";

import { listArticles, listCrawlRuns, listSites, retranslateArticle } from "../api/endpoints";
import type { ArticleAdmin, CrawlRun, Site } from "../api/types";

const sites = ref<Site[]>([]);
const runs = ref<CrawlRun[]>([]);
const failed = ref<ArticleAdmin[]>([]);
const siteId = ref<number | undefined>(undefined);
const page = ref(1);
const pageSize = 20;
const totalRuns = ref(0);
const loadingRuns = ref(false);
const loadingFailed = ref(false);
const retrying = ref(false);
const autoRefresh = ref(false);

let timer: ReturnType<typeof setInterval> | null = null;

onMounted(async () => {
  sites.value = await listSites();
  await Promise.all([loadRuns(), loadFailed()]);
});

onUnmounted(stopTimer);

watch(autoRefresh, (on) => {
  if (on) timer = setInterval(loadRuns, 10_000);
  else stopTimer();
});

function stopTimer() {
  if (timer) clearInterval(timer);
  timer = null;
}

async function loadRuns() {
  loadingRuns.value = true;
  try {
    const data = await listCrawlRuns({ site_id: siteId.value, page: page.value, page_size: pageSize });
    runs.value = data.items;
    totalRuns.value = data.total;
  } finally {
    loadingRuns.value = false;
  }
}

async function loadFailed() {
  loadingFailed.value = true;
  try {
    const data = await listArticles({ status: "translation_failed", page: 1, page_size: 50 });
    failed.value = data.items;
  } finally {
    loadingFailed.value = false;
  }
}

async function retryOne(row: ArticleAdmin) {
  await retranslateArticle(row.id);
  ElMessage.success(`#${row.id} 已加入翻译队列`);
  await loadFailed();
}

async function retryAll() {
  retrying.value = true;
  let done = 0;
  try {
    for (const row of failed.value) {
      await retranslateArticle(row.id);
      done += 1;
    }
    ElMessage.success(`已重新排队 ${done} 篇`);
  } finally {
    retrying.value = false;
    await loadFailed();
  }
}

function formatTime(iso: string | null): string {
  return iso ? iso.replace("T", " ").slice(0, 19) : "—";
}
function runLabel(s: string) {
  return { running: "进行中", success: "成功", failed: "失败" }[s] ?? s;
}
function runTag(s: string) {
  return ({ running: "warning", success: "success", failed: "danger" } as const)[
    s as "running" | "success" | "failed"
  ] ?? "info";
}
</script>

<style scoped>
h3 {
  margin: 0 0 12px;
  font-weight: 500;
}
.section {
  margin-top: 32px;
}
.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}
.filter-wide {
  width: 180px;
}
.expand {
  padding: 4px 16px;
  font-size: 13px;
  white-space: pre-wrap;
}
.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
</style>
