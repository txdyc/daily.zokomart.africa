<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { myOrders } from "../api/lg";
import type { OrderView } from "../api/lgTypes";
import OrderStatusTag from "../components/OrderStatusTag.vue";

const { t } = useI18n();
const router = useRouter();

const orders = ref<OrderView[]>([]);
const loaded = ref(false);

onMounted(async () => {
  try {
    orders.value = (await myOrders(1)).items;
  } finally {
    loaded.value = true;
  }
});
</script>

<template>
  <div class="page">
    <header class="bar">
      <button class="back" :aria-label="t('lg.common.back')" @click="router.push('/me')">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6" /></svg>
      </button>
      <h1>{{ t("lg.orders.mineTitle") }}</h1>
    </header>

    <p v-if="loaded && !orders.length" class="empty">{{ t("lg.orders.empty") }}</p>

    <RouterLink v-for="o in orders" :key="o.id" class="row" :to="`/me/orders/${o.id}`">
      <div class="top">
        <span class="lane">{{ o.origin_town }} → {{ o.dest_town }}</span>
        <OrderStatusTag :status="o.status" />
      </div>
      <p class="cargo">{{ o.cargo_name }} · {{ o.weight_kg }}kg · {{ o.volume_m3 }}m³</p>
      <p class="when">{{ o.depart_date }} {{ o.depart_time }}</p>
    </RouterLink>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; background: var(--surface); }
.bar { display: flex; align-items: center; gap: 8px; padding: 12px 14px; background: var(--bg); border-bottom: 1px solid var(--border); }
.bar h1 { font-size: 16px; font-weight: 500; }
.back { border: 0; background: transparent; color: var(--text-primary); display: flex; }
.empty { text-align: center; color: var(--text-muted); padding: 60px 0; font-size: 13px; }
.row { display: block; background: var(--bg); padding: 12px 16px; border-bottom: 1px solid var(--border); text-decoration: none; color: var(--text-primary); }
.top { display: flex; justify-content: space-between; align-items: center; }
.lane { font-size: 15px; font-weight: 600; color: var(--brand-700); }
.cargo { font-size: 12.5px; color: var(--text-secondary); margin-top: 4px; }
.when { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
</style>
