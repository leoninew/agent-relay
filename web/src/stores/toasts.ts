import { defineStore } from "pinia";
import { ref } from "vue";

export type ToastTone = "success" | "error" | "info";
export type ToastMessage = { id: number; message: string; tone: ToastTone };

export const useToastsStore = defineStore("toasts", () => {
  const items = ref<ToastMessage[]>([]);
  let nextId = 0;

  function show(message: string, tone: ToastTone = "info"): number {
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
    success: (message: string) => show(message, "success"),
    error: (message: string) => show(message, "error"),
    info: (message: string) => show(message, "info"),
  };
});
