import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import TabBar from "../src/components/TabBar.vue";
import { freshPinia, testI18n, testRouter } from "./helpers";

async function mountTabBar(path = "/") {
  const router = testRouter();
  router.push(path);
  await router.isReady();
  const w = mount(TabBar, { global: { plugins: [freshPinia(), testI18n("en"), router] } });
  return { w, router };
}

describe("TabBar", () => {
  it("renders three tabs", async () => {
    const { w } = await mountTabBar();
    expect(w.findAll(".tab")).toHaveLength(3);
  });

  it("marks the active tab from the current route", async () => {
    const { w } = await mountTabBar("/lg");
    const active = w.find(".tab.active");
    expect(active.text()).toContain("Logistics");
  });

  it("navigates when a tab is tapped", async () => {
    const { w, router } = await mountTabBar("/");
    await w.findAll(".tab")[2].trigger("click");
    await flushPromises();
    expect(router.currentRoute.value.name).toBe("me");
  });
});
