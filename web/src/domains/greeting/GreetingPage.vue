<template>
  <section class="mx-auto grid max-w-2xl gap-6">
    <form
      aria-label="Greeting form"
      class="grid gap-4 rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end sm:p-6"
      @submit.prevent="loadGreeting"
    >
      <div class="grid gap-2 text-sm font-medium text-slate-800">
        <label for="greeting-name">Name</label>
        <AppInput id="greeting-name" v-model="name" name="name" clear-label="清空名称" />
      </div>
      <AppButton type="submit" :loading="loading" loading-label="Loading greeting…">
        Load greeting
      </AppButton>
    </form>

    <GreetingCard
      :message="data?.text ?? null"
      :loading="loading"
      :error="error"
      @retry="loadGreeting"
    />
  </section>
</template>

<script setup lang="ts">
  import { onMounted, ref } from "vue";

  import AppButton from "@/components/AppButton.vue";
  import AppInput from "@/components/AppInput.vue";
  import GreetingCard from "@/components/GreetingCard.vue";
  import { useGreeting } from "@/composables/useGreeting";

  const name = ref("Ada");
  const { data, error, loading, load } = useGreeting();

  function loadGreeting(): void {
    void load(name.value);
  }

  onMounted(loadGreeting);
</script>
