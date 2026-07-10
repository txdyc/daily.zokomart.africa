<script setup lang="ts">
import { onMounted, ref } from "vue";

import { getBanner } from "../api/articles";
import type { ArticleCard } from "../api/types";
import AppHeader from "../components/AppHeader.vue";
import BannerCarousel from "../components/BannerCarousel.vue";
import NewsGrid from "../components/NewsGrid.vue";
import { useFeedStore } from "../stores/feed";

const feed = useFeedStore();
const banner = ref<ArticleCard[]>([]);
const refreshing = ref(false);

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
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <BannerCarousel v-if="!feed.keyword" :items="banner" />
      <NewsGrid />
    </van-pull-refresh>
  </div>
</template>

<style scoped>
.home {
  min-height: 100vh;
  background: var(--surface);
}
</style>
