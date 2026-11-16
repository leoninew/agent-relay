<template>
  <div class="app-skeleton" aria-hidden="true"></div>
</template>

<style scoped>
  .app-skeleton {
    flex-shrink: 0;
    width: 100%;
    max-width: 100%;
    height: 14px;
    border-radius: 4px;
    background: hsl(var(--muted-foreground) / 0.14);
  }
  @media (prefers-reduced-motion: no-preference) {
    .app-skeleton {
      animation: skeleton-pulse 1.8s ease-in-out infinite;
    }
  }
  @keyframes skeleton-pulse {
    50% {
      opacity: 0.6;
    }
  }
</style>
