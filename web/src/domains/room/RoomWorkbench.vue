<template>
  <div class="room-workbench">
    <SplitterGroup v-if="!mobile" direction="horizontal" class="room-splitter">
      <SplitterPanel
        id="room-navigation-panel"
        ref="navigationPanel"
        v-slot="{ isCollapsed }"
        class="room-sidebar-panel"
        size-unit="px"
        :order="0"
        :default-size="initialNavigationWidth"
        :min-size="160"
        :max-size="400"
        :collapsed-size="40"
        collapsible
      >
        <div v-if="isCollapsed" class="room-panel-rail">
          <AppTooltip text="展开话题与成员面板">
            <button
              type="button"
              class="icon-button room-panel-restore"
              aria-label="展开左侧面板"
              aria-controls="room-navigation-panel"
              :aria-expanded="false"
              @click="restoreNavigation"
            >
              <AppIcon name="panel-left-open" />
            </button>
          </AppTooltip>
        </div>
        <slot v-else name="sidebar" />
      </SplitterPanel>
      <SplitterResizeHandle
        class="room-resize-handle"
        aria-label="调整左侧面板宽度"
        @dblclick="toggleNavigation"
        @keydown.enter.capture.prevent="toggleNavigation"
      >
        <span class="room-resize-grip"><AppIcon name="grip" /></span>
      </SplitterResizeHandle>
      <SplitterPanel :order="1" :min-size="30" class="room-main-panel">
        <slot />
      </SplitterPanel>
      <SplitterResizeHandle
        v-if="!compact"
        class="room-resize-handle"
        aria-label="调整右侧面板宽度"
        @dblclick="toggleDetails"
        @keydown.enter.capture.prevent="toggleDetails"
      >
        <span class="room-resize-grip"><AppIcon name="grip" /></span>
      </SplitterResizeHandle>
      <SplitterPanel
        v-if="!compact"
        id="room-details-panel"
        ref="detailsPanel"
        v-slot="{ isCollapsed }"
        class="room-details-panel"
        size-unit="px"
        :order="2"
        :default-size="initialDetailsWidth"
        :min-size="280"
        :max-size="640"
        :collapsed-size="40"
        collapsible
      >
        <div v-if="isCollapsed" class="room-panel-rail">
          <AppTooltip text="展开详情与队列面板">
            <button
              type="button"
              class="icon-button room-panel-restore"
              aria-label="展开右侧面板"
              aria-controls="room-details-panel"
              :aria-expanded="false"
              @click="restoreDetails"
            >
              <AppIcon name="panel-right-open" />
            </button>
          </AppTooltip>
        </div>
        <div v-else class="room-context-panel">
          <slot name="details" :collapse="collapseDetails" />
        </div>
      </SplitterPanel>
    </SplitterGroup>
    <template v-else>
      <CollapsibleRoot v-model:open="mobileNavigationOpen" class="room-mobile-navigation">
        <CollapsibleTrigger class="room-mobile-navigation-toggle">
          <AppIcon name="panel-left-open" />
          <span>话题与成员</span>
          <AppIcon name="chevron-down" class="room-mobile-navigation-chevron" />
        </CollapsibleTrigger>
        <CollapsibleContent class="room-mobile-navigation-content">
          <slot name="sidebar" />
        </CollapsibleContent>
      </CollapsibleRoot>
      <slot />
    </template>
    <div v-if="compact" class="room-context-panel" :class="{ 'is-open': detailsOpen }">
      <slot name="details" :collapse="collapseDetails" />
    </div>
  </div>
</template>

<script setup lang="ts">
  import {
    CollapsibleContent,
    CollapsibleRoot,
    CollapsibleTrigger,
    SplitterGroup,
    SplitterPanel,
    SplitterResizeHandle,
  } from "reka-ui";
  import { onBeforeUnmount, ref, watch } from "vue";

  import AppIcon from "@/components/AppIcon.vue";
  import AppTooltip from "@/components/AppTooltip.vue";

  const props = defineProps<{ detailsOpen: boolean }>();
  const emit = defineEmits<{ collapseDetails: [] }>();
  const initialNavigationWidth = 240;
  const initialDetailsWidth = 420;
  const navigationPanel = ref<InstanceType<typeof SplitterPanel>>();
  const detailsPanel = ref<InstanceType<typeof SplitterPanel>>();
  const mobileNavigationOpen = ref(false);
  const mobileQuery = window.matchMedia("(max-width: 720px)");
  const compactQuery = window.matchMedia("(max-width: 1150px)");
  const mobile = ref(mobileQuery.matches);
  const compact = ref(compactQuery.matches);

  function syncViewport(): void {
    mobile.value = mobileQuery.matches;
    compact.value = compactQuery.matches;
  }

  function toggleNavigation(): void {
    if (navigationPanel.value?.isCollapsed) restoreNavigation();
    else navigationPanel.value?.collapse();
  }

  function toggleDetails(): void {
    if (detailsPanel.value?.isCollapsed) restoreDetails();
    else collapseDetails();
  }

  function collapseDetails(): void {
    if (!compact.value) detailsPanel.value?.collapse();
    else emit("collapseDetails");
  }

  function restoreNavigation(): void {
    navigationPanel.value?.resize(initialNavigationWidth);
  }

  function restoreDetails(): void {
    detailsPanel.value?.resize(initialDetailsWidth);
  }

  watch(
    () => detailsPanel.value?.isCollapsed,
    (collapsed) => {
      if (collapsed) emit("collapseDetails");
    },
  );

  watch(
    () => props.detailsOpen,
    (open) => {
      if (open && detailsPanel.value?.isCollapsed) restoreDetails();
    },
  );

  mobileQuery.addEventListener("change", syncViewport);
  compactQuery.addEventListener("change", syncViewport);
  onBeforeUnmount(() => {
    mobileQuery.removeEventListener("change", syncViewport);
    compactQuery.removeEventListener("change", syncViewport);
  });
</script>
