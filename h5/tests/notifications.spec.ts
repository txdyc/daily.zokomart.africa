import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import NotificationsView from "../src/views/NotificationsView.vue";
import type { NotificationList } from "../src/api/lgTypes";
import { freshPinia, testI18n, testRouter } from "./helpers";

const list: NotificationList = {
  items: [
    { id: 2, kind: "order", title: "Driver accepted your order", body: "Pickup Sat", read: false, created_at: "2026-07-11T10:00:00" },
    { id: 1, kind: "order", title: "Order submitted", body: "", read: true, created_at: "2026-07-11T09:00:00" },
  ],
  total: 2, unread: 1, page: 1, page_size: 20,
};

const mocks = vi.hoisted(() => ({ listNotifications: vi.fn(), markNotificationRead: vi.fn() }));
vi.mock("../src/api/lg", () => mocks);

async function mountNotifs() {
  const router = testRouter();
  router.push("/me/notifications");
  await router.isReady();
  const w = mount(NotificationsView, { global: { plugins: [freshPinia(), testI18n("en"), router] } });
  await flushPromises();
  return { w };
}

describe("NotificationsView", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("lists notifications, newest first, marking unread ones", async () => {
    mocks.listNotifications.mockResolvedValueOnce(list);
    const { w } = await mountNotifs();
    const rows = w.findAll(".notif");
    expect(rows).toHaveLength(2);
    expect(rows[0].text()).toContain("Driver accepted your order");
    expect(rows[0].classes()).toContain("unread");
  });

  it("marks a notification read on tap", async () => {
    mocks.listNotifications.mockResolvedValueOnce(list);
    mocks.markNotificationRead.mockResolvedValueOnce(undefined);
    const { w } = await mountNotifs();
    await w.findAll(".notif")[0].trigger("click");
    await flushPromises();
    expect(mocks.markNotificationRead).toHaveBeenCalledWith(2);
    expect(w.findAll(".notif")[0].classes()).not.toContain("unread");
  });
});
