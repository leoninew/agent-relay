<template>
  <section
    aria-labelledby="greeting-title"
    class="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
  >
    <div class="border-b border-slate-200 px-5 py-4 sm:px-6">
      <h1 id="greeting-title" class="m-0 text-lg font-semibold text-slate-950">Greeting</h1>
    </div>

    <div class="px-5 py-5 sm:px-6">
      <p v-if="loading" role="status" class="m-0 text-sm text-slate-600">Loading greeting...</p>
      <div
        v-else-if="error"
        role="alert"
        class="flex flex-wrap items-center gap-3 text-sm text-red-700"
      >
        <span>{{ error }}</span>
        <button
          type="button"
          class="rounded-md border border-red-200 bg-red-50 px-3 py-1.5 font-medium text-red-800 transition-colors hover:bg-red-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600"
          @click="emit('retry')"
        >
          Retry
        </button>
      </div>
      <p v-else-if="message" class="m-0 text-sm text-slate-800">{{ message }}</p>
      <p v-else class="m-0 text-sm text-slate-600">No greeting loaded.</p>
    </div>
  </section>
</template>

<script setup lang="ts">
  defineProps<{
    message: string | null;
    loading: boolean;
    error: string | null;
  }>();

  const emit = defineEmits<{
    retry: [];
  }>();
</script>
