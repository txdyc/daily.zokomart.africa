import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import OrderDetailView from "../src/views/OrderDetailView.vue";
import type { OrderView } from "../src/api/lgTypes";
import { freshPinia, testI18n, testRouter } from "./helpers";

function order(over: Partial<OrderView>): OrderView {
  return {
    id: 1, status: "submitted", trip_id: 5, depart_date: "2026-07-14", depart_time: "08:00",
    origin_town: "Accra", dest_town: "Kumasi", cargo_name: "TV sets", cargo_category: "electronics",
    packaging: "carton", pieces: 10, weight_kg: 200, volume_m3: 1.5, fragile: true, needs_loading: true,
    needs_pickup: false, pickup_window: "morning", remarks: "", photo_ids: [], freight_ghs: null,
    commission_ghs: null, pickup_time: "", cancel_reason: "", created_at: "2026-07-11T09:00:00",
    pickup_town: "Accra", delivery_town: "Kumasi", driver: null, shipper: null, ...over,
  };
}

const mocks = vi.hoisted(() => ({ orderDetail: vi.fn(), cancelOrder: vi.fn() }));
vi.mock("../src/api/lg", () => mocks);

async function mountDetail() {
  const router = testRouter();
  router.push("/me/orders/1");
  await router.isReady();
  const w = mount(OrderDetailView, { global: { plugins: [freshPinia(), testI18n("en"), router] } });
  await flushPromises();
  return { w };
}

describe("OrderDetailView", () => {
  beforeEach(() => vi.clearAllMocks());

  it("hides driver contact before acceptance", async () => {
    mocks.orderDetail.mockResolvedValueOnce(order({ status: "submitted", driver: null }));
    const { w } = await mountDetail();
    expect(w.text()).toContain("appears once the driver accepts");
    expect(w.find(".cancel").exists()).toBe(true);
  });

  it("shows driver contact once disclosed and hides cancel", async () => {
    mocks.orderDetail.mockResolvedValueOnce(
      order({ status: "in_transit", driver: { full_name: "Kwame", plate_number: "GR 1234-24", phone: "+233241234567" } }),
    );
    const { w } = await mountDetail();
    expect(w.text()).toContain("GR 1234-24");
    expect(w.text()).toContain("+233241234567");
    expect(w.find(".cancel").exists()).toBe(false);
  });

  it("cancels a submitted order", async () => {
    mocks.orderDetail.mockResolvedValueOnce(order({ status: "submitted" }));
    mocks.cancelOrder.mockResolvedValueOnce(order({ status: "cancelled" }));
    const { w } = await mountDetail();
    await w.find(".cancel").trigger("click");
    await w.find(".confirm-cancel").trigger("click");
    await flushPromises();
    expect(mocks.cancelOrder).toHaveBeenCalledWith(1, expect.any(String));
    expect(w.find(".status").text()).toContain("Cancelled");
  });
});
