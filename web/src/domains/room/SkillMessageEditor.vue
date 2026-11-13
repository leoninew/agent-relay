<template>
  <div class="skill-message-editor" :class="{ 'is-invalid': invalid, 'is-disabled': disabled }">
    <EditorContent :editor="editor" />
    <AppClearButton
      v-if="modelValue || uploading"
      :label="clearLabel"
      :disabled="disabled"
      @clear="clear"
    />
    <p v-if="uploadError" class="field-error" role="alert">{{ translateMessage(uploadError) }}</p>
  </div>
</template>

<script setup lang="ts">
  import { onBeforeUnmount, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";
  import { EditorContent, useEditor } from "@tiptap/vue-3";
  import { Extension, Node } from "@tiptap/core";
  import Mention from "@tiptap/extension-mention";
  import { UndoRedo } from "@tiptap/extensions";
  import { exitSuggestion, SuggestionPluginKey } from "@tiptap/suggestion";
  import { EditorState, Plugin, TextSelection } from "@tiptap/pm/state";
  import { Slice } from "@tiptap/pm/model";
  import AppClearButton from "@/components/AppClearButton.vue";
  import { translateMessage } from "@/i18n";
  import type { MessageDescriptor } from "@/i18n";
  import { createImageUploads } from "@/domains/room/messageImageUploads";
  import {
    formatSkillReference,
    isSkillTriggerPrefix,
    isSourcePosition,
  } from "@/domains/room/inlineSkills";
  import {
    decodeMessage,
    documentSkills,
    messageSlice,
    nodeSource,
    reconcileReferences,
    sourceOffset,
  } from "@/domains/room/messageEditorCodec";
  import {
    messageMaxLength,
    readSkillClipboard,
    skillClipboardType,
    writeSkillClipboard,
  } from "@/domains/room/skillEditorModel";
  import type { SkillReference } from "@/services/roomApi";
  import { skillIcon } from "@/domains/room/skillIcon";

  defineOptions({ inheritAttrs: false });
  const props = defineProps<{
    roomId: string;
    modelValue: string;
    skills: SkillReference[];
    availableSkills: (SkillReference & { description?: string })[];
    skillDescriptions?: ReadonlyMap<string, string>;
    id: string;
    label: string;
    placeholder: string;
    clearLabel: string;
    removeLabel: string;
    disabled?: boolean;
    invalid?: boolean;
    describedBy?: string;
    pickerOpen?: boolean;
    activeDescendant?: string;
  }>();
  const emit = defineEmits<{
    change: [content: string, skills: SkillReference[]];
    query: [query: { text: string } | undefined];
    keydown: [event: KeyboardEvent];
    compositionstart: [];
    compositionend: [];
    tooLong: [];
    uploading: [value: boolean];
  }>();
  const identities = new Map<string, SkillReference>();
  const { t } = useI18n();
  const uploading = ref(false);
  const uploadError = ref<MessageDescriptor>();
  let disposed = false;
  let composing = false;
  let compositionTimer: ReturnType<typeof setTimeout> | undefined;
  let output = props.modelValue;
  let outputIdentity = JSON.stringify(props.skills);
  function remember(skills: readonly SkillReference[]): void {
    for (const skill of skills) identities.set(skill.id, { ...skill });
  }
  remember(props.skills);
  const knownSkills = () => [...identities.values()];
  const uploads = createImageUploads({
    roomId: props.roomId,
    editor: () => editor.value,
    disabled: () => Boolean(props.disabled),
    composing: () => composing,
    label: (name) => t("composer.uploadingImage", { name }),
    removeLabel: () => t("composer.cancelImageUpload"),
    changed(value) {
      uploading.value = value;
      emit("uploading", value);
    },
    error(error) {
      uploadError.value = error;
    },
  });
  const showQuery = (value: { query: string }) => {
    emit("query", { text: value.query });
  };
  const Doc = Node.create({ name: "doc", topNode: true, content: "messageBody" });
  const Body = Node.create({
    name: "messageBody",
    content: "inline*",
    whitespace: "pre",
    defining: true,
    parseHTML: () => [{ tag: "div[data-message-body]", preserveWhitespace: "full" }],
    renderHTML: () => ["div", { "data-message-body": "" }, 0],
  });
  const Text = Node.create({ name: "text", group: "inline" });
  const Break = Node.create({
    name: "hardBreak",
    inline: true,
    group: "inline",
    selectable: false,
    linebreakReplacement: true,
    addAttributes: () => ({ raw: { default: "\n", rendered: false } }),
    parseHTML: () => [{ tag: "br" }],
    renderHTML: () => ["br"],
    renderText: ({ node }) => node.attrs.raw as string,
  });
  const Skill = Mention.extend({
    selectable: true,
    addAttributes() {
      return { ...this.parent?.(), marker: { default: "", rendered: false } };
    },
    // All pasted content is handled by our text/private clipboard adapter.
    parseHTML: () => [],
  }).configure({
    deleteTriggerWithBackspace: true,
    renderText: ({ node }) => `$${node.attrs.label as string}`,
    renderHTML: ({ node }) => [
      "span",
      {
        class: "editor-reference editor-skill",
        "data-skill-id": node.attrs.id as string,
        title:
          props.skillDescriptions?.get(node.attrs.id as string)?.trim() ||
          (node.attrs.label as string),
      },
      (() => {
        const icon = document.createElement("span");
        icon.className = "editor-skill-icon";
        icon.innerHTML = skillIcon;
        return icon;
      })(),
      ["span", { class: "editor-skill-label" }, node.attrs.label as string],
      [
        "span",
        {
          "data-remove-reference": "",
          role: "button",
          "aria-label": `${props.removeLabel}: ${node.attrs.label as string}`,
        },
        "×",
      ],
    ],
    suggestion: {
      pluginKey: SuggestionPluginKey,
      char: "$",
      allowedPrefixes: null,
      findSuggestionMatch: ({ $position }) => {
        const before = $position.nodeBefore?.isText ? ($position.nodeBefore.text ?? "") : "";
        const match = /\$([\p{L}\p{N}_:./@-]*)$/u.exec(before);
        if (!match) return null;
        const after = $position.nodeAfter?.isText ? ($position.nodeAfter.text ?? "") : "";
        const suffix = /^[\p{L}\p{N}_:./@-]*/u.exec(after)?.[0] ?? "";
        const from = $position.pos - match[0].length;
        const source = nodeSource($position.doc);
        const start = sourceOffset($position.doc, from);
        if (!isSkillTriggerPrefix(source, start) || !isSourcePosition(source, start)) return null;
        return {
          range: { from, to: $position.pos + suffix.length },
          query: match[1],
          text: match[0] + suffix,
        };
      },
      allow: () => !props.disabled && !composing,
      items: () => [],
      render: () => ({
        onStart: showQuery,
        onUpdate: showQuery,
        onExit: () => {
          emit("query", undefined);
        },
      }),
    },
  });
  const Image = Node.create({
    name: "imageReference",
    group: "inline",
    inline: true,
    atom: true,
    selectable: true,
    addAttributes: () =>
      Object.fromEntries(
        ["id", "url", "alt", "marker"].map((key) => [key, { default: "", rendered: false }]),
      ),
    parseHTML: () => [],
    renderHTML: ({ node }) => [
      "span",
      { class: "editor-reference editor-image", title: node.attrs.url as string },
      ["span", { "aria-hidden": "true" }, "▧"],
      ["span", {}, node.attrs.alt as string],
      [
        "span",
        { "data-remove-reference": "", role: "button", "aria-label": props.removeLabel },
        "×",
      ],
    ],
  });
  const Contract = Extension.create({
    name: "messageContract",
    priority: 1000,
    addProseMirrorPlugins() {
      return [
        uploads.plugin,
        new Plugin({
          filterTransaction(tr, state) {
            if (!tr.docChanged || tr.getMeta("externalContent")) return true;
            const next = nodeSource(tr.doc).length;
            if (next <= messageMaxLength || next <= nodeSource(state.doc).length) return true;
            emit("tooLong");
            return false;
          },
          appendTransaction(transactions, _old, state) {
            if (composing || !transactions.some((tr) => tr.docChanged)) return null;
            const tr = reconcileReferences(state.tr, knownSkills(), props.roomId);
            return tr.docChanged ? tr : null;
          },
        }),
      ];
    },
  });

  function copy(event: ClipboardEvent, cut = false): boolean {
    const active = editor.value;
    if (!active || !event.clipboardData || active.state.selection.empty || (cut && props.disabled))
      return false;
    const fragment = active.state.selection.content().content;
    let text = "";
    fragment.forEach((node) => {
      text += nodeSource(node);
    });
    const payload = writeSkillClipboard(text, knownSkills());
    event.preventDefault();
    event.clipboardData.setData("text/plain", payload.text);
    event.clipboardData.setData(skillClipboardType, payload.data);
    if (cut) active.commands.deleteSelection();
    return true;
  }
  const editor = useEditor({
    extensions: [Doc, Body, Text, Break, Skill, Image, UndoRedo, Contract],
    content: decodeMessage(props.modelValue, knownSkills(), props.roomId),
    editable: !props.disabled,
    enableInputRules: false,
    enablePasteRules: false,
    editorProps: {
      attributes: () => ({
        id: props.id,
        role: props.pickerOpen ? "combobox" : "textbox",
        "aria-label": props.label,
        "aria-multiline": "true",
        "aria-disabled": String(Boolean(props.disabled)),
        "aria-invalid": String(Boolean(props.invalid)),
        "aria-placeholder": props.placeholder,
        "data-placeholder": props.placeholder,
        "aria-expanded": String(Boolean(props.pickerOpen)),
        "aria-autocomplete": "list",
        ...(props.describedBy ? { "aria-describedby": props.describedBy } : {}),
        ...(props.pickerOpen ? { "aria-controls": "capability-options" } : {}),
        ...(props.activeDescendant ? { "aria-activedescendant": props.activeDescendant } : {}),
      }),
      handleKeyDown(view, event) {
        if (props.disabled) return true;
        if (composing || view.composing || event.isComposing || event.keyCode === 229) return false;
        emit("keydown", event);
        if (event.defaultPrevented) return true;
        if (event.key === "Enter") {
          if (event.shiftKey)
            view.dispatch(
              view.state.tr.replaceSelectionWith(view.state.schema.nodes.hardBreak.create()),
            );
          return true;
        }
        return false;
      },
      handlePaste(view, event) {
        if (props.disabled || composing) return true;
        const copied = readSkillClipboard(event.clipboardData?.getData(skillClipboardType) ?? "", [
          ...knownSkills(),
          ...props.availableSkills,
        ]);
        const text = event.clipboardData?.getData("text/plain").replace(/\r\n?/g, "\n") ?? "";
        event.preventDefault();
        if (!copied && !text) return true;
        if (copied) remember(copied.skills);
        view.dispatch(
          view.state.tr
            .replaceSelection(
              new Slice(
                messageSlice(
                  view.state.schema,
                  copied?.content ?? text,
                  knownSkills(),
                  props.roomId,
                ),
                0,
                0,
              ),
            )
            .scrollIntoView(),
        );
        return true;
      },
      handleDrop(view, event) {
        if (props.disabled || composing) return true;
        if (view.dragging) return false;
        const text = event.dataTransfer?.getData("text/plain").replace(/\r\n?/g, "\n") ?? "";
        const position = view.posAtCoords({ left: event.clientX, top: event.clientY })?.pos;
        if (text && position !== undefined)
          view.dispatch(
            view.state.tr.insert(
              Math.max(1, Math.min(position, view.state.doc.content.size - 1)),
              messageSlice(view.state.schema, text, knownSkills(), props.roomId),
            ),
          );
        return true;
      },
      handleClickOn(view, _pos, node, nodePos, event, direct) {
        if (
          !direct ||
          props.disabled ||
          !(event.target instanceof Element) ||
          !event.target.closest("[data-remove-reference]")
        )
          return false;
        if (!["mention", "imageReference"].includes(node.type.name)) return false;
        view.dispatch(view.state.tr.delete(nodePos, nodePos + node.nodeSize));
        return true;
      },
      handleDOMEvents: {
        beforeinput(view, event) {
          if (props.disabled) {
            event.preventDefault();
            return true;
          }
          if (composing || view.composing || event.isComposing) return false;
          if (!["insertParagraph", "insertLineBreak"].includes(event.inputType)) return false;
          event.preventDefault();
          if (event.inputType === "insertLineBreak")
            view.dispatch(
              view.state.tr.replaceSelectionWith(view.state.schema.nodes.hardBreak.create()),
            );
          else emit("keydown", new KeyboardEvent("keydown", { key: "Enter", cancelable: true }));
          return true;
        },
        paste(view, event) {
          const files = [...(event.clipboardData?.files ?? [])].filter((file) =>
            file.type.startsWith("image/"),
          );
          if (!files.length) return false;
          event.preventDefault();
          uploadError.value = undefined;
          uploads.add(view, files);
          return true;
        },
        dragover: (_view, event) => {
          if (!event.dataTransfer?.types.includes("Files")) return false;
          event.preventDefault();
          return true;
        },
        drop(view, event) {
          const files = [...(event.dataTransfer?.files ?? [])].filter((file) =>
            file.type.startsWith("image/"),
          );
          if (!files.length) return false;
          event.preventDefault();
          const position = view.posAtCoords({ left: event.clientX, top: event.clientY })?.pos;
          uploadError.value = undefined;
          uploads.add(view, files, position);
          return true;
        },
        copy: (_view, event) => copy(event),
        cut: (_view, event) => copy(event, true),
        compositionstart: () => {
          if (compositionTimer) clearTimeout(compositionTimer);
          compositionTimer = undefined;
          composing = true;
          emit("compositionstart");
          emit("query", undefined);
          return false;
        },
        compositionend: () => {
          if (compositionTimer) clearTimeout(compositionTimer);
          // ProseMirror's built-in handler flushes the final DOM input in a microtask.
          // Keep the guard active until a subsequent task sees the committed state.
          compositionTimer = setTimeout(() => {
            compositionTimer = undefined;
            const active = editor.value;
            if (!active || disposed || active.isDestroyed) return;
            composing = false;
            emit("compositionend");
            if (props.disabled || active.view.composing) return;
            const tr = reconcileReferences(active.state.tr, knownSkills(), props.roomId);
            if (tr.docChanged) active.view.dispatch(tr);
            uploads.flush();
          }, 0);
          return false;
        },
      },
    },
    onUpdate({ editor: active }) {
      if (disposed || props.disabled) return;
      const content = nodeSource(active.state.doc);
      const selected = documentSkills(active.state.doc);
      const identity = JSON.stringify(selected);
      if (content === output && identity === outputIdentity) return;
      output = content;
      outputIdentity = identity;
      remember(selected);
      emit("change", content, knownSkills());
    },
  });
  function refreshSkillTooltips(): void {
    const root = editor.value?.view.dom;
    if (!root) return;
    for (const element of root.querySelectorAll<HTMLElement>("[data-skill-id]")) {
      const label = element.querySelector<HTMLElement>(".editor-skill-label")?.textContent ?? "";
      element.title = props.skillDescriptions?.get(element.dataset.skillId ?? "")?.trim() || label;
    }
  }
  function focus(): void {
    if (!props.disabled) editor.value?.commands.focus();
  }
  function dismissQuery(): void {
    if (editor.value) exitSuggestion(editor.value.view, SuggestionPluginKey);
  }
  function insertSkill(reference: SkillReference): void {
    const active = editor.value;
    if (!active || props.disabled || composing || disposed) return;
    const suggestion = SuggestionPluginKey.getState(active.state) as
      { active: boolean; range: { from: number; to: number } } | undefined;
    if (!suggestion?.active) return;
    const range = suggestion.range;
    remember([reference]);
    active
      .chain()
      .focus()
      .insertContentAt(range, [
        {
          type: "mention",
          attrs: {
            id: reference.id,
            label: reference.name,
            marker: formatSkillReference(reference),
          },
        },
        { type: "text", text: " " },
      ])
      .run();
  }
  function clear(): void {
    const active = editor.value;
    if (!active || props.disabled || composing) return;
    uploads.cancelAll();
    uploadError.value = undefined;
    active.view.dispatch(active.state.tr.delete(1, active.state.doc.content.size - 1));
    focus();
  }
  watch(
    () => props.modelValue,
    (value) => {
      const active = editor.value;
      if (!active || value === nodeSource(active.state.doc)) return;
      uploads.cancelAll();
      if (compositionTimer) clearTimeout(compositionTimer);
      compositionTimer = undefined;
      composing = false;
      emit("compositionend");
      remember(props.skills);
      output = value;
      const doc = active.schema.nodeFromJSON(decodeMessage(value, knownSkills(), props.roomId));
      outputIdentity = JSON.stringify(documentSkills(doc));
      active.view.updateState(
        EditorState.create({
          doc,
          schema: active.schema,
          plugins: active.state.plugins,
          selection: TextSelection.atEnd(doc),
        }),
      );
      emit("query", undefined);
    },
    { flush: "post" },
  );
  watch(
    () => props.skills,
    (skills) => {
      remember(skills);
      const active = editor.value;
      if (active && !props.disabled && !composing) {
        const tr = reconcileReferences(active.state.tr, knownSkills(), props.roomId);
        if (tr.docChanged) active.view.dispatch(tr.setMeta("addToHistory", false));
      }
    },
    { deep: true },
  );
  watch(
    () => props.availableSkills,
    () => refreshSkillTooltips(),
    { deep: true, flush: "post" },
  );
  watch(
    () => props.skillDescriptions,
    () => refreshSkillTooltips(),
    { deep: true, flush: "post" },
  );
  watch(
    () => props.disabled,
    (disabled) => {
      editor.value?.setEditable(!disabled, false);
      if (disabled) {
        uploads.cancelAll();
        dismissQuery();
      } else if (editor.value && !composing) {
        const tr = reconcileReferences(editor.value.state.tr, knownSkills(), props.roomId);
        if (tr.docChanged) editor.value.view.dispatch(tr.setMeta("addToHistory", false));
      }
    },
  );
  watch(
    () => [
      props.invalid,
      props.label,
      props.placeholder,
      props.describedBy,
      props.pickerOpen,
      props.activeDescendant,
    ],
    () => {
      const active = editor.value;
      if (active) active.setOptions({ editorProps: active.options.editorProps });
    },
    { flush: "post" },
  );
  onBeforeUnmount(() => {
    disposed = true;
    if (compositionTimer) clearTimeout(compositionTimer);
    uploads.destroy();
  });
  defineExpose({ focus, insertSkill, dismissQuery, clear });
</script>

<style scoped>
  .skill-message-editor {
    position: relative;
    min-width: 0;
  }
  .skill-message-editor :deep(.tiptap) {
    min-height: 2lh;
    max-height: 6lh;
    padding-right: 30px;
    overflow-y: auto;
    outline: none;
    font: inherit;
    line-height: var(--line-height-body);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .skill-message-editor :deep([data-message-body]) {
    margin: 0;
  }
  .skill-message-editor :deep(.tiptap:has([data-message-body]:only-child > br:only-child)::before) {
    content: attr(data-placeholder);
    position: absolute;
    color: hsl(var(--muted-foreground));
    pointer-events: none;
  }
  .skill-message-editor :deep(.editor-reference) {
    display: inline-flex;
    align-items: baseline;
    gap: 4px;
    max-width: 100%;
    color: hsl(var(--primary));
    vertical-align: baseline;
    white-space: nowrap;
    user-select: all;
  }
  .skill-message-editor :deep(.editor-reference:not(.editor-skill)) {
    margin: 0 1px;
    padding: 0 4px;
    border: 1px solid hsl(var(--primary) / 0.12);
    border-radius: 4px;
    background: hsl(var(--primary) / 0.08);
  }
  .skill-message-editor :deep(.editor-skill) {
    display: inline;
    font: inherit;
    white-space: inherit;
    cursor: help;
  }
  .skill-message-editor :deep(.editor-reference:not(.editor-skill) > span:nth-child(2)) {
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .skill-message-editor :deep(.editor-skill-icon svg) {
    display: inline-block;
    width: 1em;
    height: 1em;
    margin-inline-end: 4px;
    vertical-align: -0.125em;
  }
  .skill-message-editor :deep([data-remove-reference]) {
    cursor: pointer;
    padding-inline: 2px;
  }
  .skill-message-editor :deep(.editor-upload) {
    color: hsl(var(--muted-foreground));
  }
  .skill-message-editor :deep(.editor-upload button) {
    border: 0;
    background: transparent;
    color: inherit;
    cursor: pointer;
  }
  .skill-message-editor :deep(.ProseMirror-selectednode:not(.editor-skill)) {
    outline: 1px solid hsl(var(--primary));
  }
  .skill-message-editor.is-invalid {
    border-bottom: 1px solid hsl(var(--destructive));
  }
  .skill-message-editor.is-disabled {
    opacity: 0.6;
  }
  .skill-message-editor > .app-clear-button {
    position: absolute;
    top: 0;
    right: 0;
  }
</style>
