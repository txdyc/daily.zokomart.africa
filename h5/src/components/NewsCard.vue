<script setup lang="ts">
import { computed, ref } from "vue";

import type { ArticleCard } from "../api/types";
import { usePrefsStore } from "../stores/prefs";
import CountryTag from "./CountryTag.vue";

const props = defineProps<{ article: ArticleCard }>();
const prefs = usePrefsStore();
const imgFailed = ref(false);

const headline = computed(() =>
  prefs.uiLang === "zh"
    ? props.article.title_zh || props.article.title
    : props.article.title,
);
const dateLabel = computed(() =>
  props.article.published_at ? props.article.published_at.slice(5, 10) : "",
);
</script>

<template>
  <router-link :to="`/article/${article.id}`" class="card">
    <div class="thumb">
      <img
        v-if="article.main_image_url && !imgFailed"
        :src="article.main_image_url"
        alt=""
        loading="lazy"
        @error="imgFailed = true"
      />
      <div v-else class="thumb-placeholder" />
    </div>
    <div class="body">
      <h3 class="headline">{{ headline }}</h3>
      <p class="meta">
        <CountryTag :country="article.country" />
        <span class="date">{{ dateLabel }}</span>
      </p>
    </div>
  </router-link>
</template>

<style scoped>
.card {
  display: block;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  overflow: hidden;
}
.thumb {
  aspect-ratio: 16 / 10;
  background: var(--surface);
}
.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.thumb-placeholder {
  width: 100%;
  height: 100%;
  background: var(--surface);
}
.body {
  padding: 8px;
}
.headline {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 6px;
}
.meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-muted);
}
</style>
