import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

import GreetingPage from "@/domains/greeting/GreetingPage.vue";
import NotificationCenter from "@/domains/notifications/NotificationCenter.vue";

const routes: RouteRecordRaw[] = [
  {
    path: "/",
    name: "greeting",
    component: GreetingPage,
  },
  {
    path: "/notifications",
    name: "notifications",
    component: NotificationCenter,
  },
];

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});
