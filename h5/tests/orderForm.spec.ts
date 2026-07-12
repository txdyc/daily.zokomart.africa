import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import OrderFormView from "../src/views/OrderFormView.vue";
import { freshPinia, testI18n, testRouter } from "./helpers";

vi.mock("../src/api/lg", () => ({
  submitOrder: vi.fn(() => Promise.resolve({ id: 99, status: "submitted" })),
  uploadImage: vi.fn(() => Promise.resolve({ id: "att-1", url: "/api/lg/uploads/att-1" })),
}));
import { submitOrder } from "../src/api/lg";

async function mountForm() {
  const router = testRouter();
  router.push("/lg/order/new/5");
  await router.isReady();
  const w = mount(OrderFormView, { global: { plugins: [freshPinia(), testI18n("en"), router] } });
  return { w, router };
}

function fill(w: Awaited<ReturnType<typeof mountForm>>["w"]) {
  const set = (name: string, value: string) => w.find(`[name=${name}]`).setValue(value);
  set("contact_name", "Efua");
  set("contact_phone", "0201112223");
  set("pickup_town", "Accra");
  set("delivery_town", "Kumasi");
  set("consignee_name", "Yaw");
  set("consignee_phone", "0261112223");
  set("cargo_name", "TV sets");
  set("pieces", "10");
  set("weight_kg", "200");
  set("volume_m3", "1.5");
  set("pickup_window", "tomorrow morning");
}

describe("OrderFormView", () => {
  beforeEach(() => vi.clearAllMocks());

  it("blocks submission until required fields are filled", async () => {
    const { w } = await mountForm();
    await w.find("form").trigger("submit.prevent");
    expect(submitOrder).not.toHaveBeenCalled();
    expect(w.find(".error").exists()).toBe(true);
  });

  it("submits the order with the trip id from the route", async () => {
    const { w, router } = await mountForm();
    const spy = vi.spyOn(router, "replace");
    fill(w);
    await w.find("form").trigger("submit.prevent");
    await flushPromises();
    expect(submitOrder).toHaveBeenCalledWith(expect.objectContaining({ trip_id: 5, cargo_name: "TV sets", weight_kg: 200 }));
    expect(spy).toHaveBeenCalledWith("/me/orders");
  });
});
