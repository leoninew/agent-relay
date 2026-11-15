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
          <slot name="sidebar" :close-navigation="closeNavigation" />
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
        @keydown.capture="guardCollapsedResize($event, navigationPanel?.isCollapsed)"
      />
      <SplitterPanel :order="1" :min-size="30" class="room-main-panel">
        <slot />
      </SplitterPanel>
      <SplitterResizeHandle
        v-if="!compact"
        class="room-resize-handle"
        :aria-label="t('sidebar.resizeRight')"
        @keydown.capture="guardCollapsedResize($event, detailsPanel?.isCollapsed)"
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
        :min-size="160"
        :max-size="400"
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
      <DialogRoot v-model:open="mobileNavigationOpen">
        <DialogTrigger class="room-mobile-navigation-toggle">
          <AppIcon name="panel-left-open" />
          <span>{{ t("room.navigation") }}</span>
          <AppIcon name="chevron" class="room-mobile-navigation-chevron" />
        </DialogTrigger>
        <DialogPortal>
          <DialogOverlay class="room-drawer-overlay" />
          <DialogContent class="room-navigation-drawer" :aria-describedby="undefined">
            <header class="room-panel-heading room-navigation-heading">
              <DialogTitle class="room-panel-title">{{ t("room.navigation") }}</DialogTitle>
              <DialogClose class="icon-button" :aria-label="t('sidebar.collapseLeft')">
                <AppIcon name="close" />
              </DialogClose>
            </header>
            <slot name="sidebar" :close-navigation="closeNavigation" />
          </DialogContent>
        </DialogPortal>
      </DialogRoot>
      <slot />
    </template>
    <DialogRoot v-if="compact" :open="detailsOpen" @update:open="updateDetailsOpen">
      <DialogPortal>
        <DialogOverlay class="room-drawer-overlay" />
        <DialogContent
          class="room-context-panel room-details-drawer"
          :aria-describedby="undefined"
          @close-auto-focus="restoreDetailsFocus"
        >
          <DialogTitle class="sr-only">{{ t("sidebar.details") }}</DialogTitle>
          <slot name="details" :collapse="collapseDetails" />
        </DialogContent>
      </DialogPortal>
    </DialogRoot>
  </div>
</template>

<script setup lang="ts">
  import {
    DialogClose,
    DialogContent,
    DialogOverlay,
    DialogPortal,
    DialogRoot,
    DialogTitle,
    DialogTrigger,
    SplitterGroup,
    SplitterPanel,
    SplitterResizeHandle,
  } from "reka-ui";
  import { nextTick, onBeforeUnmount, onDeactivated, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import AppIcon from "@/components/AppIcon.vue";
  import AppTooltip from "@/components/AppTooltip.vue";
  import { usePanelPreferencesStore } from "@/stores/panelPreferences";

  const { t } = useI18n();
  const props = defineProps<{ detailsOpen: boolean }>();
  const emit = defineEmits<{ collapseDetails: [] }>();
  const initialNavigationWidth = 240;
  const initialDetailsWidth = 300;
  const panelPreferences = usePanelPreferencesStore();
  const navigationPanel = ref<InstanceType<typeof SplitterPanel>>();
  const detailsPanel = ref<InstanceType<typeof SplitterPanel>>();
  const mobileNavigationOpen = ref(false);
  const mobileQuery = window.matchMedia("(max-width: 720px)");
  const compactQuery = window.matchMedia("(max-width: 1150px)");
  const mobile = ref(mobileQuery.matches);
  const compact = ref(compactQuery.matches);
  let previousDetailsFocus: HTMLElement | null = null;
  let changingViewport = false;

  function syncViewport(): void {
    if (mobile.value === mobileQuery.matches && compact.value === compactQuery.matches) return;
    changingViewport = true;
    mobile.value = mobileQuery.matches;
    compact.value = compactQuery.matches;
    closeNavigation();
    void nextTick(() => {
      changingViewport = false;
    });
  }

  function savePanelState(panel: "navigation" | "details", collapsed: boolean): void {
    if (!changingViewport) panelPreferences.setCollapsed(panel, collapsed);
  }

  function collapseDetails(): void {
    if (!compact.value) detailsPanel.value?.collapse();
    else emit("collapseDetails");
  }

  function closeNavigation(): void {
    mobileNavigationOpen.value = false;
  }

  function updateDetailsOpen(open: boolean): void {
    if (!open) emit("collapseDetails");
  }

  function restoreDetailsFocus(event: Event): void {
    if (previousDetailsFocus?.isConnected) {
      event.preventDefault();
      previousDetailsFocus.focus({ preventScroll: true });
    }
  }

  function guardCollapsedResize(event: KeyboardEvent, collapsed: boolean | undefined): void {
    if (
      event.key === "Enter" ||
      (collapsed &&
        ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key))
    ) {
      event.preventDefault();
    }
  }

  function restoreNavigation(): void {
    navigationPanel.value?.resize(initialNavigationWidth);
  }

  function restoreDetails(): void {
    detailsPanel.value?.resize(initialDetailsWidth);
  }

  watch(
    () => props.detailsOpen,
    (open) => {
      if (open) {
        previousDetailsFocus =
          document.activeElement instanceof HTMLElement ? document.activeElement : null;
      }
      if (open && !compact.value && detailsPanel.value?.isCollapsed) restoreDetails();
    },
  );

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

  mobileQuery.addEventListener("change", syncViewport);
  compactQuery.addEventListener("change", syncViewport);
  onDeactivated(() => {
    closeNavigation();
    emit("collapseDetails");
  });
  onBeforeUnmount(() => {
    mobileQuery.removeEventListener("change", syncViewport);
    compactQuery.removeEventListener("change", syncViewport);
  });
</script>
