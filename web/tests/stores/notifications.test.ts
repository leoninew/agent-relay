import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import { NOTIFICATIONS_STORAGE_KEY, useNotificationsStore } from "@/stores/notifications";

describe("useNotificationsStore", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it("starts with unread notifications", () => {
    const notifications = useNotificationsStore();

    expect(notifications.unreadCount).toBe(1);
  });

  it("marks notifications as read and persists them", () => {
    const notifications = useNotificationsStore();
    notifications.items = [{ id: "deploy", title: "Deploy finished", unread: true }];

    notifications.markRead("deploy");

    expect(notifications.unreadCount).toBe(0);
    expect(localStorage.getItem(NOTIFICATIONS_STORAGE_KEY)).toContain('"unread":false');
  });
});
