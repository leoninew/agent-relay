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
    Languages,
    MessagesSquare,
    PanelLeftClose,
    PanelLeftOpen,
    PanelRightClose,
    PanelRightOpen,
    Pencil,
    Plus,
    Plug,
    RefreshCw,
    Reply,
    Search,
    Settings,
    Sparkles,
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
    language: Languages,
    "panel-left-close": PanelLeftClose,
    "panel-left-open": PanelLeftOpen,
    "panel-right-close": PanelRightClose,
    "panel-right-open": PanelRightOpen,
    plus: Plus,
    plug: Plug,
    refresh: RefreshCw,
    relay: Waypoints,
    reply: Reply,
    search: Search,
    settings: Settings,
    skill: Sparkles,
    trash: Trash2,
  };
</script>
