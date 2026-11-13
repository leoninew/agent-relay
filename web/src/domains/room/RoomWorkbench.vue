<template>
  <div class="room-workbench">
    <SplitterGroup
      v-if="!mobile"
      :key="compact ? 'compact' : 'wide'"
      direction="horizontal"
      class="room-splitter"
    >
      <SplitterPanel
        id="room-navigation-panel"
        ref="navigationPanel"
        v-slot="{ isCollapsed }"
        class="room-sidebar-panel"
        size-unit="px"
        :order="0"
        :default-size="panelPreferences.collapsed.navigation ? 40 : initialNavigationWidth"
        :min-size="160"
        :max-size="400"
        :collapsed-size="40"
        collapsible
      >
        <div v-if="isCollapsed" class="room-panel-rail">
          <AppTooltip :text="t('sidebar.openNavigation')">
            <button
              type="button"
              class="icon-button room-panel-restore"
              :aria-label="t('sidebar.openLeft')"
              aria-controls="room-navigation-panel"
              :aria-expanded="false"
              @click="restoreNavigation"
            >
              <AppIcon name="panel-left-open" />
            </button>
          </AppTooltip>
        </div>
        <template v-else>
          <slot name="sidebar" />
          <div class="room-panel-footer">
            <AppTooltip :text="t('sidebar.collapseLeft')">
              <button
                type="button"
                class="icon-button room-panel-collapse"
                :aria-label="t('sidebar.collapseLeft')"
                aria-controls="room-navigation-panel"
                :aria-expanded="true"
                @mousedown.stop
                @touchstart.stop
                @click="navigationPanel?.collapse()"
              >
                <AppIcon name="panel-left-close" />
              </button>
            </AppTooltip>
          </div>
        </template>
      </SplitterPanel>
      <SplitterResizeHandle
        class="room-resize-handle"
        :aria-label="t('sidebar.resizeLeft')"
        @dblclick="toggleNavigation"
        @keydown.enter.capture.prevent="toggleNavigation"
      />
      <SplitterPanel :order="1" :min-size="30" class="room-main-panel">
        <slot />
      </SplitterPanel>
      <SplitterResizeHandle
        v-if="!compact"
        class="room-resize-handle"
        :aria-label="t('sidebar.resizeRight')"
        @dblclick="toggleDetails"
        @keydown.enter.capture.prevent="toggleDetails"
      />
      <SplitterPanel
        v-if="!compact"
        id="room-details-panel"
        ref="detailsPanel"
        v-slot="{ isCollapsed }"
        class="room-details-panel"
        size-unit="px"
        :order="2"
        :default-size="panelPreferences.collapsed.details ? 40 : initialDetailsWidth"
        :min-size="280"
        :max-size="640"
        :collapsed-size="40"
        collapsible
      >
        <div v-if="isCollapsed" class="room-panel-rail">
          <AppTooltip :text="t('sidebar.openDetails')">
            <button
              type="button"
              class="icon-button room-panel-restore"
              :aria-label="t('sidebar.openRight')"
              aria-controls="room-details-panel"
              :aria-expanded="false"
              @click="restoreDetails"
            >
              <AppIcon name="panel-right-open" />
            </button>
          </AppTooltip>
        </div>
        <template v-else>
          <div class="room-context-panel">
            <slot name="details" :collapse="collapseDetails" />
          </div>
          <div class="room-panel-footer">
            <AppTooltip :text="t('sidebar.collapseRight')">
              <button
                type="button"
                class="icon-button room-panel-collapse"
                :aria-label="t('sidebar.collapseRight')"
                aria-controls="room-details-panel"
                :aria-expanded="true"
                @mousedown.stop
                @touchstart.stop
                @click="collapseDetails"
              >
                <AppIcon name="panel-right-close" />
              </button>
            </AppTooltip>
          </div>
        </template>
      </SplitterPanel>
    </SplitterGroup>
    <template v-else>
      <CollapsibleRoot v-model:open="mobileNavigationOpen" class="room-mobile-navigation">
        <CollapsibleTrigger class="room-mobile-navigation-toggle">
          <AppIcon name="panel-left-open" />
          <span>{{ t("room.navigation") }}</span>
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
  import { nextTick, onBeforeUnmount, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import AppIcon from "@/components/AppIcon.vue";
  import AppTooltip from "@/components/AppTooltip.vue";
  import { usePanelPreferencesStore } from "@/stores/panelPreferences";

  const { t } = useI18n();
  const props = defineProps<{ detailsOpen: boolean }>();
  const emit = defineEmits<{ collapseDetails: [] }>();
  const initialNavigationWidth = 240;
  const initialDetailsWidth = 420;
  const panelPreferences = usePanelPreferencesStore();
  const navigationPanel = ref<InstanceType<typeof SplitterPanel>>();
  const detailsPanel = ref<InstanceType<typeof SplitterPanel>>();
  const mobileNavigationOpen = ref(false);
  const mobileQuery = window.matchMedia("(max-width: 720px)");
  const compactQuery = window.matchMedia("(max-width: 1150px)");
  const mobile = ref(mobileQuery.matches);
  const compact = ref(compactQuery.matches);
  let changingViewport = false;

  function syncViewport(): void {
    if (mobile.value === mobileQuery.matches && compact.value === compactQuery.matches) return;
    changingViewport = true;
    mobile.value = mobileQuery.matches;
    compact.value = compactQuery.matches;
    void nextTick(() => {
      changingViewport = false;
    });
  }

  function savePanelState(panel: "navigation" | "details", collapsed: boolean): void {
    if (!changingViewport) panelPreferences.setCollapsed(panel, collapsed);
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
    () => navigationPanel.value?.isCollapsed,
    (collapsed, previous) => {
      if (typeof collapsed === "boolean" && typeof previous === "boolean") {
        savePanelState("navigation", collapsed);
      }
    },
    { flush: "sync" },
  );

  watch(
    () => detailsPanel.value?.isCollapsed,
    (collapsed, previous) => {
      if (typeof collapsed === "boolean" && typeof previous === "boolean") {
        savePanelState("details", collapsed);
      }
    },
    { flush: "sync" },
  );

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
