import { defineStore } from "pinia";

import { browserStorage, readJSON, writeJSON } from "@/services/storage";

export const NOTIFICATIONS_STORAGE_KEY = "vue-vite-app.notifications";

export type Notification = {
  id: string;
  title: string;
  unread: boolean;
};

type NotificationsSnapshot = {
  items: Notification[];
};

const defaultSnapshot: NotificationsSnapshot = {
  items: [
    { id: "deploy", title: "Deploy finished", unread: true },
    { id: "review", title: "Review requested", unread: false },
  ],
};

function readSnapshot(): NotificationsSnapshot {
  const storage = browserStorage();
  return storage ? readJSON(storage, NOTIFICATIONS_STORAGE_KEY, defaultSnapshot) : defaultSnapshot;
}

function persistSnapshot(snapshot: NotificationsSnapshot): void {
  const storage = browserStorage();
  if (storage) {
    writeJSON(storage, NOTIFICATIONS_STORAGE_KEY, snapshot);
  }
}

export const useNotificationsStore = defineStore("notifications", {
  state: (): NotificationsSnapshot => ({ ...readSnapshot() }),
  getters: {
    unreadCount: (state) => state.items.filter((notification) => notification.unread).length,
  },
  actions: {
    markRead(notificationId: string): void {
      this.items = this.items.map((notification) =>
        notification.id === notificationId ? { ...notification, unread: false } : notification,
      );
      persistSnapshot({ items: this.items });
    },
    markAllRead(): void {
      this.items = this.items.map((notification) => ({ ...notification, unread: false }));
      persistSnapshot({ items: this.items });
    },
  },
});
