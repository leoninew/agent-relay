<template>
  <DialogRoot :open="open" @update:open="updateOpen">
    <DialogTrigger v-if="$slots.trigger" as-child><slot name="trigger" /></DialogTrigger>
    <DialogPortal>
      <DialogOverlay class="dialog-overlay" />
      <DialogContent
        class="app-dialog"
        :aria-describedby="undefined"
        @escape-key-down="preventBusyClose"
        @interact-outside="preventBusyClose"
        @close-auto-focus="restoreFocus"
      >
        <header class="dialog-heading">
          <DialogTitle>{{ title }}</DialogTitle>
          <DialogClose as-child>
            <button type="button" class="icon-button" aria-label="关闭对话框" :disabled="busy">
              <AppIcon name="close" />
            </button>
          </DialogClose>
        </header>
        <slot />
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>

<script setup lang="ts">
  import {
    DialogClose,
    DialogContent,
    DialogOverlay,
    DialogPortal,
    DialogRoot,
    DialogTitle,
    DialogTrigger,
  } from "reka-ui";
  import { watch } from "vue";

  import AppIcon from "@/components/AppIcon.vue";

  const props = defineProps<{ open: boolean; title: string; busy: boolean }>();
  const emit = defineEmits<{ close: []; "update:open": [open: boolean] }>();
  let previousFocus: HTMLElement | null = null;

  watch(
    () => props.open,
    (open) => {
      if (open)
        previousFocus =
          document.activeElement instanceof HTMLElement ? document.activeElement : null;
    },
  );

  function updateOpen(open: boolean): void {
    if (props.busy) return;
    emit("update:open", open);
    if (!open) emit("close");
  }

  function preventBusyClose(event: Event): void {
    if (props.busy) event.preventDefault();
  }

  function restoreFocus(event: Event): void {
    if (previousFocus?.isConnected) {
      event.preventDefault();
      previousFocus.focus();
    }
  }
</script>
