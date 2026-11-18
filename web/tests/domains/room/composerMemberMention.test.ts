import { Editor, Node } from "@tiptap/core";
import { UndoRedo } from "@tiptap/extensions";
import { history } from "@tiptap/pm/history";
import { Plugin, TextSelection } from "@tiptap/pm/state";
import { afterEach, describe, expect, it } from "vitest";
import {
  deleteAdjacentMemberMention,
  insertMemberMention,
  MemberMention,
  memberMentionMeta,
  updateComposerContent,
  type ComposerDraft,
} from "@/domains/room/composerMemberMention";
import {
  decodeMessage,
  documentMemberMentions,
  nodeSource,
} from "@/domains/room/messageEditorCodec";
import { messageMaxLength } from "@/domains/room/skillEditorModel";

const Document = Node.create({ name: "doc", topNode: true, content: "messageBody" });
const Body = Node.create({ name: "messageBody", content: "inline*" });
const Text = Node.create({ name: "text", group: "inline" });
const member = { id: "architect", name: "Backend Worker" };
const memberText = "@Backend Worker";
const draftWithQuery = { content: "请 @Back", topicIds: ["development"], mentionedMemberIds: [] };

describe("composer member selection", () => {
  let editor: Editor | undefined;

  afterEach(() => editor?.destroy());

  function edit(draft: ComposerDraft) {
    const updates: ComposerDraft[] = [];
    const active = new Editor({
      element: null,
      extensions: [Document, Body, Text, MemberMention, UndoRedo],
      content: decodeMessage(draft.content, [], "room", "channel", draft.memberMentions),
      onUpdate({ editor, transaction }) {
        const addedMemberIds: string[] | undefined = transaction.getMeta(memberMentionMeta);
        const doc = editor.state.doc;
        draft = updateComposerContent(
          draft,
          nodeSource(doc),
          [],
          documentMemberMentions(doc),
          addedMemberIds,
        );
        updates.push(draft);
      },
    });
    editor = active;
    active.registerPlugin(history());
    active.registerPlugin(
      new Plugin({ filterTransaction: (tr) => nodeSource(tr.doc).length <= messageMaxLength }),
    );
    return { active, updates };
  }

  it.each([[[]], [[member.id]]])(
    "writes the inserted mention and recipient in a single draft update (%j already selected)",
    (mentionedMemberIds) => {
      const draft = {
        ...draftWithQuery,
        mentionedMemberIds,
        replyToMessageId: "quoted-message",
      };
      const { active, updates } = edit(draft);
      insertMemberMention(active, { from: 3, to: draft.content.length + 1 }, member);
      expect(updates).toEqual([
        {
          ...draft,
          content: `请 ${memberText} `,
          mentionedMemberIds: [member.id],
          capabilities: [],
          memberMentions: [{ ...member, start: 2, end: 17 }],
        },
      ]);
    },
  );

  it("backspaces the whole mention and its trailing space, then undoes and redoes the deletion", () => {
    const { active, updates } = edit(draftWithQuery);
    insertMemberMention(active, { from: 3, to: draftWithQuery.content.length + 1 }, member);
    const withMention = updates.at(-1);
    const deletion = deleteAdjacentMemberMention(active.state, "Backspace");
    expect(deletion).toBeDefined();
    active.view.dispatch(deletion!);
    expect(updates.at(-1)).toMatchObject({ content: "请 ", mentionedMemberIds: [member.id] });
    expect(updates.at(-1)?.memberMentions).toBeUndefined();

    expect(active.commands.undo()).toBe(true);
    expect(updates.at(-1)).toEqual(withMention);
    expect(active.commands.redo()).toBe(true);
    expect(updates.at(-1)?.content).toBe("请 ");
  });

  it("restores only the tagged occurrence and removes it with forward Delete", () => {
    const prefix = `🙂${memberText} `;
    const content = `${prefix}${memberText} next`;
    const tag = { ...member, start: prefix.length, end: prefix.length + memberText.length };
    const { active, updates } = edit({ ...draftWithQuery, content, memberMentions: [tag] });
    expect(documentMemberMentions(active.state.doc)).toEqual([tag]);
    const position = prefix.length + 1;
    active.view.dispatch(
      active.state.tr.setSelection(TextSelection.create(active.state.doc, position)),
    );

    const deletion = deleteAdjacentMemberMention(active.state, "Delete");
    expect(deletion).toBeDefined();
    active.view.dispatch(deletion!);
    expect(updates.at(-1)?.content).toBe(`${prefix} next`);
    expect(updates.at(-1)?.memberMentions).toBeUndefined();
  });

  it("does not add a recipient when the editor rejects the insertion", () => {
    const content = `${"x".repeat(messageMaxLength - 2)} @`;
    const { active, updates } = edit({ content, topicIds: [], mentionedMemberIds: [] });
    insertMemberMention(active, { from: content.length, to: content.length + 1 }, member);
    expect(nodeSource(active.state.doc)).toBe(content);
    expect(updates).toEqual([]);
  });
});
