<template>
  <section class="mx-auto grid max-w-2xl gap-6">
    <form
      aria-label="Greeting form"
      class="grid gap-4 rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end sm:p-6"
      @submit.prevent="loadGreeting"
    >
      <label class="grid gap-2 text-sm font-medium text-slate-800">
        Name
        <input
          v-model="name"
          name="name"
          class="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-950 shadow-xs outline-none transition focus:border-slate-900 focus:ring-2 focus:ring-slate-900/15"
        />
      </label>
      <button
        type="submit"
        class="h-10 rounded-md bg-slate-900 px-4 text-sm font-medium text-white transition-colors hover:bg-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
      >
        Load greeting
      </button>
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

  import GreetingCard from "@/components/GreetingCard.vue";
  import { useGreeting } from "@/composables/useGreeting";

  const name = ref("Ada");
  const { data, error, loading, load } = useGreeting();

  function loadGreeting(): void {
    void load(name.value);
  }

  onMounted(loadGreeting);
</script>
