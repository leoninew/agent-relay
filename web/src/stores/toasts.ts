import { defineStore } from "pinia";
import { ref } from "vue";
import type { MessageDescriptor } from "@/i18n";

export type ToastTone = "success" | "error" | "info";
export type ToastMessage = { id: number; message: MessageDescriptor; tone: ToastTone };

export const useToastsStore = defineStore("toasts", () => {
  const items = ref<ToastMessage[]>([]);
  let nextId = 0;

  function show(message: MessageDescriptor, tone: ToastTone = "info"): number {
    const id = ++nextId;
    items.value = [...items.value, { id, message, tone }].slice(-3);
    return id;
  }

  function dismiss(id: number): void {
    items.value = items.value.filter((item) => item.id !== id);
  }

  return {
    items,
    show,
    dismiss,
    success: (message: MessageDescriptor) => show(message, "success"),
    error: (message: MessageDescriptor) => show(message, "error"),
    info: (message: MessageDescriptor) => show(message, "info"),
  };
});
