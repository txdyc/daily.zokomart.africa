<template>
  <el-card class="card">
    <template #header>AI 翻译配置</template>
    <el-form label-width="110px" class="form">
      <el-form-item label="Base URL">
        <el-input v-model="form.ai_base_url" placeholder="https://api.openai.com/v1" />
      </el-form-item>
      <el-form-item label="模型">
        <el-input v-model="form.ai_model" placeholder="gpt-4o-mini" />
      </el-form-item>
      <el-form-item label="API Key">
        <el-input
          v-model="form.ai_api_key"
          type="password"
          show-password
          :placeholder="maskedPlaceholder"
        />
        <div class="muted">留空则保持现有 Key 不变</div>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        <el-button :loading="testing" @click="runTest">测试翻译</el-button>
      </el-form-item>
      <el-alert
        v-if="testResult && testResult.ok"
        type="success"
        :closable="false"
        :title="`测试成功（${testResult.latency_ms} ms）：${testResult.title_zh}`"
        :description="testResult.paragraph_zh"
      />
      <el-alert
        v-else-if="testResult"
        type="error"
        :closable="false"
        :title="`测试失败：${testResult.error}`"
      />
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import { getConfig, testTranslation, updateConfig } from "../api/endpoints";
import type { TestTranslationResult } from "../api/endpoints";

const saving = ref(false);
const testing = ref(false);
const masked = ref("");
const testResult = ref<TestTranslationResult | null>(null);

const form = reactive({
  ai_base_url: "",
  ai_model: "",
  ai_api_key: "",
});

const maskedPlaceholder = computed(() =>
  masked.value ? `当前：${masked.value}` : "尚未配置",
);

onMounted(load);

async function load() {
  const cfg = await getConfig();
  form.ai_base_url = cfg.ai_base_url;
  form.ai_model = cfg.ai_model;
  masked.value = cfg.ai_api_key_masked;
  form.ai_api_key = "";
}

async function save() {
  saving.value = true;
  try {
    const body: { ai_base_url: string; ai_model: string; ai_api_key?: string } = {
      ai_base_url: form.ai_base_url,
      ai_model: form.ai_model,
    };
    if (form.ai_api_key) body.ai_api_key = form.ai_api_key;
    const cfg = await updateConfig(body);
    masked.value = cfg.ai_api_key_masked;
    form.ai_api_key = "";
    ElMessage.success("已保存");
  } catch {
    /* interceptor toasted */
  } finally {
    saving.value = false;
  }
}

async function runTest() {
  testing.value = true;
  testResult.value = null;
  try {
    testResult.value = await testTranslation();
  } catch {
    /* 404 before Plan 2 — interceptor toasted */
  } finally {
    testing.value = false;
  }
}
</script>

<style scoped>
.card {
  max-width: 640px;
}
.form :deep(.el-alert) {
  margin-top: 8px;
}
.muted {
  color: #93918a;
  font-size: 12px;
}
</style>
