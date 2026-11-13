<template>
  <AppTooltip :text="tooltipText">
    <span
      class="member-identity"
      :class="{
        'message-identity': appearance === 'author',
        'member-identity-text': appearance === 'text',
      }"
      :tabindex="tooltipText ? 0 : undefined"
      v-bind="$attrs"
    >
      <AppIcon name="at" class="member-marker" />
      <span :class="appearance === 'author' ? 'message-author' : 'member-name'">
        {{ member.id === "user" ? t("member.you") : member.name }}
      </span>
    </span>
  </AppTooltip>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import AppIcon from "@/components/AppIcon.vue";
  import AppTooltip from "@/components/AppTooltip.vue";
  import type { Member } from "@/services/roomApi";

  defineOptions({ inheritAttrs: false });
  const { t } = useI18n();
  const props = withDefaults(
    defineProps<{
      member: Pick<Member, "id" | "name">;
      sessionName?: string;
      appearance?: "default" | "author" | "text";
    }>(),
    { appearance: "default", sessionName: undefined },
  );
  const tooltipText = computed(() =>
    props.member.id === "user"
      ? undefined
      : props.sessionName?.trim()
        ? t("member.session", { name: props.sessionName })
        : t("member.sessionUnavailable"),
  );
</script>
