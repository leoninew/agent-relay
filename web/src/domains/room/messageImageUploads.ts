import type { Editor } from "@tiptap/core";
import { closeHistory } from "@tiptap/pm/history";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import type { EditorView } from "@tiptap/pm/view";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import { imageReferences } from "@/domains/room/messageEditorCodec";
import { messageMaxLength } from "@/domains/room/skillEditorModel";
import { nodeSource } from "@/domains/room/messageEditorCodec";
import { uploadRoomImage } from "@/services/roomApi";
import type { UploadedImage } from "@/services/roomApi";
import { describeApiError } from "@/services/api";
import type { MessageDescriptor } from "@/i18n";

const uploadsKey = new PluginKey<DecorationSet>("messageImageUploads");
type Upload = {
  id: object;
  batch: object;
  file: File;
  controller: AbortController;
  result?: UploadedImage;
  failed?: boolean;
};
type UploadMeta = { add?: Decoration[]; remove?: object[]; clear?: boolean };

export function createImageUploads(options: {
  roomId: string;
  editor: () => Editor | undefined;
  disabled: () => boolean;
  composing: () => boolean;
  label: (name: string) => string;
  removeLabel: () => string;
  changed: (value: boolean) => void;
  error: (error: MessageDescriptor) => void;
}) {
  const tasks: Upload[] = [];
  let disposed = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const placeholders = (view: EditorView) => uploadsKey.getState(view.state) ?? DecorationSet.empty;
  function report(): void {
    options.changed(tasks.length > 0);
  }
  function cancel(ids: object[]): void {
    for (let index = tasks.length - 1; index >= 0; index--) {
      if (!ids.includes(tasks[index].id)) continue;
      tasks[index].controller.abort();
      tasks.splice(index, 1);
    }
    report();
  }
  function remove(view: EditorView, id: object): void {
    cancel([id]);
    view.dispatch(
      view.state.tr
        .setMeta(uploadsKey, { remove: [id] } satisfies UploadMeta)
        .setMeta("addToHistory", false),
    );
    queueMicrotask(flush);
  }
  function flush(): void {
    if (timer) clearTimeout(timer);
    timer = undefined;
    const active = options.editor();
    if (disposed || !active || active.isDestroyed) return;
    if (options.disabled()) {
      cancelAll();
      return;
    }
    if (options.composing() || active.view.composing) {
      if (tasks.some((task) => task.result || task.failed)) timer = setTimeout(flush, 50);
      return;
    }
    for (const batch of new Set(tasks.map((task) => task.batch))) {
      for (const task of tasks.filter((task) => task.batch === batch)) {
        if (!tasks.includes(task)) continue;
        if (!task.result && !task.failed) break;
        const anchor = placeholders(active.view)
          .find()
          .find((item) => item.spec.id === task.id);
        if (!anchor || task.failed) {
          remove(active.view, task.id);
          continue;
        }
        const image = imageReferences(task.result!.markdown, options.roomId)[0];
        if (
          !image ||
          image.start !== 0 ||
          image.end !== task.result!.markdown.length ||
          image.node.attrs?.id !== task.result!.id ||
          image.node.attrs?.url !== task.result!.url
        ) {
          options.error({ key: "composer.imageUploadFailed" });
          remove(active.view, task.id);
          continue;
        }
        if (nodeSource(active.state.doc).length + task.result!.markdown.length > messageMaxLength) {
          options.error({ key: "validation.contentTooLong" });
          remove(active.view, task.id);
          continue;
        }
        const node = active.schema.nodeFromJSON(image.node);
        const tr = closeHistory(active.state.tr)
          .insert(anchor.from, node)
          .setMeta(uploadsKey, { remove: [task.id] } satisfies UploadMeta);
        // Remove the live task before dispatch: plugin updates cannot cancel a completed result.
        cancel([task.id]);
        active.view.dispatch(tr);
      }
    }
  }
  function cancelAll(): void {
    cancel(tasks.map((task) => task.id));
    if (timer) clearTimeout(timer);
    timer = undefined;
    const active = options.editor();
    if (active && !active.isDestroyed)
      active.view.dispatch(
        active.state.tr
          .setMeta(uploadsKey, { clear: true } satisfies UploadMeta)
          .setMeta("addToHistory", false),
      );
  }
  function add(view: EditorView, files: File[], position?: number): void {
    if (disposed || options.disabled() || options.composing() || view.composing) return;
    const accepted = files.filter((file) => {
      const key =
        file.size > 10 * 1024 * 1024
          ? "errors.image_too_large"
          : !["image/png", "image/jpeg", "image/webp"].includes(file.type)
            ? "errors.image_invalid"
            : undefined;
      if (key) options.error({ key });
      return !key;
    });
    if (!accepted.length) return;
    const tr = view.state.tr;
    if (position === undefined) tr.deleteSelection();
    const pos = Math.max(1, Math.min(position ?? tr.selection.from, tr.doc.content.size - 1));
    const batch = {};
    const added = accepted.map((file): Upload => ({
      id: {},
      batch,
      file,
      controller: new AbortController(),
    }));
    tasks.push(...added);
    const widgets = added.map((task) =>
      Decoration.widget(
        pos,
        () => {
          const element = document.createElement("span");
          element.className = "editor-reference editor-upload";
          element.contentEditable = "false";
          const label = document.createElement("span");
          label.textContent = options.label(task.file.name);
          const button = document.createElement("button");
          button.type = "button";
          button.textContent = "×";
          button.setAttribute("aria-label", options.removeLabel());
          button.addEventListener("mousedown", (event) => event.preventDefault());
          button.addEventListener("click", (event) => {
            event.preventDefault();
            remove(view, task.id);
          });
          element.append(label, button);
          return element;
        },
        { id: task.id, side: 1, ignoreSelection: true, stopEvent: () => true },
      ),
    );
    view.dispatch(tr.setMeta(uploadsKey, { add: widgets } satisfies UploadMeta));
    report();
    for (const task of added) {
      void uploadRoomImage(options.roomId, task.file, task.controller.signal)
        .then((result) => {
          if (disposed || !tasks.includes(task)) return;
          task.result = result;
        })
        .catch((error: unknown) => {
          if (disposed || !tasks.includes(task)) return;
          task.failed = true;
          options.error(describeApiError(error, "composer.imageUploadFailed"));
        })
        .finally(flush);
    }
  }
  const plugin = new Plugin<DecorationSet>({
    key: uploadsKey,
    state: {
      init: () => DecorationSet.empty,
      apply(tr, previous) {
        const meta = tr.getMeta(uploadsKey) as UploadMeta | undefined;
        let next = meta?.clear ? DecorationSet.empty : previous.map(tr.mapping, tr.doc);
        if (meta?.remove)
          next = next.remove(
            next.find().filter((item) => meta.remove!.includes(item.spec.id as object)),
          );
        if (meta?.add) next = next.add(tr.doc, meta.add);
        return next;
      },
    },
    props: {
      decorations: (state) => uploadsKey.getState(state),
      handleKeyDown(view, event) {
        if (!["Backspace", "Delete"].includes(event.key) || !view.state.selection.empty)
          return false;
        const anchor = placeholders(view).find(
          view.state.selection.from,
          view.state.selection.from,
        )[0];
        if (!anchor) return false;
        remove(view, anchor.spec.id as object);
        return true;
      },
    },
    view: () => ({
      update(view) {
        const live = placeholders(view)
          .find()
          .map((item) => item.spec.id as object);
        const missing = tasks.filter((task) => !live.includes(task.id)).map((task) => task.id);
        if (missing.length) cancel(missing);
      },
    }),
  });
  return {
    plugin,
    add,
    flush,
    cancelAll,
    destroy() {
      disposed = true;
      if (timer) clearTimeout(timer);
      cancel(tasks.map((task) => task.id));
    },
  };
}
