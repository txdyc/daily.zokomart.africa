<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";

const { t } = useI18n();
const route = useRoute();

const tabs = computed(() => [
  { name: "news", to: "/", label: t("lg.tabs.news"), icon: "M4 10l8-6 8 6v9a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1z" },
  { name: "logistics", to: "/lg", label: t("lg.tabs.logistics"), icon: "M3 7h10v7H3zM13 10h4l3 3v1h-7zM7 18a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM17 18a2 2 0 1 0 0-4 2 2 0 0 0 0 4z" },
  { name: "me", to: "/me", label: t("lg.tabs.me"), icon: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 20a8 8 0 0 1 16 0z" },
]);

const activeRoot = computed(() => {
  const p = route.path;
  if (p === "/" || p.startsWith("/article")) return "news";
  if (p.startsWith("/lg")) return "logistics";
  return "me";
});
</script>

<template>
  <nav class="tabbar">
    <RouterLink
      v-for="tab in tabs"
      :key="tab.name"
      class="tab"
      :class="{ active: activeRoot === tab.name }"
      :to="tab.to"
    >
      <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
        <path :d="tab.icon" />
      </svg>
      <span>{{ tab.label }}</span>
    </RouterLink>
  </nav>
</template>

<style scoped>
.tabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 20;
  display: flex;
  background: var(--bg);
  border-top: 1px solid var(--border);
  padding-bottom: env(safe-area-inset-bottom, 0);
}
.tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 7px 0;
  font-size: 11px;
  color: var(--text-muted);
  text-decoration: none;
}
.tab.active {
  color: var(--brand-500);
}
</style>
