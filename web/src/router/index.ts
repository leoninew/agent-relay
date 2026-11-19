import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

import RoomPage from "@/domains/room/RoomPage.vue";
import SettingsPage from "@/domains/settings/SettingsPage.vue";

const routes: RouteRecordRaw[] = [
  {
    path: "/settings",
    name: "settings",
    component: SettingsPage,
  },
  {
    path: "/",
    name: "room",
    component: RoomPage,
  },
  {
    path: "/room/:roomId/channel/:channelId",
    name: "channel",
    component: RoomPage,
    props: true,
  },
];

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});
