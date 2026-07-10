<script setup lang="ts">
import type { ContentMode } from "../api/types";

defineProps<{
  paragraphs: string[];
  paragraphsZh: string[] | null;
  mode: ContentMode;
}>();
</script>

<template>
  <div class="article-body">
    <template v-if="mode === 'zh' && paragraphsZh">
      <p v-for="(p, i) in paragraphsZh" :key="`zh-${i}`" class="para">{{ p }}</p>
    </template>
    <template v-else-if="mode === 'bilingual' && paragraphsZh">
      <template v-for="(p, i) in paragraphs" :key="`bl-${i}`">
        <p class="para">{{ p }}</p>
        <p class="para zh-trans">{{ paragraphsZh[i] }}</p>
      </template>
    </template>
    <template v-else>
      <p v-for="(p, i) in paragraphs" :key="`src-${i}`" class="para">{{ p }}</p>
    </template>
  </div>
</template>

<style scoped>
.para {
  font-size: 15px;
  line-height: 1.65;
  margin-bottom: 12px;
}
.zh-trans {
  color: var(--text-secondary);
  border-left: 2px solid var(--border);
  border-radius: 0;
  padding-left: 8px;
}
</style>
