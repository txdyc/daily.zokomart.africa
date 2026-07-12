import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it } from "vitest";

import MeView from "../src/views/MeView.vue";
import { useAuthStore } from "../src/stores/auth";
import { freshPinia, testI18n, testRouter } from "./helpers";

async function mountMe() {
  const router = testRouter();
  router.push("/me");
  await router.isReady();
  const pinia = freshPinia();
  const w = mount(MeView, { global: { plugins: [pinia, testI18n("en"), router] } });
  return { w };
}

describe("MeView", () => {
  beforeEach(() => localStorage.clear());

  it("shows a sign-in prompt when logged out", async () => {
    const { w } = await mountMe();
    expect(w.text()).toContain("Sign in");
    expect(w.find(".menu").exists()).toBe(false);
  });

  it("shows the account menu and can sign out when logged in", async () => {
    const { w } = await mountMe();
    const auth = useAuthStore();
    auth.token = "tok";
    auth.phone = "+233241234567";
    await w.vm.$nextTick();
    expect(w.find(".menu").exists()).toBe(true);
    await w.find(".sign-out").trigger("click");
    expect(auth.loggedIn).toBe(false);
  });
});
