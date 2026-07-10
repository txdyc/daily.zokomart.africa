<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import { useFeedStore } from "../stores/feed";
import NewsCard from "./NewsCard.vue";

const { t } = useI18n();
const feed = useFeedStore();

const listLoading = computed({
  get: () => feed.loading,
  set: (v: boolean) => {
    feed.loading = v;
  },
});
</script>

<template>
  <van-list
    v-model:loading="listLoading"
    :finished="feed.finished"
    :error="!!feed.error"
    :finished-text="feed.items.length ? t('noMore') : ''"
    :error-text="t('loadError')"
    @load="feed.loadMore()"
    @update:error="feed.error = ''"
  >
    <div class="grid">
      <NewsCard v-for="a in feed.items" :key="a.id" :article="a" />
    </div>
    <p v-if="feed.finished && !feed.items.length" class="empty">{{ t("empty") }}</p>
  </van-list>
</template>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding: 12px;
}
.empty {
  text-align: center;
  color: var(--text-muted);
  padding: 40px 0;
  font-size: 13px;
}
</style>
