import MarkdownIt from "markdown-it";
import { skillAt } from "@/domains/room/inlineSkills";
import type { CapabilityReference, SkillReference } from "@/services/roomApi";

type MessageEnvironment = {
  skills: Map<string, SkillReference>;
  renderedSkills: Set<string>;
};

const markdown = new MarkdownIt({ breaks: true });
// Lucide Sparkles (@lucide/vue, ISC), matching AppIcon's skill icon in selected tags.
const skillIcon =
  '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z"/><path d="M20 2v4M22 4h-4"/><circle cx="4" cy="20" r="2"/></svg>';
markdown.inline.ruler.before("link", "skill_reference", (state, silent) => {
  if (state.src[state.pos] !== "[" || state.linkLevel > 0) return false;
  const reference = skillAt(state.src, state.pos);
  const environment = state.env as MessageEnvironment;
  const skill = reference && environment.skills.get(reference.id);
  if (!reference || !skill) return false;
  if (!silent) {
    const token = state.push("skill_reference", "span", 0);
    token.content = skill.name;
    environment.renderedSkills.add(reference.id);
  }
  state.pos = reference.end;
  return true;
});
markdown.renderer.rules.skill_reference = (tokens, index) => {
  const name = markdown.utils.escapeHtml(tokens[index].content);
  return `<span class="message-skill-chip" title="${name}">${skillIcon}<span>${name}</span></span>`;
};

export function renderMessage(
  content: string,
  capabilities: readonly CapabilityReference[] = [],
): { html: string; remainingCapabilities: CapabilityReference[] } {
  const skills = new Map(
    capabilities
      .filter((reference): reference is SkillReference => reference.type === "skill")
      .map((reference) => [reference.id, reference]),
  );
  const environment: MessageEnvironment = { skills, renderedSkills: new Set() };
  const html = markdown.render(content, environment);
  return {
    html,
    remainingCapabilities: capabilities.filter(
      (reference) => reference.type !== "skill" || !environment.renderedSkills.has(reference.id),
    ),
  };
}
