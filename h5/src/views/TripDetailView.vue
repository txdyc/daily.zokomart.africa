<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { routeDetail } from "../api/lg";
import type { RouteDetail } from "../api/lgTypes";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const detail = ref<RouteDetail | null>(null);
const error = ref("");

onMounted(async () => {
  try {
    const routeId = typeof route.query.route === "string" ? route.query.route : route.params.id;
    detail.value = await routeDetail(routeId);
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  }
});

function book(tripId: number) {
  router.push(`/lg/order/new/${tripId}`);
}
</script>

<template>
  <div class="detail">
    <header class="bar">
      <button class="back" :aria-label="t('lg.common.back')" @click="router.back()">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </button>
    </header>

    <p v-if="error" class="state">{{ error }}</p>

    <template v-else-if="detail">
      <section class="lane-box">
        <div class="lane">
          <span>{{ detail.origin_town }}</span>
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
          <span>{{ detail.dest_town }}</span>
        </div>
        <p v-if="detail.via_towns.length" class="via">via {{ detail.via_towns.join(", ") }}</p>
        <p class="price">
          <template v-if="detail.negotiable">{{ t("lg.browse.negotiable") }}</template>
          <template v-else>
            <span v-if="detail.rate_per_ton">GHS {{ detail.rate_per_ton }}{{ t("lg.browse.perTon") }}</span>
            <span v-if="detail.rate_per_m3"> · GHS {{ detail.rate_per_m3 }}{{ t("lg.browse.perM3") }}</span>
          </template>
        </p>
      </section>

      <section class="veh">
        <h2>{{ detail.vehicle.vehicle_type }} · {{ detail.vehicle.brand_model }}</h2>
        <p>{{ detail.vehicle.max_load_kg }}kg · {{ detail.vehicle.max_volume_m3 }}m³</p>
      </section>

      <section class="trips">
        <div v-for="tr in detail.upcoming_trips" :key="tr.trip_id" class="trip-row">
          <div>
            <p class="d">{{ tr.depart_date }} {{ tr.depart_time }}</p>
            <p class="r">{{ t("lg.browse.remaining") }} {{ tr.remaining_load_kg }}kg · {{ tr.remaining_volume_m3 }}m³</p>
          </div>
          <button class="book" @click="book(tr.trip_id)">{{ t("lg.browse.book") }}</button>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.detail { min-height: 100vh; background: var(--surface); }
.bar { padding: 12px 14px; background: var(--bg); }
.back { border: 0; background: transparent; color: var(--text-primary); display: flex; }
.state { padding: 60px 20px; text-align: center; color: var(--text-muted); }
.lane-box { background: var(--bg); padding: 16px; margin-bottom: 8px; }
.lane { display: flex; align-items: center; gap: 8px; font-size: 19px; font-weight: 600; color: var(--brand-700); }
.via { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
.price { margin-top: 8px; font-size: 14px; font-weight: 600; color: var(--brand-500); }
.veh { background: var(--bg); padding: 14px 16px; margin-bottom: 8px; }
.veh h2 { font-size: 14px; font-weight: 500; }
.veh p { font-size: 12.5px; color: var(--text-secondary); margin-top: 2px; }
.trips { background: var(--bg); }
.trip-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border); }
.trip-row .d { font-size: 14px; font-weight: 500; }
.trip-row .r { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }
.book { border: 0; border-radius: var(--radius-pill); background: var(--brand-500); color: #fff; padding: 8px 16px; font-size: 13px; }
</style>
