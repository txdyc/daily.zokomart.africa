<template>
  <el-tabs v-model="tab">
    <el-tab-pane label="站点" name="sites">
      <div class="toolbar">
        <el-button type="primary" @click="openSiteDialog()">新增站点</el-button>
        <el-button :loading="loading" @click="loadAll">刷新</el-button>
      </div>
      <el-table v-loading="loading" :data="sites">
        <el-table-column prop="name" label="名称" min-width="130" />
        <el-table-column label="国家" width="130">
          <template #default="{ row }">{{ countryLabel(row.country_id) }}</template>
        </el-table-column>
        <el-table-column prop="language" label="语言" width="70" />
        <el-table-column label="采集方式" width="90">
          <template #default="{ row }">{{ row.discovery_method === "rss" ? "RSS" : "列表页" }}</template>
        </el-table-column>
        <el-table-column prop="tier" label="层级" width="70" />
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch
              :model-value="row.enabled"
              @change="(v: string | number | boolean) => toggleSite(row, Boolean(v))"
            />
          </template>
        </el-table-column>
        <el-table-column label="最近抓取" min-width="180">
          <template #default="{ row }">
            <div v-if="row.last_crawl_status">
              <span :class="{ failed: row.last_crawl_status.startsWith('failed') }">
                {{ row.last_crawl_status }}
              </span>
              <div class="muted">{{ formatTime(row.last_crawl_at) }}</div>
            </div>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="crawlNow(row)">抓取</el-button>
            <el-button link type="primary" @click="openSiteDialog(row)">编辑</el-button>
            <el-button link type="danger" @click="removeSite(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="国家" name="countries">
      <div class="toolbar">
        <el-button type="primary" @click="openCountryDialog()">新增国家</el-button>
      </div>
      <el-table v-loading="loading" :data="countries">
        <el-table-column prop="code" label="代码" width="80" />
        <el-table-column prop="flag_emoji" label="国旗" width="70" />
        <el-table-column prop="name_zh" label="中文名" min-width="110" />
        <el-table-column prop="name_en" label="英文名" min-width="130" />
        <el-table-column prop="tier" label="层级" width="70" />
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch
              :model-value="row.enabled"
              @change="(v: string | number | boolean) => toggleCountry(row, Boolean(v))"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openCountryDialog(row)">编辑</el-button>
            <el-button link type="danger" @click="removeCountry(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>
  </el-tabs>

  <el-dialog v-model="siteDialog" :title="siteForm.id ? '编辑站点' : '新增站点'" width="560px">
    <el-form label-width="110px">
      <el-form-item label="国家" required>
        <el-select v-model="siteForm.country_id" placeholder="选择国家">
          <el-option
            v-for="c in countries"
            :key="c.id"
            :value="c.id"
            :label="`${c.flag_emoji} ${c.name_zh}`"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="名称" required>
        <el-input v-model="siteForm.name" />
      </el-form-item>
      <el-form-item label="Base URL" required>
        <el-input v-model="siteForm.base_url" placeholder="https://..." />
      </el-form-item>
      <el-form-item label="语言">
        <el-radio-group v-model="siteForm.language">
          <el-radio value="en">英语</el-radio>
          <el-radio value="fr">法语</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="层级">
        <el-select v-model="siteForm.tier">
          <el-option :value="1" label="Tier 1（每小时）" />
          <el-option :value="2" label="Tier 2（每6小时）" />
          <el-option :value="3" label="低频（每天）" />
        </el-select>
      </el-form-item>
      <el-form-item label="采集方式">
        <el-radio-group v-model="siteForm.discovery_method">
          <el-radio value="rss">RSS</el-radio>
          <el-radio value="listing">列表页</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="siteForm.discovery_method === 'rss'" label="Feed URL" required>
        <el-input v-model="siteForm.feed_url" placeholder="https://.../feed/" />
      </el-form-item>
      <template v-else>
        <el-form-item label="列表页 URL" required>
          <el-input v-model="siteForm.listing_url" />
        </el-form-item>
        <el-form-item label="链接选择器">
          <el-input v-model="siteForm.listing_selector" placeholder="CSS 选择器，留空用同域启发式" />
        </el-form-item>
      </template>
      <el-collapse>
        <el-collapse-item title="高级：提取选择器（可选，留空用通用提取）">
          <el-form-item label="标题选择器"><el-input v-model="siteForm.title_selector" /></el-form-item>
          <el-form-item label="正文选择器"><el-input v-model="siteForm.body_selector" /></el-form-item>
          <el-form-item label="图片选择器"><el-input v-model="siteForm.image_selector" /></el-form-item>
          <el-form-item label="日期选择器"><el-input v-model="siteForm.date_selector" /></el-form-item>
        </el-collapse-item>
      </el-collapse>
    </el-form>
    <template #footer>
      <el-button @click="siteDialog = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="saveSite">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="countryDialog" :title="countryForm.id ? '编辑国家' : '新增国家'" width="420px">
    <el-form label-width="90px">
      <el-form-item label="代码" required>
        <el-input v-model="countryForm.code" placeholder="两位大写，如 GH" maxlength="2" />
      </el-form-item>
      <el-form-item label="中文名" required><el-input v-model="countryForm.name_zh" /></el-form-item>
      <el-form-item label="英文名" required><el-input v-model="countryForm.name_en" /></el-form-item>
      <el-form-item label="国旗" required>
        <el-input v-model="countryForm.flag_emoji" placeholder="🇬🇭" maxlength="8" />
      </el-form-item>
      <el-form-item label="层级">
        <el-select v-model="countryForm.tier">
          <el-option :value="1" label="Tier 1" />
          <el-option :value="2" label="Tier 2" />
          <el-option :value="3" label="低频" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="countryDialog = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="saveCountry">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { onMounted, reactive, ref } from "vue";

