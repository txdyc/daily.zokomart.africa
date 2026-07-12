<script setup lang="ts">
import { useI18n } from "vue-i18n";

import type { TripCard } from "../api/lgTypes";

defineProps<{ trip: TripCard }>();
const { t } = useI18n();
</script>

<template>
  <RouterLink class="card" :to="`/lg/trip/${trip.trip_id}?route=${trip.route_id}`">
    <div class="lane">
      <span class="town">{{ trip.origin_town }}</span>
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M5 12h14M13 6l6 6-6 6" />
      </svg>
      <span class="town">{{ trip.dest_town }}</span>
    </div>
    <p class="when">{{ t("lg.browse.departs") }} {{ trip.depart_date }} {{ trip.depart_time }} · {{ t("lg.browse.duration", { h: trip.est_duration_hours }) }}</p>
    <div class="meta">
      <span class="cap">{{ t("lg.browse.remaining") }} {{ trip.remaining_load_kg }}kg · {{ trip.remaining_volume_m3 }}m³</span>
      <span class="price">
        <template v-if="trip.negotiable">{{ t("lg.browse.negotiable") }}</template>
        <template v-else-if="trip.rate_per_ton">GHS {{ trip.rate_per_ton }}{{ t("lg.browse.perTon") }}</template>
        <template v-else-if="trip.rate_per_m3">GHS {{ trip.rate_per_m3 }}{{ t("lg.browse.perM3") }}</template>
      </span>
    </div>
    <p class="veh">{{ trip.vehicle_type }} · {{ trip.brand_model }}</p>
  </RouterLink>
</template>

<style scoped>
.card { display: block; background: var(--bg); border-radius: var(--radius-card); padding: 12px 14px; margin: 8px 12px; text-decoration: none; color: var(--text-primary); border: 1px solid var(--border); }
.lane { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; color: var(--brand-700); }
.when { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
.meta { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }
.cap { font-size: 12.5px; color: var(--text-secondary); }
.price { font-size: 13px; font-weight: 600; color: var(--brand-500); }
.veh { font-size: 11.5px; color: var(--text-muted); margin-top: 4px; }
</style>
