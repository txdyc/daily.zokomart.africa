import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "../src/stores/auth";
import { freshPinia } from "./helpers";

vi.mock("../src/api/lg", () => ({
  requestOtp: vi.fn(() => Promise.resolve({ ok: true })),
  login: vi.fn(() =>
    Promise.resolve({ access_token: "tok-123", token_type: "bearer", user_id: 7, phone: "+233241234567" }),
  ),
}));
import { login, requestOtp } from "../src/api/lg";

describe("auth store", () => {
  beforeEach(() => {
    freshPinia();
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("starts logged out", () => {
    expect(useAuthStore().loggedIn).toBe(false);
  });

  it("requestCode delegates to the api", async () => {
    await useAuthStore().requestCode("0241234567");
    expect(requestOtp).toHaveBeenCalledWith("0241234567");
  });

  it("signIn stores the session and persists the token", async () => {
    const auth = useAuthStore();
    await auth.signIn("0241234567", "123456");
    expect(login).toHaveBeenCalledWith("0241234567", "123456");
    expect(auth.loggedIn).toBe(true);
    expect(auth.phone).toBe("+233241234567");
    expect(auth.userId).toBe(7);
    expect(localStorage.getItem("lg-token")).toBe("tok-123");
  });

  it("signOut clears state and storage", async () => {
    const auth = useAuthStore();
    await auth.signIn("0241234567", "123456");
    auth.signOut();
    expect(auth.loggedIn).toBe(false);
    expect(auth.token).toBe("");
    expect(localStorage.getItem("lg-token")).toBeNull();
  });

  it("hydrates the token from storage on creation", () => {
    localStorage.setItem("lg-token", "persisted");
    freshPinia();
    expect(useAuthStore().token).toBe("persisted");
  });
});
