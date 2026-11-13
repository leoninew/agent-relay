import re
from collections.abc import Sequence
from dataclasses import dataclass

from agent_relay.domain.rooms.markdown import inline_matches
from agent_relay.domain.rooms.models.capabilities import CapabilityReference

_SKILL_LINK = re.compile(
    r"\[((?:\\[^\r\n]|[^\]\\\r\n])*)\]\(skill:([A-Za-z0-9_][A-Za-z0-9_.@-]{0,255})\)"
)


@dataclass(frozen=True)
class InlineSkill:
    start: int
    end: int
    id: str


def inline_skills(content: str) -> list[InlineSkill]:
    """Read the shared inline format, leaving Markdown code and escaped examples literal."""
    return [
        InlineSkill(match.start(), match.end(), match[2])
        for match in inline_matches(content, _SKILL_LINK)
        if match.start() == 0 or content[match.start() - 1] != "!"
    ]


def without_inline_skills(content: str) -> str:
    start = 0
    parts: list[str] = []
    for reference in inline_skills(content):
        parts.append(content[start : reference.start])
        start = reference.end
    parts.append(content[start:])
    return "".join(parts)


def message_text(content: str, capabilities: Sequence[CapabilityReference]) -> str:
    skills = {reference.id: reference for reference in capabilities if reference.type == "skill"}
    start = 0
    parts: list[str] = []
    for reference in inline_skills(content):
        parts.append(content[start : reference.start])
        skill = skills.get(reference.id)
        parts.append(
            f"${skill.name}" if skill is not None else content[reference.start : reference.end]
        )
        start = reference.end
    parts.append(content[start:])
    return "".join(parts)
