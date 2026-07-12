<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";

import TabBar from "../components/TabBar.vue";
import TripCard from "../components/TripCard.vue";
import { useLgFeedStore } from "../stores/lgFeed";

const { t } = useI18n();
const feed = useLgFeedStore();

const listLoading = computed({
  get: () => feed.loading,
  set: (v: boolean) => (feed.loading = v),
});

function applyFilters() {
  feed.refresh();
}
function clearFilters() {
  feed.filters.origin_town = "";
  feed.filters.dest_town = "";
  feed.filters.date = "";
  feed.refresh();
}

onMounted(() => {
  if (!feed.items.length) feed.refresh();
});
</script>

<template>
  <div class="page">
    <header class="filters">
      <h1>{{ t("lg.browse.title") }}</h1>
      <div class="row">
        <input v-model="feed.filters.origin_town" :placeholder="t('lg.browse.from')" @keyup.enter="applyFilters" />
        <input v-model="feed.filters.dest_town" :placeholder="t('lg.browse.to')" @keyup.enter="applyFilters" />
      </div>
      <div class="row">
        <input v-model="feed.filters.date" type="date" :aria-label="t('lg.browse.date')" />
        <button class="search" @click="applyFilters">{{ t("lg.browse.search") }}</button>
        <button class="clear" @click="clearFilters">{{ t("lg.browse.clear") }}</button>
      </div>
    </header>

    <van-list
      v-model:loading="listLoading"
      :finished="feed.finished"
      finished-text=""
      @load="feed.loadMore()"
    >
      <TripCard v-for="tr in feed.items" :key="tr.trip_id" :trip="tr" />
      <p v-if="feed.finished && !feed.items.length" class="empty">{{ t("lg.browse.empty") }}</p>
    </van-list>

    <TabBar />
  </div>
</template>

<style scoped>
.page { min-height: 100vh; background: var(--surface); padding-bottom: 64px; }
.filters { background: var(--bg); padding: 14px 12px 12px; border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10; }
.filters h1 { font-size: 16px; font-weight: 600; margin-bottom: 10px; }
.row { display: flex; gap: 8px; margin-bottom: 8px; }
.row input { flex: 1; min-width: 0; border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; font-size: 13.5px; background: var(--surface); outline: none; }
.search { border: 0; border-radius: 8px; background: var(--brand-500); color: #fff; padding: 8px 16px; font-size: 13px; }
.clear { border: 1px solid var(--border); border-radius: 8px; background: var(--bg); color: var(--text-secondary); padding: 8px 12px; font-size: 13px; }
.empty { text-align: center; color: var(--text-muted); padding: 50px 0; font-size: 13px; }
</style>
