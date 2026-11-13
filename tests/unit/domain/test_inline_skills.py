import json
from pathlib import Path

import pytest

from agent_relay.domain.rooms.inline_skills import (
    inline_skills,
    message_text,
    without_inline_skills,
)
from agent_relay.domain.rooms.models import SkillReference

CASES = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures/inline_skills.json").read_text(
        encoding="utf-8"
    )
)
CHECK = SkillReference(id="skill-check", name="dev-check")
FIX = SkillReference(id="skill-fix", name="dev-fix")


@pytest.mark.parametrize("case", CASES)
def test_inline_skill_format_matches_frontend_contract(case: dict[str, object]) -> None:
    content = str(case["content"])
    assert [reference.id for reference in inline_skills(content)] == case["ids"]
    assert message_text(content, [CHECK, FIX]) == case["text"]


def test_skill_only_body_is_empty_but_literal_examples_remain_content() -> None:
    assert not without_inline_skills(" [check](skill:skill-check)\n").strip()
    assert without_inline_skills("`[check](skill:skill-check)`").strip()


def test_unknown_references_are_not_silently_substituted() -> None:
    content = "请用 [check](skill:skill-check) 检查"
    assert message_text(content, []) == content
