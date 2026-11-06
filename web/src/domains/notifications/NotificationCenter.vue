<template>
  <section aria-labelledby="notifications-title" class="mx-auto max-w-2xl">
    <div class="mb-6">
      <h1 id="notifications-title" class="m-0 text-xl font-semibold text-slate-950">
        Notifications
      </h1>
      <p class="mb-0 mt-2 text-sm text-slate-600">{{ unreadCount }} unread notifications</p>
    </div>

    <TabsRoot
      v-model="activeFilter"
      class="block overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
    >
      <div
        class="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6"
      >
        <TabsList
          aria-label="Notification filter"
          class="inline-flex w-fit rounded-md bg-slate-100 p-1"
        >
          <TabsTrigger
            value="all"
            class="rounded px-3 py-1.5 text-sm font-medium text-slate-600 transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 data-[state=active]:bg-white data-[state=active]:text-slate-950 data-[state=active]:shadow-sm"
          >
            All
          </TabsTrigger>
          <TabsTrigger
            value="unread"
            class="rounded px-3 py-1.5 text-sm font-medium text-slate-600 transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 data-[state=active]:bg-white data-[state=active]:text-slate-950 data-[state=active]:shadow-sm"
          >
            Unread
          </TabsTrigger>
        </TabsList>
        <button
          type="button"
          :disabled="unreadCount === 0"
          class="w-fit rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
          @click="notifications.markAllRead"
        >
          Mark all read
        </button>
      </div>

      <TabsContent value="all" class="outline-none">
        <ul aria-label="Notification list" class="m-0 divide-y divide-slate-100 p-0">
          <li
            v-for="notification in notifications.items"
            :key="notification.id"
            class="flex items-center justify-between gap-4 px-5 py-4 sm:px-6"
          >
            <span class="min-w-0 text-sm text-slate-800">{{ notification.title }}</span>
            <button
              v-if="notification.unread"
              type="button"
              class="shrink-0 rounded-md px-2.5 py-1.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
              @click="notifications.markRead(notification.id)"
            >
              Mark read
            </button>
          </li>
        </ul>
      </TabsContent>

      <TabsContent value="unread" class="outline-none">
        <ul aria-label="Notification list" class="m-0 divide-y divide-slate-100 p-0">
          <li
            v-for="notification in notifications.items.filter(
              (notification) => notification.unread,
            )"
            :key="notification.id"
            class="flex items-center justify-between gap-4 px-5 py-4 sm:px-6"
          >
            <span class="min-w-0 text-sm text-slate-800">{{ notification.title }}</span>
            <button
              type="button"
              class="shrink-0 rounded-md px-2.5 py-1.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
              @click="notifications.markRead(notification.id)"
            >
              Mark read
            </button>
          </li>
          <li v-if="unreadCount === 0" class="px-5 py-4 text-sm text-slate-600 sm:px-6">
            No unread notifications.
          </li>
        </ul>
      </TabsContent>
    </TabsRoot>
  </section>
</template>

<script setup lang="ts">
  import { storeToRefs } from "pinia";
  import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "reka-ui";
  import { ref } from "vue";

  import { useNotificationsStore } from "@/stores/notifications";

  const activeFilter = ref("all");
  const notifications = useNotificationsStore();
  const { unreadCount } = storeToRefs(notifications);
</script>
