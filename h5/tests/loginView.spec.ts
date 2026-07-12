import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginView from "../src/views/LoginView.vue";
import { useAuthStore } from "../src/stores/auth";
import { freshPinia, testI18n, testRouter } from "./helpers";

vi.mock("../src/api/lg", () => ({
  requestOtp: vi.fn(() => Promise.resolve({ ok: true })),
  login: vi.fn(() =>
    Promise.resolve({ access_token: "tok", token_type: "bearer", user_id: 1, phone: "+233241234567" }),
  ),
}));
import { login, requestOtp } from "../src/api/lg";

async function mountLogin() {
  const router = testRouter();
  router.push("/me/login");
  await router.isReady();
  const w = mount(LoginView, { global: { plugins: [freshPinia(), testI18n("en"), router] } });
  return { w, router };
}

describe("LoginView", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("requests a code for the entered phone", async () => {
    const { w } = await mountLogin();
    await w.find("input[type=tel]").setValue("0241234567");
    await w.find(".send-code").trigger("click");
    expect(requestOtp).toHaveBeenCalledWith("0241234567");
    await flushPromises();
    expect(w.find("input[inputmode=numeric]").exists()).toBe(true);
  });

  it("verifies the code, signs in, and redirects", async () => {
    const { w, router } = await mountLogin();
    const spy = vi.spyOn(router, "replace");
    await w.find("input[type=tel]").setValue("0241234567");
    await w.find(".send-code").trigger("click");
    await flushPromises();
    await w.find("input[inputmode=numeric]").setValue("123456");
    await w.find(".verify").trigger("click");
    await flushPromises();
    expect(login).toHaveBeenCalledWith("0241234567", "123456");
    expect(useAuthStore().loggedIn).toBe(true);
    expect(spy).toHaveBeenCalled();
  });
});
