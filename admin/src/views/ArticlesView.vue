<template>
  <div class="filters">
    <el-select v-model="filters.status" placeholder="全部状态" clearable class="filter">
      <el-option v-for="s in ARTICLE_STATUSES" :key="s.value" :value="s.value" :label="s.label" />
    </el-select>
    <el-select v-model="filters.country" placeholder="全部国家" clearable class="filter">
      <el-option
        v-for="c in countries"
        :key="c.code"
        :value="c.code"
        :label="`${c.flag_emoji} ${c.name_zh}`"
      />
    </el-select>
    <el-select v-model="filters.site_id" placeholder="全部站点" clearable class="filter-wide">
      <el-option v-for="s in sites" :key="s.id" :value="s.id" :label="s.name" />
    </el-select>
    <el-button :loading="loading" @click="load">查询</el-button>
  </div>

  <el-table v-loading="loading" :data="rows">
    <el-table-column type="expand">
      <template #default="{ row }">
        <div class="expand">
          <p>来源：<a :href="row.source_url" target="_blank" rel="noopener">{{ row.source_url }}</a></p>
          <p v-if="row.translation_error" class="failed">翻译错误：{{ row.translation_error }}</p>
        </div>
      </template>
    </el-table-column>
    <el-table-column prop="id" label="ID" width="70" />
    <el-table-column label="图片" width="70">
      <template #default="{ row }">
        <img v-if="row.main_image_url" :src="row.main_image_url" class="thumb" />
        <span v-else class="muted">—</span>
      </template>
    </el-table-column>
    <el-table-column label="标题" min-width="240">
      <template #default="{ row }">
        <div class="title-cell">{{ row.title }}</div>
        <div v-if="row.title_zh" class="muted title-cell">{{ row.title_zh }}</div>
      </template>
    </el-table-column>
    <el-table-column prop="site_name" label="站点" width="120" />
    <el-table-column prop="country_code" label="国家" width="70" />
    <el-table-column label="分类" width="80">
      <template #default="{ row }">{{ categoryLabel(row.category) }}</template>
    </el-table-column>
    <el-table-column label="状态" width="90">
      <template #default="{ row }">
        <el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="轮播" width="70">
      <template #default="{ row }">
        <el-button
          link
          :type="row.is_banner ? 'warning' : 'info'"
          @click="toggleBanner(row)"
        >{{ row.is_banner ? "★" : "☆" }}</el-button>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="190" fixed="right">
      <template #default="{ row }">
        <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
        <el-button link type="primary" @click="retranslate(row)">重翻译</el-button>
        <el-button link type="danger" @click="remove(row)">删除</el-button>
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

  <el-dialog v-model="editDialog" title="编辑新闻" width="860px" top="4vh">
    <el-form label-width="90px">
      <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
      <el-form-item label="中文标题"><el-input v-model="form.title_zh" /></el-form-item>
      <div class="row2">
        <el-form-item label="分类">
          <el-select v-model="form.category" clearable>
            <el-option v-for="c in CATEGORIES" :key="c.value" :value="c.value" :label="c.label" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option v-for="s in ARTICLE_STATUSES" :key="s.value" :value="s.value" :label="s.label" />
          </el-select>
        </el-form-item>
      </div>
      <el-form-item label="主图 URL">
        <el-input v-model="form.main_image_url" />
        <img v-if="form.main_image_url" :src="form.main_image_url" class="preview" />
      </el-form-item>
      <div class="row2">
        <el-form-item label="原文段落" class="para-item">
          <el-input v-model="form.paragraphsText" type="textarea" :rows="14" />
          <div class="muted">段落数: {{ sourceCount }}（空行分段）</div>
        </el-form-item>
        <el-form-item label="中文段落" class="para-item">
          <el-input v-model="form.paragraphsZhText" type="textarea" :rows="14" />
          <div class="muted">段落数: {{ zhCount }}</div>
        </el-form-item>
      </div>
      <el-alert
        v-if="zhCount > 0 && sourceCount !== zhCount"
        title="段落数不一致：双语对照视图将错位"
        type="warning"
        :closable="false"
      />
    </el-form>
    <template #footer>
      <el-button @click="editDialog = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import {
  deleteArticle,
  listArticles,
  listCountries,
  listSites,
  patchArticle,
  retranslateArticle,
} from "../api/endpoints";
import type { ArticleAdmin, Country, Site } from "../api/types";
import { ARTICLE_STATUSES, CATEGORIES } from "../api/types";
import { joinParagraphs, splitParagraphs } from "../utils/paragraphs";

const loading = ref(false);
const saving = ref(false);
const rows = ref<ArticleAdmin[]>([]);
const total = ref(0);
const countries = ref<Country[]>([]);
const sites = ref<Site[]>([]);

