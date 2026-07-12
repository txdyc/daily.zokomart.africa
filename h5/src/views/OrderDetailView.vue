<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { cancelOrder, orderDetail } from "../api/lg";
import type { OrderView } from "../api/lgTypes";
import OrderStatusTag from "../components/OrderStatusTag.vue";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const order = ref<OrderView | null>(null);
const error = ref("");
const showCancel = ref(false);
const reason = ref("");
const busy = ref(false);

const cancellable = computed(
  () => order.value != null && ["submitted", "price_confirmed"].includes(order.value.status),
);

onMounted(async () => {
  try {
    order.value = await orderDetail(String(route.params.id));
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  }
});

async function confirmCancel() {
  if (!order.value || busy.value) return;
  busy.value = true;
  try {
    order.value = await cancelOrder(order.value.id, reason.value.trim() || "cancelled by shipper");
    showCancel.value = false;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="page">
    <header class="bar">
      <button class="back" :aria-label="t('lg.common.back')" @click="router.push('/me/orders')">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6" /></svg>
      </button>
      <h1>{{ t("lg.orders.detailTitle") }}</h1>
    </header>

    <p v-if="error" class="state">{{ error }}</p>

    <template v-else-if="order">
      <section class="head">
        <div class="lane">{{ order.origin_town }} → {{ order.dest_town }}</div>
        <OrderStatusTag :status="order.status" />
      </section>

      <section class="block">
        <h2>{{ t("lg.orders.cargo") }}</h2>
        <p>{{ order.cargo_name }} · {{ order.pieces }} · {{ order.weight_kg }}kg · {{ order.volume_m3 }}m³</p>
        <p class="sub">{{ order.pickup_town }} → {{ order.delivery_town }}</p>
      </section>

      <section class="block">
        <h2>{{ t("lg.orders.trip") }}</h2>
        <p>{{ order.depart_date }} {{ order.depart_time }}</p>
        <p v-if="order.freight_ghs != null" class="sub">{{ t("lg.orders.freight") }}: GHS {{ order.freight_ghs }}</p>
        <p v-if="order.pickup_time" class="sub">{{ t("lg.orders.pickupTime") }}: {{ order.pickup_time }}</p>
      </section>

      <section class="block">
        <h2>{{ t("lg.orders.driver") }}</h2>
        <template v-if="order.driver">
          <p>{{ order.driver.full_name }}</p>
          <p class="sub">{{ t("lg.orders.plate") }}: {{ order.driver.plate_number }}</p>
          <p class="sub">{{ t("lg.orders.phone") }}: <a :href="`tel:${order.driver.phone}`">{{ order.driver.phone }}</a></p>
        </template>
        <p v-else class="hint">{{ t("lg.orders.contactHidden") }}</p>
      </section>

      <button v-if="cancellable" class="cancel" @click="showCancel = true">{{ t("lg.orders.cancel") }}</button>

      <div v-if="showCancel" class="sheet">
        <p>{{ t("lg.orders.cancelConfirm") }}</p>
        <input v-model="reason" :placeholder="t('lg.orders.cancelReason')" />
        <div class="sheet-actions">
          <button class="ghost" @click="showCancel = false">{{ t("lg.common.back") }}</button>
          <button class="confirm-cancel" :disabled="busy" @click="confirmCancel">{{ t("lg.orders.cancel") }}</button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; background: var(--surface); }
.bar { display: flex; align-items: center; gap: 8px; padding: 12px 14px; background: var(--bg); border-bottom: 1px solid var(--border); }
.bar h1 { font-size: 16px; font-weight: 500; }
.back { border: 0; background: transparent; color: var(--text-primary); display: flex; }
.state { padding: 60px 20px; text-align: center; color: var(--text-muted); }
.head { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; background: var(--bg); margin-bottom: 8px; }
.lane { font-size: 17px; font-weight: 600; color: var(--brand-700); }
.block { background: var(--bg); padding: 12px 16px; margin-bottom: 8px; }
.block h2 { font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted); margin-bottom: 6px; }
.block p { font-size: 14px; }
.sub { font-size: 12.5px; color: var(--text-secondary); margin-top: 2px; }
.hint { font-size: 12.5px; color: var(--text-muted); font-style: italic; }
.cancel { display: block; width: calc(100% - 24px); margin: 16px 12px; border: 1px solid #d9534f; color: #c0392b; background: var(--bg); border-radius: var(--radius-pill); padding: 11px; font-size: 14px; }
.sheet { position: fixed; left: 0; right: 0; bottom: 0; background: var(--bg); border-top: 1px solid var(--border); padding: 16px; }
.sheet input { width: 100%; border: 1px solid var(--border); border-radius: 8px; padding: 10px; margin: 10px 0; font-size: 14px; }
.sheet-actions { display: flex; gap: 10px; }
.ghost { flex: 1; border: 1px solid var(--border); background: var(--bg); border-radius: var(--radius-pill); padding: 10px; }
.confirm-cancel { flex: 1; border: 0; background: #c0392b; color: #fff; border-radius: var(--radius-pill); padding: 10px; }
</style>
