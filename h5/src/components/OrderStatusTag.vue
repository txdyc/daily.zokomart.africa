<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps<{ status: string }>();
const { t } = useI18n();

const tone = computed(() => {
  if (["completed"].includes(props.status)) return "done";
  if (["cancelled", "exception_closed"].includes(props.status)) return "closed";
  if (["submitted"].includes(props.status)) return "new";
  return "active";
});
</script>

<template>
  <span class="status" :class="tone">{{ t(`lg.orders.status.${status}`) }}</span>
</template>

<style scoped>
.status { font-size: 11px; padding: 3px 8px; border-radius: var(--radius-pill); font-weight: 500; }
.new { background: var(--brand-50); color: var(--brand-700); }
.active { background: #fef3e0; color: #b26a00; }
.done { background: #e3f4ec; color: #1d7a52; }
.closed { background: #f0efec; color: var(--text-muted); }
</style>
