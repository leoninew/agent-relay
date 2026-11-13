import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

import RoomPage from "@/domains/room/RoomPage.vue";

const routes: RouteRecordRaw[] = [
  {
    path: "/settings",
    name: "settings",
    redirect: { name: "room" },
  },
  {
    path: "/",
    name: "room",
    component: RoomPage,
  },
  {
    path: "/room/:roomId",
    name: "room-detail",
    component: RoomPage,
    props: true,
  },
];

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});
