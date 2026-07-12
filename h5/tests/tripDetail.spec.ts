import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import TripDetailView from "../src/views/TripDetailView.vue";
import type { RouteDetail } from "../src/api/lgTypes";
import { freshPinia, testI18n, testRouter } from "./helpers";

const detail: RouteDetail = {
  id: 1, origin_region: "Greater Accra", origin_town: "Accra", dest_region: "Ashanti",
  dest_town: "Kumasi", via_towns: ["Nkawkaw"], est_duration_hours: 6, cargo_types: ["general"],
  prohibited_notes: "", rate_per_ton: 350, rate_per_m3: 60, min_charge: 80, negotiable: false,
  vehicle: { vehicle_type: "box_truck", brand_model: "Kia K2700", max_load_kg: 2000, max_volume_m3: 10, cargo_length_m: 3.1, cargo_width_m: 1.7, cargo_height_m: 1.8 },
  upcoming_trips: [
    { trip_id: 5, depart_date: "2026-07-14", depart_time: "08:00", remaining_load_kg: 2000, remaining_volume_m3: 10 },
  ],
};

vi.mock("../src/api/lg", () => ({ routeDetail: vi.fn(() => Promise.resolve(detail)) }));

async function mountDetail() {
  const router = testRouter();
  router.push("/lg/trip/5");
  await router.isReady();
  const w = mount(TripDetailView, { global: { plugins: [freshPinia(), testI18n("en"), router] } });
  await flushPromises();
  return { w, router };
}

describe("TripDetailView", () => {
  it("shows the lane, vehicle, and an upcoming trip", async () => {
    const { w } = await mountDetail();
    expect(w.text()).toContain("Accra");
    expect(w.text()).toContain("Kumasi");
    expect(w.text()).toContain("box_truck");
    expect(w.find(".trip-row").exists()).toBe(true);
  });

  it("books the focused trip", async () => {
    const { w, router } = await mountDetail();
    const spy = vi.spyOn(router, "push");
    await w.find(".book").trigger("click");
    expect(spy).toHaveBeenCalledWith("/lg/order/new/5");
  });
});
