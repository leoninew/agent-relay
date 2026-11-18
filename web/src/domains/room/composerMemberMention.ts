import type { Editor, JSONContent, Range } from "@tiptap/core";
import Mention from "@tiptap/extension-mention";
import { closeHistory } from "@tiptap/pm/history";
import { NodeSelection, type EditorState, type Transaction } from "@tiptap/pm/state";
import type { CapabilityReference, Member, MessageDraft } from "@/services/roomApi";

type MentionedMember = Pick<Member, "id" | "name">;
export type MemberMentionRange = MentionedMember & { start: number; end: number };
export type ComposerDraft = MessageDraft & { memberMentions?: MemberMentionRange[] };

export const memberMentionMeta = "confluaMemberMention";
export const memberMentionNodeName = "memberMention";

export function memberMentionNode(member: MentionedMember): JSONContent {
  return { type: memberMentionNodeName, attrs: { id: member.id, label: member.name } };
}

export function deleteAdjacentMemberMention(
  state: EditorState,
  key: "Backspace" | "Delete",
): Transaction | undefined {
  const { selection } = state;
  if (selection instanceof NodeSelection && selection.node.type.name === memberMentionNodeName) {
    return closeHistory(state.tr.deleteSelection());
  }
  if (!selection.empty) {
    return;
  }
  const { $from } = selection;
  if (key === "Delete") {
    if ($from.nodeAfter?.type.name === memberMentionNodeName) {
      return closeHistory(state.tr.delete($from.pos, $from.pos + 1));
    }
    return;
  }
  const before = $from.nodeBefore;
  if (before?.type.name === memberMentionNodeName) {
    return closeHistory(state.tr.delete($from.pos - 1, $from.pos));
  }
  if (
    before?.text === " " &&
    state.doc.resolve($from.pos - 1).nodeBefore?.type.name === memberMentionNodeName
  ) {
    return closeHistory(state.tr.delete($from.pos - 2, $from.pos));
  }
}

export const MemberMention = Mention.extend({
  name: memberMentionNodeName,
  selectable: true,
  parseHTML: () => [],
  addProseMirrorPlugins: () => [],
  addKeyboardShortcuts() {
    const remove = (key: "Backspace" | "Delete") => {
      if (!this.editor.isEditable || this.editor.view.composing) {
        return false;
      }
      const transaction = deleteAdjacentMemberMention(this.editor.state, key);
      if (!transaction) {
        return false;
      }
      this.editor.view.dispatch(transaction);
      return true;
    };
    return { Backspace: () => remove("Backspace"), Delete: () => remove("Delete") };
  },
}).configure({
  renderText: ({ node }) => `@${node.attrs.label as string}`,
  renderHTML: ({ node }) => [
    "span",
    { class: "editor-reference editor-member", title: `@${node.attrs.label as string}` },
    ["span", { "aria-hidden": "true" }, "@"],
    ["span", {}, node.attrs.label as string],
  ],
});

export function insertMemberMention(editor: Editor, range: Range, member: MentionedMember): void {
  editor
    .chain()
    .insertContentAt(range, [memberMentionNode(member), { type: "text", text: " " }])
    .setMeta(memberMentionMeta, [member.id])
    .command(({ tr }) => {
      closeHistory(tr);
      return true;
    })
    .run();
}

export function updateComposerContent(
  draft: ComposerDraft,
  content: string,
  capabilities: CapabilityReference[],
  memberMentions: MemberMentionRange[],
  addedMemberIds: readonly string[] = [],
): ComposerDraft {
  return {
    ...draft,
    content,
    capabilities,
    memberMentions: memberMentions.length ? memberMentions : undefined,
    mentionedMemberIds: [...new Set([...draft.mentionedMemberIds, ...addedMemberIds])],
  };
}
