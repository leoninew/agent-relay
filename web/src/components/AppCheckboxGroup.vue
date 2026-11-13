<template>
  <CheckboxGroupRoot
    ref="root"
    v-model="model"
    class="app-checkbox-group"
    role="group"
    :roving-focus="false"
    :disabled="disabled"
    :aria-invalid="invalid"
    :aria-describedby="describedBy"
  >
    <slot />
    <AppClearButton
      v-if="clearLabel && model.length"
      :label="clearLabel"
      :disabled="disabled"
      @clear="clear"
    />
  </CheckboxGroupRoot>
</template>

<script setup lang="ts">
  import { CheckboxGroupRoot } from "reka-ui";
  import { nextTick, ref } from "vue";

  import AppClearButton from "@/components/AppClearButton.vue";

  const props = defineProps<{
    clearLabel?: string;
    disabled?: boolean;
    invalid?: boolean;
    describedBy?: string;
  }>();
  const model = defineModel<string[]>({ required: true });
  const root = ref<InstanceType<typeof CheckboxGroupRoot>>();

  async function clear(): Promise<void> {
    if (props.disabled) return;
    model.value = [];
    await nextTick();
    const element = root.value?.$el as HTMLElement | undefined;
    element?.querySelector<HTMLButtonElement>('[role="checkbox"]:not(:disabled)')?.focus();
  }
</script>
