<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import type { CountryInfo } from "../api/types";

const props = defineProps<{ country: CountryInfo }>();
const { locale } = useI18n();
const name = computed(() =>
  locale.value === "zh" ? props.country.name_zh : props.country.name_en,
);
</script>

<template>
  <span class="country-tag">
    <span class="flag">{{ country.flag_emoji }}</span>
    <span>{{ name }}</span>
  </span>
</template>

<style scoped>
.country-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: var(--text-muted);
}
.flag {
  font-size: 12px;
  line-height: 1;
}
</style>