const filters = reactive({
  status: undefined as string | undefined,
  country: undefined as string | undefined,
  site_id: undefined as number | undefined,
  page: 1,
  page_size: 20,
});

const editDialog = ref(false);
const editing = ref<ArticleAdmin | null>(null);
const form = reactive({
  title: "",
  title_zh: "",
  category: "" as string | null,
  status: "",
  main_image_url: "" as string | null,
  paragraphsText: "",
  paragraphsZhText: "",
});

const sourceCount = computed(() => splitParagraphs(form.paragraphsText).length);
const zhCount = computed(() => splitParagraphs(form.paragraphsZhText).length);

onMounted(async () => {
  [countries.value, sites.value] = await Promise.all([listCountries(), listSites()]);
  await load();
});

async function load() {
  loading.value = true;
  try {
    const data = await listArticles({ ...filters });
    rows.value = data.items;
    total.value = data.total;
  } finally {
    loading.value = false;
  }
}

function statusLabel(v: string) {
  return ARTICLE_STATUSES.find((s) => s.value === v)?.label ?? v;
}
function statusTag(v: string) {
  return ARTICLE_STATUSES.find((s) => s.value === v)?.tag ?? "info";
}
function categoryLabel(v: string | null) {
  return CATEGORIES.find((c) => c.value === v)?.label ?? (v || "—");
}

async function toggleBanner(row: ArticleAdmin) {
  const updated = await patchArticle(row.id, { is_banner: !row.is_banner });
  row.is_banner = updated.is_banner;
}

async function retranslate(row: ArticleAdmin) {
  await ElMessageBox.confirm(`将「${row.title}」重新加入翻译队列？`, "重新翻译", { type: "info" });
  const updated = await retranslateArticle(row.id);
  row.status = updated.status;
  row.translation_error = updated.translation_error;
  ElMessage.success("已加入翻译队列");
}

async function remove(row: ArticleAdmin) {
  await ElMessageBox.confirm(`确定删除「${row.title}」？`, "删除确认", { type: "warning" });
  await deleteArticle(row.id);
  ElMessage.success("已删除");
  await load();
}

function openEdit(row: ArticleAdmin) {
  editing.value = row;
  form.title = row.title;
  form.title_zh = row.title_zh ?? "";
  form.category = row.category;
  form.status = row.status;
  form.main_image_url = row.main_image_url;
  form.paragraphsText = joinParagraphs(row.paragraphs);
  form.paragraphsZhText = joinParagraphs(row.paragraphs_zh);
  editDialog.value = true;
}

async function save() {
  const row = editing.value;
  if (!row) return;
  if (zhCount.value > 0 && sourceCount.value !== zhCount.value) {
    await ElMessageBox.confirm(
      "段落数不一致，双语对照将错位，确定保存？",
      "段落对齐警告",
      { type: "warning" },
    );
  }
  const body: Parameters<typeof patchArticle>[1] = {};
  if (form.title !== row.title) body.title = form.title;
  if ((form.title_zh || null) !== row.title_zh) body.title_zh = form.title_zh || null;
  if (form.category !== row.category) body.category = form.category || null;
  if (form.status !== row.status) body.status = form.status;
  if ((form.main_image_url || null) !== row.main_image_url)
    body.main_image_url = form.main_image_url || null;
  const paragraphs = splitParagraphs(form.paragraphsText);
  if (JSON.stringify(paragraphs) !== JSON.stringify(row.paragraphs)) body.paragraphs = paragraphs;
  const paragraphsZh = splitParagraphs(form.paragraphsZhText);
  if (JSON.stringify(paragraphsZh) !== JSON.stringify(row.paragraphs_zh ?? []))
    body.paragraphs_zh = paragraphsZh;

  if (Object.keys(body).length === 0) {
    editDialog.value = false;
    return;
  }
  saving.value = true;
  try {
    await patchArticle(row.id, body);
    editDialog.value = false;
    ElMessage.success("已保存");
    await load();
  } catch {
    /* interceptor toasted */
  } finally {
    saving.value = false;
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
  width: 140px;
}
.filter-wide {
  width: 180px;
}
.thumb {
  width: 48px;
  height: 32px;
  object-fit: cover;
  border-radius: 4px;
}
.title-cell {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.muted {
  color: #93918a;
  font-size: 12px;
}
.failed {
  color: #e24b4a;
}
.expand {
  padding: 4px 16px;
  font-size: 13px;
}
.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
.row2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 12px;
}
.para-item :deep(.el-form-item__content) {
  display: block;
}
.preview {
  margin-top: 8px;
  max-height: 120px;
  border-radius: 4px;
}
</style>