import {
  createCountry,
  createSite,
  deleteCountry,
  deleteSite,
  listCountries,
  listSites,
  triggerCrawl,
  updateCountry,
  updateSite,
} from "../api/endpoints";
import type { Country, Site, SiteIn } from "../api/types";

const tab = ref("sites");
const loading = ref(false);
const saving = ref(false);
const countries = ref<Country[]>([]);
const sites = ref<Site[]>([]);

const siteDialog = ref(false);
const countryDialog = ref(false);

const emptySite = (): SiteIn & { id?: number } => ({
  country_id: 0,
  name: "",
  base_url: "",
  language: "en",
  discovery_method: "rss",
  feed_url: null,
  listing_url: null,
  listing_selector: null,
  title_selector: null,
  body_selector: null,
  image_selector: null,
  date_selector: null,
  tier: 1,
  enabled: true,
});
const siteForm = reactive<SiteIn & { id?: number }>(emptySite());

const emptyCountry = (): Omit<Country, "id"> & { id?: number } => ({
  code: "",
  name_en: "",
  name_zh: "",
  flag_emoji: "",
  tier: 1,
  enabled: true,
});
const countryForm = reactive<Omit<Country, "id"> & { id?: number }>(emptyCountry());

onMounted(loadAll);

async function loadAll() {
  loading.value = true;
  try {
    [countries.value, sites.value] = await Promise.all([listCountries(), listSites()]);
  } finally {
    loading.value = false;
  }
}

function countryLabel(id: number): string {
  const c = countries.value.find((c) => c.id === id);
  return c ? `${c.flag_emoji} ${c.name_zh}` : String(id);
}

function formatTime(iso: string | null): string {
  return iso ? iso.replace("T", " ").slice(0, 16) : "";
}

function openSiteDialog(row?: Site) {
  Object.assign(siteForm, emptySite(), row ?? {});
  if (row) siteForm.id = row.id;
  else delete siteForm.id;
  siteDialog.value = true;
}

async function saveSite() {
  if (!siteForm.country_id || !siteForm.name || !siteForm.base_url) {
    ElMessage.warning("请填写国家、名称和 Base URL");
    return;
  }
  if (siteForm.discovery_method === "rss" && !siteForm.feed_url) {
    ElMessage.warning("RSS 方式需要填写 Feed URL");
    return;
  }
  if (siteForm.discovery_method === "listing" && !siteForm.listing_url) {
    ElMessage.warning("列表页方式需要填写列表页 URL");
    return;
  }
  saving.value = true;
  try {
    const { id, ...body } = siteForm;
    if (id) await updateSite(id, body);
    else await createSite(body);
    siteDialog.value = false;
    await loadAll();
    ElMessage.success("已保存");
  } catch {
    /* interceptor already toasted */
  } finally {
    saving.value = false;
  }
}

async function toggleSite(row: Site, enabled: boolean) {
  const { id, last_crawl_at, last_crawl_status, country, ...body } = row;
  try {
    await updateSite(id, { ...body, enabled });
    row.enabled = enabled;
  } catch {
    /* interceptor toasted */
  }
}

async function removeSite(row: Site) {
  await ElMessageBox.confirm(`确定删除站点「${row.name}」？`, "删除确认", { type: "warning" });
  try {
    await deleteSite(row.id);
    await loadAll();
    ElMessage.success("已删除");
  } catch {
    /* 409 has articles — interceptor toasted */
  }
}

async function crawlNow(row: Site) {
  try {
    const { crawl_run_id } = await triggerCrawl(row.id);
    ElMessage.success(`已开始抓取（记录 #${crawl_run_id}），可在「抓取与翻译」页查看进度`);
  } catch {
    /* 409 already running / 404 before Plan 2 — interceptor toasted */
  }
}

function openCountryDialog(row?: Country) {
  Object.assign(countryForm, emptyCountry(), row ?? {});
  if (row) countryForm.id = row.id;
  else delete countryForm.id;
  countryDialog.value = true;
}

async function saveCountry() {
  if (!countryForm.code || !countryForm.name_zh || !countryForm.name_en || !countryForm.flag_emoji) {
    ElMessage.warning("请填写完整的国家信息");
    return;
  }
  saving.value = true;
  try {
    const { id, ...body } = countryForm;
    body.code = body.code.toUpperCase();
    if (id) await updateCountry(id, body);
    else await createCountry(body);
    countryDialog.value = false;
    await loadAll();
    ElMessage.success("已保存");
  } catch {
    /* interceptor toasted */
  } finally {
    saving.value = false;
  }
}

async function toggleCountry(row: Country, enabled: boolean) {
  const { id, ...body } = row;
  try {
    await updateCountry(id, { ...body, enabled });
    row.enabled = enabled;
  } catch {
    /* interceptor toasted */
  }
}

async function removeCountry(row: Country) {
  await ElMessageBox.confirm(`确定删除国家「${row.name_zh}」？`, "删除确认", { type: "warning" });
  try {
    await deleteCountry(row.id);
    await loadAll();
    ElMessage.success("已删除");
  } catch {
    /* 409 has sites/articles — interceptor toasted */
  }
}
</script>

<style scoped>
.toolbar {
  margin-bottom: 12px;
  display: flex;
  gap: 8px;
}
.failed {
  color: #e24b4a;
}
.muted {
  color: #93918a;
  font-size: 12px;
}
</style>
