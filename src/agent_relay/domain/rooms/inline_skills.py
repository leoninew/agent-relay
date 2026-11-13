import re
from collections.abc import Sequence
from dataclasses import dataclass

from agent_relay.domain.rooms.models.capabilities import CapabilityReference

_SKILL_LINK = re.compile(
    r"\[((?:\\[^\r\n]|[^\]\\\r\n])*)\]\(skill:([A-Za-z0-9_][A-Za-z0-9_.@-]{0,255})\)"
)
_FENCE = re.compile(r"^ {0,3}(?:> ?)*(`{3,}|~{3,})([^\r\n]*)")


@dataclass(frozen=True)
class InlineSkill:
    start: int
    end: int
    id: str


def inline_skills(content: str) -> list[InlineSkill]:
    """Read the shared inline format, leaving Markdown code and escaped examples literal."""
    references: list[InlineSkill] = []
    fence: tuple[str, int] | None = None
    index = 0
    while index < len(content):
        if index == 0 or content[index - 1] == "\n":
            end = content.find("\n", index)
            line_end = len(content) if end < 0 else end + 1
            line = content[index:line_end]
            marker = _FENCE.match(line)
            if fence is not None:
                if (
                    marker is not None
                    and marker[1][0] == fence[0]
                    and len(marker[1]) >= fence[1]
                    and not marker[2].strip()
                ):
                    fence = None
                index = line_end
                continue
            if marker is not None and (marker[1][0] != "`" or "`" not in marker[2]):
                fence = (marker[1][0], len(marker[1]))
                index = line_end
                continue
            if line.startswith(("    ", "\t")):
                index = line_end
                continue
        if content[index] == "\\":
            index += 2
            continue
        if content[index] == "`":
            run_end = index + 1
            while run_end < len(content) and content[run_end] == "`":
                run_end += 1
            run = content[index:run_end]
            close = content.find(run, run_end)
            while close >= 0 and (
                content[close - 1] == "`" or content[close + len(run) : close + len(run) + 1] == "`"
            ):
                close = content.find(run, close + len(run))
            index = run_end if close < 0 else close + len(run)
            continue
        match = _SKILL_LINK.match(content, index) if content[index] == "[" else None
        if match is not None:
            if index == 0 or content[index - 1] != "!":
                references.append(InlineSkill(index, match.end(), match[2]))
            index = match.end()
        else:
            index += 1
    return references


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
