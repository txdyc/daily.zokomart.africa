import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("element-plus", () => ({
  // Cover every named import any view uses — the guard test lazily loads view modules.
  ElMessage: { warning: vi.fn(), error: vi.fn(), success: vi.fn() },
  ElMessageBox: { confirm: vi.fn() },
}));

import { TOKEN_KEY, USER_KEY, handleApiError } from "../src/api/client";
import { router } from "../src/router";

beforeEach(() => {
  localStorage.clear();
});

describe("router guard", () => {
  it("redirects unauthenticated users to login with redirect query", async () => {
    await router.push("/articles");
    expect(router.currentRoute.value.name).toBe("login");
    expect(router.currentRoute.value.query.redirect).toBe("/articles");
  });

  it("lets authenticated users through", async () => {
    localStorage.setItem(TOKEN_KEY, "some-token");
    await router.push("/articles");
    expect(router.currentRoute.value.name).toBe("articles");
  });
});

describe("handleApiError", () => {
  it("clears token and redirects on 401", async () => {
    localStorage.setItem(TOKEN_KEY, "t");
    localStorage.setItem(USER_KEY, "admin");
    const redirect = vi.fn();
    await expect(
      handleApiError({ response: { status: 401, data: {} } }, redirect),
    ).rejects.toBeTruthy();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(USER_KEY)).toBeNull();
    expect(redirect).toHaveBeenCalled();
  });

  it("does not clear token on 409", async () => {
    localStorage.setItem(TOKEN_KEY, "t");
    const redirect = vi.fn();
    await expect(
      handleApiError({ response: { status: 409, data: { detail: "占用" } } }, redirect),
    ).rejects.toBeTruthy();
    expect(localStorage.getItem(TOKEN_KEY)).toBe("t");
    expect(redirect).not.toHaveBeenCalled();
  });
});
