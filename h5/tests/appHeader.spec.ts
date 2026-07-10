import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AppHeader from "../src/components/AppHeader.vue";
import { usePrefsStore } from "../src/stores/prefs";
import { freshPinia, testI18n } from "./helpers";

function mountHeader() {
  const pinia = freshPinia();
  return {
    w: mount(AppHeader, { global: { plugins: [pinia, testI18n("zh")] } }),
    prefs: usePrefsStore(),
  };
}

describe("AppHeader", () => {
  it("shows the wordmark and lang pill", () => {
    const { w } = mountHeader();
    expect(w.text()).toContain("ZokoDaily");
    expect(w.find(".lang-pill").exists()).toBe(true);
  });

  it("lang pill toggles the UI language", async () => {
    const { w, prefs } = mountHeader();
    await w.find(".lang-pill").trigger("click");
    expect(prefs.uiLang).toBe("en");
  });

  it("search expands, submits keyword, and cancel clears", async () => {
    const { w } = mountHeader();
    await w.find(".search-btn").trigger("click");
    const input = w.find("input");
    expect(input.exists()).toBe(true);
    await input.setValue("外汇");
    await input.trigger("keyup.enter");
    expect(w.emitted("search")![0]).toEqual(["外汇"]);
    await w.find(".cancel-btn").trigger("click");
    expect(w.find("input").exists()).toBe(false);
    expect(w.emitted("search")![1]).toEqual([""]);
  });
});
