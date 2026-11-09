<template>
  <component
    :is="icons[name]"
    :size="20"
    :stroke-width="1.7"
    aria-hidden="true"
    focusable="false"
  />
</template>

<script setup lang="ts">
  import {
    AtSign,
    ArrowRight,
    Check,
    ChevronDown,
    ChevronRight,
    CornerDownLeft,
    GripVertical,
    Hash,
    Info,
    MessagesSquare,
    Plus,
    RefreshCw,
    Reply,
    Trash2,
    Waypoints,
    X,
  } from "@lucide/vue";

  defineProps<{ name: keyof typeof icons }>();

  const icons = {
    "chevron-down": ChevronDown,
    arrow: ArrowRight,
    at: AtSign,
    chat: MessagesSquare,
    check: Check,
    chevron: ChevronRight,
    close: X,
    enter: CornerDownLeft,
    grip: GripVertical,
    hash: Hash,
    info: Info,
    plus: Plus,
    refresh: RefreshCw,
    relay: Waypoints,
    reply: Reply,
    trash: Trash2,
  };
</script>
