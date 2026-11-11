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
    Copy,
    Ellipsis,
    GripVertical,
    Hash,
    Info,
    MessagesSquare,
    PanelLeftOpen,
    PanelRightOpen,
    Pencil,
    Plus,
    RefreshCw,
    Reply,
    Search,
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
    copy: Copy,
    enter: CornerDownLeft,
    more: Ellipsis,
    edit: Pencil,
    grip: GripVertical,
    hash: Hash,
    info: Info,
    "panel-left-open": PanelLeftOpen,
    "panel-right-open": PanelRightOpen,
    plus: Plus,
    refresh: RefreshCw,
    relay: Waypoints,
    reply: Reply,
    search: Search,
    trash: Trash2,
  };
</script>
