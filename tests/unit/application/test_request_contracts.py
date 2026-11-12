import pytest
from pydantic import ValidationError

from agent_relay.application.messages.contracts import CreateMessage


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        ({"content": "   ", "topicIds": ["frontend"]}, "content cannot be blank"),
        (
            {"content": "必须选择投递目标", "topicIds": [], "mentionedMemberIds": []},
            "requires a topic or a directly mentioned member",
        ),
    ],
)
def test_message_requires_content_and_targets(payload: dict[str, object], error: str) -> None:
    with pytest.raises(ValidationError, match=error):
        CreateMessage.model_validate({"publicationId": "invalid", **payload})


@pytest.mark.parametrize(
    "capability",
    [
        {"type": "unknown", "id": "example", "name": "Example"},
        {"type": "skill", "id": "C:/private/SKILL.md", "name": "Example"},
        {"type": "mcp_server", "id": "example", "name": "Example", "token": "secret"},
        {"type": "skill", "id": "example", "name": "Example", "path": "C:/private"},
        {"type": "skill", "id": "example", "name": "   "},
    ],
)
def test_capability_references_reject_unknown_types_native_paths_and_unowned_fields(
    capability: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        CreateMessage.model_validate(
            {
                "publicationId": "invalid-capability",
                "content": "Message",
                "mentionedMemberIds": ["user"],
                "capabilities": [capability],
            }
        )
