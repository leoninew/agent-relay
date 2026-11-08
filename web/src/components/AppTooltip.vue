<template>
  <TooltipProvider :delay-duration="200">
    <TooltipRoot>
      <TooltipTrigger as-child><slot /></TooltipTrigger>
      <TooltipPortal>
        <div class="app-tooltip-layer">
          <TooltipContent class="app-tooltip" :side-offset="6" :collision-padding="12">
            {{ text }}
            <TooltipArrow class="app-tooltip-arrow" />
          </TooltipContent>
        </div>
      </TooltipPortal>
    </TooltipRoot>
  </TooltipProvider>
</template>

<script setup lang="ts">
  import {
    TooltipArrow,
    TooltipContent,
    TooltipPortal,
    TooltipProvider,
    TooltipRoot,
    TooltipTrigger,
  } from "reka-ui";

  defineProps<{ text: string }>();
</script>

<style>
  .app-tooltip-layer {
    position: relative;
    z-index: 60;
  }

  .app-tooltip {
    max-width: min(320px, calc(100vw - 24px));
    padding: 10px 12px;
    border: 1px solid hsl(var(--border));
    border-radius: 8px;
    background: hsl(var(--popover));
    color: hsl(var(--popover-foreground));
    font-size: var(--font-size-body);
    line-height: var(--line-height-body);
    font-weight: 400;
    overflow-wrap: anywhere;
    box-shadow: 0 4px 16px hsl(222 30% 10% / 0.12);
  }

  .app-tooltip-arrow {
    fill: hsl(var(--popover));
  }
</style>
