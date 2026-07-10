<script setup lang="ts">
import QRCode from "qrcode";
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps<{ show: boolean; title: string }>();
const emit = defineEmits<{ "update:show": [boolean] }>();
const { t } = useI18n();

const wechatPane = ref(false);
const qrDataUrl = ref("");
const copied = ref(false);
const canSystemShare = typeof navigator !== "undefined" && "share" in navigator;

const pageUrl = () => window.location.href;

function openFacebook() {
  window.open(
    `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(pageUrl())}`,
    "_blank",
  );
}

function openWhatsApp() {
  window.open(
    `https://wa.me/?text=${encodeURIComponent(`${props.title} ${pageUrl()}`)}`,
    "_blank",
  );
}

async function openWeChat() {
  qrDataUrl.value = await QRCode.toDataURL(pageUrl(), { margin: 1, width: 180 });
  wechatPane.value = true;
}

async function copyLink() {
  try {
    await navigator.clipboard.writeText(pageUrl());
  } catch {
    const ta = document.createElement("textarea");
    ta.value = pageUrl();
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  copied.value = true;
  setTimeout(() => (copied.value = false), 1500);
}

function systemShare() {
  navigator.share?.({ title: props.title, url: pageUrl() });
}

watch(
  () => props.show,
  (open) => {
    if (!open) wechatPane.value = false;
  },
);
</script>

<template>
  <van-popup
    :show="show"
    position="bottom"
    round
    @update:show="(v: boolean) => emit('update:show', v)"
  >
    <div class="sheet">
      <template v-if="!wechatPane">
        <p class="sheet-title">{{ t("share") }}</p>
        <div class="row">
          <button type="button" class="item" @click="openFacebook">Facebook</button>
          <button type="button" class="item" @click="openWhatsApp">WhatsApp</button>
          <button type="button" class="item" @click="openWeChat">{{ t("wechat") }}</button>
          <button type="button" class="item" @click="copyLink">
            {{ copied ? t("copied") : t("copyLink") }}
          </button>
          <button v-if="canSystemShare" type="button" class="item" @click="systemShare">
            {{ t("systemShare") }}
          </button>
        </div>
      </template>
      <template v-else>
        <p class="sheet-title">{{ t("wechatHint") }}</p>
        <img v-if="qrDataUrl" :src="qrDataUrl" alt="QR" class="qr" />
        <button type="button" class="item wide" @click="copyLink">
          {{ copied ? t("copied") : t("copyLink") }}
        </button>
      </template>
    </div>
  </van-popup>
</template>

<style scoped>
.sheet {
  padding: 16px 16px 28px;
  text-align: center;
}
.sheet-title {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 14px;
}
.row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}
.item {
  border: 1px solid var(--border);
  background: var(--bg);
  border-radius: var(--radius-card);
  padding: 10px 14px;
  font-size: 13px;
  min-height: 40px;
}
.item.wide {
  margin-top: 12px;
}
.qr {
  margin: 0 auto 4px;
  width: 180px;
  height: 180px;
}
</style>
