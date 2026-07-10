<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { getArticle } from "../api/articles";
import type { ArticleDetail, ContentMode } from "../api/types";
import ArticleBody from "../components/ArticleBody.vue";
import ContentLangToggle from "../components/ContentLangToggle.vue";
import CountryTag from "../components/CountryTag.vue";
import ShareSheet from "../components/ShareSheet.vue";

const route = useRoute();
const router = useRouter();
const { t } = useI18n();

const article = ref<ArticleDetail | null>(null);
const error = ref("");
const mode = ref<ContentMode>("source");
const showShare = ref(false);
const imgFailed = ref(false);

const hasTranslation = computed(
  () => !!article.value?.paragraphs_zh && !!article.value?.title_zh,
);
const categoryLabel = computed(() => {
  const c = article.value?.category;
  return c ? t(`categories.${c}`) : "";
});
const dateLabel = computed(() =>
  article.value?.published_at ? article.value.published_at.slice(0, 10) : "",
);
const showSourceTitle = computed(() => mode.value !== "zh");
const showZhTitle = computed(
  () => hasTranslation.value && mode.value !== "source",
);

function goBack() {
  if (window.history.length > 1) router.back();
  else router.push("/");
}

onMounted(async () => {
  try {
    article.value = await getArticle(String(route.params.id));
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  }
});
</script>

<template>
  <div class="detail">
    <header class="bar hairline">
      <button type="button" class="back" :aria-label="t('back')" @click="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </button>
      <span v-if="article" class="crumb">
        <CountryTag :country="article.country" />
        <span v-if="categoryLabel"> · {{ categoryLabel }}</span>
      </span>
      <span class="spacer" />
      <button type="button" class="share" :aria-label="t('share')" @click="showShare = true">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="6" cy="12" r="2.5" /><circle cx="17" cy="6" r="2.5" /><circle cx="17" cy="18" r="2.5" />
          <path d="M8.2 10.8l6.6-3.6M8.2 13.2l6.6 3.6" />
        </svg>
      </button>
    </header>

    <div v-if="error" class="state">
      <p>{{ t("notFound") }}</p>
      <button type="button" class="retry" @click="goBack">{{ t("back") }}</button>
    </div>

    <template v-else-if="article">
      <div class="hero">
        <img
          v-if="article.main_image_url && !imgFailed"
          :src="article.main_image_url"
          alt=""
          @error="imgFailed = true"
        />
        <ContentLangToggle
          v-model="mode"
          class="toggle"
          :source-lang="article.source_language"
          :has-translation="hasTranslation"
        />
      </div>

      <div class="content">
        <p class="meta">
          <CountryTag :country="article.country" />
          <span v-if="categoryLabel"> · {{ categoryLabel }}</span>
          <span v-if="dateLabel"> · {{ dateLabel }}</span>
        </p>
        <h1 v-if="showSourceTitle" class="title">{{ article.title }}</h1>
        <h2 v-if="showZhTitle" class="title-zh">{{ article.title_zh }}</h2>
        <p class="source-line">
          {{ t("source") }}
          <a :href="article.site.url" target="_blank" rel="noopener">{{ article.site.name }}</a>
        </p>
        <ArticleBody
          :paragraphs="article.paragraphs"
          :paragraphs-zh="article.paragraphs_zh"
          :mode="mode"
        />
      </div>

      <ShareSheet v-model:show="showShare" :title="article.title" />
    </template>
  </div>
</template>

<style scoped>
.detail {
  min-height: 100vh;
  background: var(--bg);
}
.bar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  background: var(--bg);
}
.back,
.share {
  border: 0;
  background: transparent;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  min-width: 40px;
  min-height: 24px;
}
.crumb {
  font-size: 12.5px;
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
}
.spacer {
  flex: 1;
}
.hero {
  position: relative;
  background: var(--brand-700);
  min-height: 120px;
}
.hero img {
  width: 100%;
  max-height: 240px;
  object-fit: cover;
}
.toggle {
  position: absolute;
  top: 8px;
  right: 8px;
}
.content {
  padding: 12px 14px 24px;
}
.meta {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
  display: flex;
  align-items: center;
}
.title {
  font-size: 17px;
  font-weight: 500;
  line-height: 1.45;
  margin-bottom: 4px;
}
.title-zh {
  font-size: 15px;
  font-weight: 500;
  line-height: 1.45;
  color: var(--text-secondary);
  margin-bottom: 4px;
}
.source-line {
  font-size: 12px;
  margin: 6px 0 14px;
}
.source-line a {
  color: var(--brand-500);
}
.state {
  padding: 80px 20px;
  text-align: center;
  color: var(--text-muted);
}
.retry {
  margin-top: 12px;
  border: 1px solid var(--border);
  background: var(--bg);
  border-radius: var(--radius-pill);
  padding: 6px 20px;
  font-size: 13px;
}
</style>
