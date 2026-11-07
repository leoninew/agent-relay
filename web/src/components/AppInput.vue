<template>
  <div
    ref="root"
    class="app-input"
    :class="{ 'is-multiline': multiline, 'is-invalid': invalid, 'is-disabled': disabled }"
  >
    <Primitive
      v-bind="$attrs"
      :as="multiline ? 'textarea' : 'input'"
      class="app-input-control"
      :value="model"
      :disabled="disabled"
      :readonly="readonly"
      :aria-invalid="invalid"
      @input="updateValue"
      @compositionstart="composing = true"
      @compositionend="finishComposition"
    />
    <AppClearButton
      v-if="model && !readonly"
      :label="clearLabel"
      :disabled="disabled"
      @clear="clear"
    />
  </div>
</template>

<script setup lang="ts">
  import { Primitive } from "reka-ui";
  import { nextTick, ref } from "vue";

  import AppClearButton from "@/components/AppClearButton.vue";

  defineOptions({ inheritAttrs: false });
  const props = defineProps<{
    clearLabel: string;
    multiline?: boolean;
    disabled?: boolean;
    readonly?: boolean;
    invalid?: boolean;
  }>();
  const model = defineModel<string>({ required: true });
  const root = ref<HTMLElement>();
  const composing = ref(false);

  function updateValue(event: Event): void {
    if (!composing.value)
      model.value = (event.target as HTMLInputElement | HTMLTextAreaElement).value;
  }

  function finishComposition(event: CompositionEvent): void {
    composing.value = false;
    updateValue(event);
  }

  function focus(): void {
    root.value?.querySelector<HTMLInputElement | HTMLTextAreaElement>("input, textarea")?.focus();
  }

  async function clear(): Promise<void> {
    if (props.disabled || props.readonly) return;
    model.value = "";
    await nextTick();
    focus();
  }

  defineExpose({ focus });
</script>
