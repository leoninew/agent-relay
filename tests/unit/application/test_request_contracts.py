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
