from typing import Any, Protocol

from pydantic import Field

from conflua.application.dto.members import SessionInfo
from conflua.application.dto.session_models import SessionModelCatalog, SessionModelOption
from conflua.domain.rooms.models import RoomModel


class ModelRpc(Protocol):
    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]: ...


class ReasoningOption(RoomModel):
    reasoning_effort: str = Field(min_length=1)


class CodexModel(RoomModel):
    id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str
    hidden: bool
    default_reasoning_effort: str = Field(min_length=1)
    supported_reasoning_efforts: list[ReasoningOption]


class ModelPage(RoomModel):
    data: list[CodexModel]
    next_cursor: str | None = None


def read_models(rpc: ModelRpc, provider: str) -> list[CodexModel]:
    models: list[CodexModel] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    identifiers: set[str] = set()
    model_names: set[str] = set()
    while True:
        page = ModelPage.model_validate(
            rpc.call(
                "model/list",
                {"modelProvider": provider, "includeHidden": False, "limit": 100, "cursor": cursor},
            )
        )
        for model in page.data:
            if model.hidden:
                continue
            efforts = {option.reasoning_effort for option in model.supported_reasoning_efforts}
            if (
                model.id in identifiers
                or model.model in model_names
                or (efforts and model.default_reasoning_effort not in efforts)
            ):
                raise ValueError("Invalid Codex model catalog")
            identifiers.add(model.id)
            model_names.add(model.model)
            models.append(model)
        cursor = page.next_cursor
        if cursor is None:
            return models
        if not cursor or cursor in seen_cursors:
            raise ValueError("Invalid Codex model pagination cursor")
        seen_cursors.add(cursor)


def public_catalog(session: SessionInfo, models: list[CodexModel]) -> SessionModelCatalog:
    return SessionModelCatalog(
        session_id=session.id,
        provider=session.provider,
        current_model=session.model,
        models=[
            SessionModelOption(
                id=model.id,
                model=model.model,
                display_name=model.display_name,
                description=model.description,
            )
            for model in models
        ],
    )
