<template>
  <div class="min-h-screen bg-slate-100 text-slate-950">
    <header class="border-b border-slate-200 bg-white">
      <div
        class="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6"
      >
        <p class="m-0 text-sm font-semibold text-slate-900">Agent Relay</p>
        <nav aria-label="Primary navigation" class="flex items-center gap-2">
          <RouterLink
            to="/"
            class="rounded-md px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-950"
            exact-active-class="bg-slate-900 text-white hover:bg-slate-900 hover:text-white"
          >
            Greeting
          </RouterLink>
          <RouterLink
            to="/notifications"
            class="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-950"
            exact-active-class="bg-slate-900 text-white hover:bg-slate-900 hover:text-white"
          >
            <span>Notifications</span>
            <span
              class="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-semibold text-slate-700"
            >
              {{ unreadCount }}
            </span>
          </RouterLink>
        </nav>
      </div>
    </header>

    <main class="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
  import { storeToRefs } from "pinia";
  import { RouterLink, RouterView } from "vue-router";

  import { useNotificationsStore } from "@/stores/notifications";

  const notifications = useNotificationsStore();
  const { unreadCount } = storeToRefs(notifications);
</script>
