<script setup lang="ts">
import { reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { submitOrder } from "../api/lg";
import type { OrderDraft } from "../api/lgTypes";
import ImageUpload from "../components/ImageUpload.vue";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const tripId = Number(route.params.tripId);
const packagingOptions = ["carton", "pallet", "bag", "drum", "loose", "other"];

const draft = reactive<OrderDraft>({
  trip_id: tripId,
  contact_name: "",
  contact_phone: "",
  pickup_region: "",
  pickup_town: "",
  pickup_details: "",
  delivery_region: "",
  delivery_town: "",
  delivery_details: "",
  consignee_name: "",
  consignee_phone: "",
  cargo_name: "",
  cargo_category: "general",
  packaging: "carton",
  pieces: 0,
  weight_kg: 0,
  volume_m3: 0,
  fragile: false,
  needs_loading: false,
  needs_pickup: false,
  pickup_window: "",
  remarks: "",
  photo_ids: [],
});

const error = ref("");
const busy = ref(false);

const REQUIRED: (keyof OrderDraft)[] = [
  "contact_name", "contact_phone", "pickup_town", "delivery_town",
  "consignee_name", "consignee_phone", "cargo_name", "pickup_window",
];

function valid(): boolean {
  for (const f of REQUIRED) {
    if (!String(draft[f]).trim()) return false;
  }
  return draft.pieces > 0 && draft.weight_kg > 0 && draft.volume_m3 > 0;
}

async function submit() {
  error.value = "";
  if (!valid()) {
    error.value = t("lg.common.required");
    return;
  }
  busy.value = true;
  try {
    await submitOrder({ ...draft });
    router.replace("/me/orders");
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    error.value = /capacity/i.test(msg) ? t("lg.order.overCapacity") : msg;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="form-page">
    <header class="bar">
      <button class="back" :aria-label="t('lg.common.back')" @click="router.back()">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6" /></svg>
      </button>
      <h1>{{ t("lg.order.title") }}</h1>
    </header>

    <form @submit.prevent="submit">
      <fieldset>
        <legend>{{ t("lg.order.contact") }}</legend>
        <input name="contact_name" v-model="draft.contact_name" :placeholder="t('lg.order.contactName')" />
        <input name="contact_phone" v-model="draft.contact_phone" type="tel" :placeholder="t('lg.order.contactPhone')" />
      </fieldset>

      <fieldset>
        <legend>{{ t("lg.order.pickup") }}</legend>
        <input name="pickup_region" v-model="draft.pickup_region" :placeholder="t('lg.order.region')" />
        <input name="pickup_town" v-model="draft.pickup_town" :placeholder="t('lg.order.town')" />
        <input name="pickup_details" v-model="draft.pickup_details" :placeholder="t('lg.order.addressDetails')" />
      </fieldset>

      <fieldset>
        <legend>{{ t("lg.order.delivery") }}</legend>
        <input name="delivery_region" v-model="draft.delivery_region" :placeholder="t('lg.order.region')" />
        <input name="delivery_town" v-model="draft.delivery_town" :placeholder="t('lg.order.town')" />
        <input name="delivery_details" v-model="draft.delivery_details" :placeholder="t('lg.order.addressDetails')" />
        <input name="consignee_name" v-model="draft.consignee_name" :placeholder="t('lg.order.consigneeName')" />
        <input name="consignee_phone" v-model="draft.consignee_phone" type="tel" :placeholder="t('lg.order.consigneePhone')" />
      </fieldset>

      <fieldset>
        <legend>{{ t("lg.order.cargo") }}</legend>
        <input name="cargo_name" v-model="draft.cargo_name" :placeholder="t('lg.order.cargoName')" />
        <input name="cargo_category" v-model="draft.cargo_category" :placeholder="t('lg.order.category')" />
        <select v-model="draft.packaging" :aria-label="t('lg.order.packaging')">
          <option v-for="p in packagingOptions" :key="p" :value="p">{{ t(`lg.order.packagingOptions.${p}`) }}</option>
        </select>
        <div class="triple">
          <input name="pieces" v-model.number="draft.pieces" type="number" min="1" :placeholder="t('lg.order.pieces')" />
          <input name="weight_kg" v-model.number="draft.weight_kg" type="number" min="0" step="0.1" :placeholder="t('lg.order.weight')" />
          <input name="volume_m3" v-model.number="draft.volume_m3" type="number" min="0" step="0.1" :placeholder="t('lg.order.volume')" />
        </div>
        <label class="chk"><input type="checkbox" v-model="draft.fragile" /> {{ t("lg.order.fragile") }}</label>
        <label class="chk"><input type="checkbox" v-model="draft.needs_loading" /> {{ t("lg.order.needsLoading") }}</label>
        <label class="chk"><input type="checkbox" v-model="draft.needs_pickup" /> {{ t("lg.order.needsPickup") }}</label>
        <input name="pickup_window" v-model="draft.pickup_window" :placeholder="t('lg.order.pickupWindow')" />
        <input name="remarks" v-model="draft.remarks" :placeholder="t('lg.order.remarks')" />
        <p class="lbl">{{ t("lg.order.photos") }}</p>
        <ImageUpload v-model="draft.photo_ids" />
      </fieldset>

      <p class="note">{{ t("lg.order.priceNote") }}</p>
      <p class="note disc">{{ t("lg.order.disclaimer") }}</p>
      <p v-if="error" class="error">{{ error }}</p>

      <button class="submit" type="submit" :disabled="busy">
        {{ busy ? t("lg.order.submitting") : t("lg.order.submit") }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.form-page { min-height: 100vh; background: var(--surface); }
.bar { display: flex; align-items: center; gap: 8px; padding: 12px 14px; background: var(--bg); border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10; }
.bar h1 { font-size: 16px; font-weight: 500; }
.back { border: 0; background: transparent; color: var(--text-primary); display: flex; }
form { padding: 12px; display: flex; flex-direction: column; gap: 12px; }
fieldset { border: 0; background: var(--bg); border-radius: var(--radius-card); padding: 12px; display: flex; flex-direction: column; gap: 8px; }
legend { font-size: 13px; font-weight: 600; color: var(--brand-700); padding: 0 0 6px; }
input, select { border: 1px solid var(--border); border-radius: 8px; padding: 9px 11px; font-size: 14px; background: var(--surface); outline: none; }
.triple { display: flex; gap: 8px; }
.triple input { flex: 1; min-width: 0; }
.chk { display: flex; align-items: center; gap: 8px; font-size: 13.5px; color: var(--text-secondary); }
.lbl { font-size: 12.5px; color: var(--text-secondary); }
.note { font-size: 12px; color: var(--text-muted); padding: 0 4px; }
.disc { font-style: italic; }
.error { color: #c0392b; font-size: 13px; padding: 0 4px; }
.submit { border: 0; border-radius: var(--radius-pill); background: var(--brand-500); color: #fff; padding: 12px; font-size: 15px; font-weight: 500; }
.submit:disabled { opacity: 0.5; }
</style>
