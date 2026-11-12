import type { SkillCatalog } from "@/services/roomApi";

export function skillsFixture(): SkillCatalog {
  return {
    skills: [
      {
        type: "skill",
        id: "skill-repo",
        name: "lint",
        displayName: "代码审查",
        description: "检查逻辑",
        scope: "repo",
        source: "repo",
        pluginId: null,
        enabled: true,
      },
      {
        type: "skill",
        id: "skill-user",
        name: "lint",
        displayName: "代码审查",
        description: "检查样式",
        scope: "user",
        source: "user",
        pluginId: null,
        enabled: true,
      },
      {
        type: "skill",
        id: "skill-disabled",
        name: "disabled",
        displayName: "禁用技能",
        description: "不可选",
        scope: "repo",
        source: "repo",
        pluginId: null,
        enabled: false,
      },
    ],
    errors: [],
  };
}
