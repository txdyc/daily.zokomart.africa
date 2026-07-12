<script setup lang="ts">
import { onUnmounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";

const { t } = useI18n();
const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const phone = ref("");
const code = ref("");
const step = ref<"phone" | "code">("phone");
const error = ref("");
const busy = ref(false);
const cooldown = ref(0);
let timer: ReturnType<typeof setInterval> | undefined;

function startCooldown() {
  cooldown.value = 60;
  timer = setInterval(() => {
    cooldown.value -= 1;
    if (cooldown.value <= 0 && timer) clearInterval(timer);
  }, 1000);
}
onUnmounted(() => timer && clearInterval(timer));

async function sendCode() {
  if (busy.value || cooldown.value > 0) return;
  error.value = "";
  busy.value = true;
  try {
    await auth.requestCode(phone.value.trim());
    step.value = "code";
    startCooldown();
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    busy.value = false;
  }
}

async function verify() {
  if (busy.value) return;
  error.value = "";
  busy.value = true;
  try {
    await auth.signIn(phone.value.trim(), code.value.trim());
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/me";
    router.replace(redirect);
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="login">
    <header class="bar">
      <button class="back" :aria-label="t('lg.common.back')" @click="router.back()">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </button>
      <h1>{{ t("lg.auth.loginTitle") }}</h1>
    </header>

    <div class="form">
      <label class="field">
        <span>{{ t("lg.auth.phone") }}</span>
        <input v-model="phone" type="tel" inputmode="tel" :placeholder="t('lg.auth.phoneHint')" :disabled="step === 'code'" />
      </label>

      <button v-if="step === 'phone'" class="send-code primary" :disabled="busy || !phone" @click="sendCode">
        {{ t("lg.auth.sendCode") }}
      </button>

      <template v-else>
        <label class="field">
          <span>{{ t("lg.auth.code") }}</span>
          <input v-model="code" inputmode="numeric" maxlength="6" :placeholder="t('lg.auth.codeSent')" />
        </label>
        <button class="verify primary" :disabled="busy || code.length < 6" @click="verify">
          {{ t("lg.auth.verify") }}
        </button>
        <button class="resend" :disabled="cooldown > 0 || busy" @click="sendCode">
          {{ cooldown > 0 ? t("lg.auth.resendIn", { s: cooldown }) : t("lg.auth.sendCode") }}
        </button>
      </template>

      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<style scoped>
.login { min-height: 100vh; background: var(--bg); }
.bar { display: flex; align-items: center; gap: 8px; padding: 12px 14px; border-bottom: 1px solid var(--border); }
.bar h1 { font-size: 16px; font-weight: 500; }
.back { border: 0; background: transparent; color: var(--text-primary); display: flex; }
.form { padding: 20px 16px; display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-secondary); }
.field input {
  border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px;
  font-size: 15px; background: var(--surface); outline: none;
}
.primary {
  border: 0; border-radius: var(--radius-pill); background: var(--brand-500); color: #fff;
  padding: 11px; font-size: 15px; font-weight: 500;
}
.primary:disabled { opacity: 0.5; }
.resend { border: 0; background: transparent; color: var(--brand-500); font-size: 13px; padding: 4px; }
.resend:disabled { color: var(--text-muted); }
.error { color: #c0392b; font-size: 13px; text-align: center; }
</style>
