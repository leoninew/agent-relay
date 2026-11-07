<template>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.7"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="paths[name]" />
  </svg>
</template>

<script setup lang="ts">
  defineProps<{ name: keyof typeof paths }>();

  const paths = {
    plus: "M12 5v14 M5 12h14",
    relay: "M7 4v12a4 4 0 0 0 4 4h6 M7 8h6a4 4 0 0 0 4-4 M4 4h6 M14 4h6 M14 20h6",
    chat: "M21 11a8 8 0 0 1-8 8H5l-4 3V11a10 10 0 0 1 20 0Z M7 10h10 M7 14h6",
    hash: "M5 9h14 M4 15h14 M11 3 7 21 M17 3l-4 18",
    arrow: "M5 12h14 M13 6l6 6-6 6",
    enter: "M19 5v5a4 4 0 0 1-4 4H5 M9 10l-4 4 4 4",
    send: "m22 2-7 20-4-9-9-4 20-7Z M22 2 11 13",
    refresh: "M20 7v5h-5 M4 17v-5h5 M6 7a7 7 0 0 1 12-1l2 6 M4 12l2 6a7 7 0 0 0 12-1",
    "chevron-down": "m6 9 6 6 6-6",
    people:
      "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M22 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75",
    check: "m5 12 4 4L19 6",
    clock: "M12 8v4l3 2 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
    reply: "m9 4-6 6 6 6 M3 10h10a7 7 0 0 1 7 7v3",
    close: "m6 6 12 12 M6 18 18 6",
    bell: "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9 M10 21h4",
    chevron: "m9 5 7 7-7 7",
    activity: "M2 12h5l3-9 4 18 3-9h5",
    info: "M12 11v6 M12 7h.01 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
    at: "M16 8v6a2 2 0 0 0 4 0v-2a8 8 0 1 0-3 6 M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
  };
</script>
