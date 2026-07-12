import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import MyOrdersView from "../src/views/MyOrdersView.vue";
import type { OrderList } from "../src/api/lgTypes";
import { freshPinia, testI18n, testRouter } from "./helpers";

const list: OrderList = {
  items: [
    {
      id: 1, status: "price_confirmed", trip_id: 5, depart_date: "2026-07-14", depart_time: "08:00",
      origin_town: "Accra", dest_town: "Kumasi", cargo_name: "TV sets", cargo_category: "electronics",
      packaging: "carton", pieces: 10, weight_kg: 200, volume_m3: 1.5, fragile: true, needs_loading: true,
      needs_pickup: false, pickup_window: "morning", remarks: "", photo_ids: [], freight_ghs: 500,
      commission_ghs: 40, pickup_time: "Sat 08:00", cancel_reason: "", created_at: "2026-07-11T09:00:00",
      pickup_town: "Accra", delivery_town: "Kumasi", driver: null, shipper: null,
    },
  ],
  total: 1, page: 1, page_size: 20,
};

vi.mock("../src/api/lg", () => ({ myOrders: vi.fn(() => Promise.resolve(list)) }));

async function mountList() {
  const router = testRouter();
  router.push("/me/orders");
  await router.isReady();
  const w = mount(MyOrdersView, { global: { plugins: [freshPinia(), testI18n("en"), router] } });
  await flushPromises();
  return { w };
}

describe("MyOrdersView", () => {
  it("lists the shipper's orders with a status tag", async () => {
    const { w } = await mountList();
    expect(w.text()).toContain("TV sets");
    expect(w.text()).toContain("Accra");
    expect(w.find(".status").text()).toContain("Price confirmed");
  });
});
