<template>
  <DialogRoot :open="open" @update:open="updateOpen">
    <DialogTrigger v-if="$slots.trigger" as-child><slot name="trigger" /></DialogTrigger>
    <DialogPortal>
      <DialogOverlay class="dialog-overlay" />
      <DialogContent
        class="app-dialog"
        :class="contentClass"
        :aria-describedby="undefined"
        @open-auto-focus="focusInitial"
        @escape-key-down="preventBusyClose"
        @interact-outside="preventBusyClose"
        @close-auto-focus="restoreFocus"
      >
        <header class="dialog-heading">
          <DialogTitle>{{ title }}</DialogTitle>
          <DialogClose as-child>
            <button
              type="button"
              class="icon-button"
              :aria-label="t('dialog.close')"
              :disabled="busy"
            >
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
  import { useI18n } from "vue-i18n";

  import AppIcon from "@/components/AppIcon.vue";

  const { t } = useI18n();
  const props = defineProps<{
    open: boolean;
    title: string;
    busy: boolean;
    contentClass?: string;
    initialFocus?: string;
  }>();
  const emit = defineEmits<{ close: []; "update:open": [open: boolean] }>();
  let previousFocus: HTMLElement | null = null;

  watch(
    () => props.open,
    (open) => {
      if (open) {
        previousFocus =
          document.activeElement instanceof HTMLElement ? document.activeElement : null;
      }
    },
  );

  function updateOpen(open: boolean): void {
    if (props.busy) {
      return;
    }
    emit("update:open", open);
    if (!open) {
      emit("close");
    }
  }

  function preventBusyClose(event: Event): void {
    if (props.busy) {
      event.preventDefault();
    }
  }

  function focusInitial(event: Event): void {
    if (!props.initialFocus || !(event.target instanceof HTMLElement)) {
      return;
    }
    const target = event.target.querySelector<HTMLElement>(props.initialFocus);
    target?.focus();
    if (!target || target.ownerDocument.activeElement !== target) {
      return;
    }
    event.preventDefault();
    if (
      (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) &&
      target.selectionStart !== null
    ) {
      const end = target.value.length;
      target.setSelectionRange(end, end);
    }
  }

  function restoreFocus(event: Event): void {
    if (previousFocus?.isConnected) {
      event.preventDefault();
      previousFocus.focus();
    }
  }
</script>
