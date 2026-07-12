<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import { getBanner } from "../api/articles";
import type { ArticleCard } from "../api/types";
import AppHeader from "../components/AppHeader.vue";
import BannerCarousel from "../components/BannerCarousel.vue";
import NewsGrid from "../components/NewsGrid.vue";
import TabBar from "../components/TabBar.vue";
import { useFeedStore } from "../stores/feed";

const { t } = useI18n();
const feed = useFeedStore();
const banner = ref<ArticleCard[]>([]);
const refreshing = ref(false);
const activeTab = ref("all");

const tabs = computed(() => [
  { code: "all", label: t("allCountries") },
  { code: "GH", label: t("countries.GH") },
  { code: "NG", label: t("countries.NG") },
  { code: "CI", label: t("countries.CI") },
  { code: "SN", label: t("countries.SN") },
]);

watch(activeTab, (val) => {
  feed.setCountry(val === "all" ? "" : val);
});

async function loadBanner() {
  try {
    banner.value = await getBanner();
  } catch {
    banner.value = [];
  }
}

async function onRefresh() {
  await Promise.all([loadBanner(), feed.refresh()]);
  refreshing.value = false;
}

function onSearch(keyword: string) {
  feed.search(keyword);
}

onMounted(() => {
  loadBanner();
  if (!feed.items.length) feed.refresh();
});
</script>

<template>
  <div class="home">
    <AppHeader @search="onSearch" />
    <BannerCarousel v-if="!feed.keyword && !feed.country" :items="banner" />
    <div class="country-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.code"
        class="tab"
        :class="{ active: activeTab === tab.code }"
        @click="activeTab = tab.code"
      >
        {{ tab.label }}
      </button>
    </div>
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <NewsGrid />
    </van-pull-refresh>
    <TabBar />
  </div>
</template>

<style scoped>
.home {
  min-height: 100vh;
  background: var(--surface);
  padding-bottom: 64px;
}
.country-tabs {
  display: flex;
  gap: 0;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  position: sticky;
  top: 0;
  z-index: 10;
}
.tab {
  flex: 1 0 auto;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.2s, border-color 0.2s;
}
.tab.active {
  color: var(--brand-700);
  border-bottom-color: var(--brand-500);
}
</style>
