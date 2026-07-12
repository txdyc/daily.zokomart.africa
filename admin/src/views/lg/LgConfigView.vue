<template>
  <el-card class="card" v-loading="loading">
    <template #header>物流设置</template>
    <el-form label-width="130px" class="form">
      <el-form-item label="佣金费率">
        <el-input-number
          v-model="commissionRateNum"
          :min="0"
          :max="0.5"
          :step="0.01"
          :precision="2"
          @change="onRateChange"
        />
        <div class="muted">范围 0 – 0.5（即 0% – 50%）</div>
      </el-form-item>
      <el-form-item label="支付说明">
        <el-input
          v-model="form.lg_payment_instructions"
          type="textarea"
          :rows="4"
          placeholder="司机可见的支付收款说明，如银行账户/MoMo 号码等"
        />
      </el-form-item>
      <el-form-item label="短信服务商">
        <el-select v-model="form.lg_sms_provider">
          <el-option value="mock" label="mock（仅日志）" />
          <el-option value="arkesel" label="Arkesel" />
        </el-select>
      </el-form-item>
      <el-form-item label="短信 Sender ID">
        <el-input v-model="form.lg_sms_sender_id" placeholder="ZokoDaily" />
      </el-form-item>
      <el-form-item label="短信 API Key">
        <el-input
          v-model="form.lg_sms_api_key"
          type="password"
          show-password
          :placeholder="maskedPlaceholder"
        />
        <div class="muted">留空则保持现有 Key 不变</div>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        <el-button @click="load">重置</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import { lgConfig, lgUpdateConfig } from "../../api/endpoints";

const loading = ref(false);
const saving = ref(false);
const maskedApiKey = ref("");
const commissionRateNum = ref(0.08);

const form = reactive({
  lg_commission_rate: "0.08",
  lg_payment_instructions: "",
  lg_sms_provider: "mock",
  lg_sms_sender_id: "",
  lg_sms_api_key: "",
});

const maskedPlaceholder = computed(() =>
  maskedApiKey.value ? `当前：${maskedApiKey.value}` : "尚未配置",
);

function onRateChange(val: number | undefined) {
  form.lg_commission_rate = val !== undefined ? String(val) : "0.08";
}

onMounted(load);

async function load() {
  loading.value = true;
  try {
    const cfg = await lgConfig();
    form.lg_commission_rate = cfg.lg_commission_rate;
    commissionRateNum.value = parseFloat(cfg.lg_commission_rate) || 0.08;
    form.lg_payment_instructions = cfg.lg_payment_instructions;
    form.lg_sms_provider = cfg.lg_sms_provider;
    form.lg_sms_sender_id = cfg.lg_sms_sender_id;
    maskedApiKey.value = cfg.lg_sms_api_key;
    form.lg_sms_api_key = "";
  } finally {
    loading.value = false;
  }
}

async function save() {
  const rate = parseFloat(form.lg_commission_rate);
  if (Number.isNaN(rate) || rate < 0 || rate > 0.5) {
    ElMessage.warning("佣金费率必须是 0 – 0.5 之间的数字");
    return;
  }
  saving.value = true;
  try {
    const body: Record<string, string> = {
      lg_commission_rate: form.lg_commission_rate,
      lg_payment_instructions: form.lg_payment_instructions,
      lg_sms_provider: form.lg_sms_provider,
      lg_sms_sender_id: form.lg_sms_sender_id,
    };
    if (form.lg_sms_api_key) body.lg_sms_api_key = form.lg_sms_api_key;
    await lgUpdateConfig(body);
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
.card {
  max-width: 720px;
}
.form {
  max-width: 560px;
}
.muted {
  color: #93918a;
  font-size: 12px;
}
</style>
