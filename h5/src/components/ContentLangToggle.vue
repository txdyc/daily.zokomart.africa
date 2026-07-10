<script setup lang="ts">
import { computed } from "vue";

import type { ContentMode } from "../api/types";

const props = defineProps<{
  sourceLang: "en" | "fr";
  modelValue: ContentMode;
  hasTranslation: boolean;
}>();
const emit = defineEmits<{ "update:modelValue": [ContentMode] }>();

const segments = computed(() => {
  const base: { key: ContentMode; label: string }[] = [
    { key: "source", label: props.sourceLang.toUpperCase() },
  ];
  if (props.hasTranslation) {
    base.push({ key: "zh", label: "中" }, { key: "bilingual", label: "双语" });
  }
  return base;
});
</script>

<template>
  <div class="toggle">
    <button
      v-for="seg in segments"
      :key="seg.key"
      type="button"
      class="seg"
      :class="{ active: seg.key === modelValue }"
      @click="emit('update:modelValue', seg.key)"
    >
      {{ seg.label }}
    </button>
  </div>
</template>

<style scoped>
.toggle {
  display: inline-flex;
  background: var(--brand-900);
  border-radius: var(--radius-pill);
  padding: 2px;
}
.seg {
  border: 0;
  background: transparent;
  color: var(--brand-200);
  font-size: 11px;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  min-height: 24px;
}
.seg.active {
  background: var(--brand-50);
  color: var(--brand-900);
  font-weight: 500;
}
</style>
