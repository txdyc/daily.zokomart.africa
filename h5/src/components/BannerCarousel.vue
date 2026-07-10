<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import type { ArticleCard } from "../api/types";
import { usePrefsStore } from "../stores/prefs";

const props = defineProps<{ items: ArticleCard[] }>();
const router = useRouter();
const prefs = usePrefsStore();
const current = ref(0);

const headlines = computed(() =>
  props.items.map((a) =>
    prefs.uiLang === "zh" ? a.title_zh || a.title : a.title,
  ),
);

function open(a: ArticleCard) {
  router.push(`/article/${a.id}`);
}
</script>

<template>
  <van-swipe
    v-if="items.length"
    class="banner"
    :autoplay="5000"
    :show-indicators="false"
    @change="(i: number) => (current = i)"
  >
    <van-swipe-item v-for="(a, i) in items" :key="a.id" @click="open(a)">
      <div class="slide">
        <img v-if="a.main_image_url" :src="a.main_image_url" alt="" />
        <div class="scrim">
          <p class="headline">{{ headlines[i] }}</p>
          <div class="dashes">
            <span
              v-for="(_, d) in items"
              :key="d"
              class="dash"
              :class="{ active: d === current }"
            />
          </div>
        </div>
      </div>
    </van-swipe-item>
  </van-swipe>
</template>

<style scoped>
.banner {
  height: 40vw;
  max-height: 220px;
}
.slide {
  position: relative;
  width: 100%;
  height: 100%;
  background: var(--brand-700);
  overflow: hidden;
}
.slide img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.scrim {
  position: absolute;
  inset: auto 0 0 0;
  padding: 24px 12px 10px;
  background: linear-gradient(transparent, rgba(8, 80, 65, 0.85));
}
.headline {
  color: var(--brand-50);
  font-size: 14px;
  font-weight: 500;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.dashes {
  display: flex;
  gap: 4px;
  margin-top: 8px;
}
.dash {
  width: 6px;
  height: 3px;
  border-radius: 2px;
  background: var(--brand-700);
  transition: width 0.2s;
}
.dash.active {
  width: 14px;
  background: var(--brand-200);
}
</style>
