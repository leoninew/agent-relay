import MarkdownIt from "markdown-it";
import { skillAt } from "@/domains/room/inlineSkills";
import { skillIcon } from "@/domains/room/skillIcon";
import type { CapabilityReference, SkillReference } from "@/services/roomApi";

type MessageEnvironment = {
  skills: Map<string, SkillReference>;
  skillDescriptions: ReadonlyMap<string, string>;
  renderedSkills: Set<string>;
  imageFailureText: string;
};

const markdown = new MarkdownIt({ breaks: true });
const renderImage = markdown.renderer.rules.image!;
markdown.renderer.rules.image = (tokens, index, options, environment, renderer) => {
  tokens[index].attrSet("loading", "lazy");
  tokens[index].attrSet("decoding", "async");
  const image = renderImage(tokens, index, options, environment, renderer);
  const failure = markdown.utils.escapeHtml(
    (environment as MessageEnvironment | undefined)?.imageFailureText ??
      "Image could not be loaded",
  );
  return `<span class="message-image-frame">${image}<span class="message-image-failure" hidden>${failure}</span></span>`;
};
markdown.inline.ruler.before("link", "skill_reference", (state, silent) => {
  if (state.src[state.pos] !== "[" || state.linkLevel > 0) return false;
  const reference = skillAt(state.src, state.pos);
  const environment = state.env as MessageEnvironment;
  const skill = reference && environment.skills.get(reference.id);
  if (!reference || !skill) return false;
  if (!silent) {
    const token = state.push("skill_reference", "span", 0);
    token.content = skill.name;
    token.attrSet("title", environment.skillDescriptions.get(reference.id)?.trim() || skill.name);
    environment.renderedSkills.add(reference.id);
  }
  state.pos = reference.end;
  return true;
});
markdown.renderer.rules.skill_reference = (tokens, index) => {
  const name = markdown.utils.escapeHtml(tokens[index].content);
  const title = markdown.utils.escapeHtml(
    String(tokens[index].attrGet("title") ?? tokens[index].content),
  );
  return `<span class="message-skill-chip" title="${title}">${skillIcon}<span>${name}</span></span>`;
};

export function renderMessage(
  content: string,
  capabilities: readonly CapabilityReference[] = [],
  options: { imageFailureText?: string; skillDescriptions?: ReadonlyMap<string, string> } = {},
): { html: string; remainingCapabilities: CapabilityReference[] } {
  const skills = new Map(
    capabilities
      .filter((reference): reference is SkillReference => reference.type === "skill")
      .map((reference) => [reference.id, reference]),
  );
  const environment: MessageEnvironment = {
    skills,
    skillDescriptions: options.skillDescriptions ?? new Map(),
    renderedSkills: new Set(),
    imageFailureText: options.imageFailureText ?? "Image could not be loaded",
  };
  const html = markdown.render(content, environment);
  return {
    html,
    remainingCapabilities: capabilities.filter(
      (reference) => reference.type !== "skill" || !environment.renderedSkills.has(reference.id),
    ),
  };
}
