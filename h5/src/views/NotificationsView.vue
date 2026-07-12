<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { listNotifications, markNotificationRead } from "../api/lg";
import type { NotificationItem } from "../api/lgTypes";

const { t } = useI18n();
const router = useRouter();

const items = ref<NotificationItem[]>([]);
const loaded = ref(false);

onMounted(async () => {
  try {
    items.value = (await listNotifications(1)).items;
  } finally {
    loaded.value = true;
  }
});

async function open(n: NotificationItem) {
  if (n.read) return;
  await markNotificationRead(n.id);
  n.read = true;
}
</script>

<template>
  <div class="page">
    <header class="bar">
      <button class="back" :aria-label="t('lg.common.back')" @click="router.push('/me')">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6" /></svg>
      </button>
      <h1>{{ t("lg.notif.title") }}</h1>
    </header>

    <p v-if="loaded && !items.length" class="empty">{{ t("lg.notif.empty") }}</p>

    <button v-for="n in items" :key="n.id" class="notif" :class="{ unread: !n.read }" @click="open(n)">
      <span v-if="!n.read" class="dot" />
      <span class="body">
        <span class="title">{{ n.title }}</span>
        <span v-if="n.body" class="text">{{ n.body }}</span>
        <span class="time">{{ n.created_at.slice(0, 16).replace("T", " ") }}</span>
      </span>
    </button>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; background: var(--surface); }
.bar { display: flex; align-items: center; gap: 8px; padding: 12px 14px; background: var(--bg); border-bottom: 1px solid var(--border); }
.bar h1 { font-size: 16px; font-weight: 500; }
.back { border: 0; background: transparent; color: var(--text-primary); display: flex; }
.empty { text-align: center; color: var(--text-muted); padding: 60px 0; font-size: 13px; }
.notif { display: flex; gap: 10px; width: 100%; text-align: left; background: var(--bg); border: 0; border-bottom: 1px solid var(--border); padding: 14px 16px; }
.notif.unread { background: var(--brand-50); }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--brand-500); margin-top: 6px; flex: none; }
.body { display: flex; flex-direction: column; gap: 3px; }
.title { font-size: 14px; font-weight: 500; color: var(--text-primary); }
.text { font-size: 12.5px; color: var(--text-secondary); }
.time { font-size: 11px; color: var(--text-muted); }
</style>
