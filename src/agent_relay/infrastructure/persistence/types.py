import json
from datetime import datetime

from pydantic import TypeAdapter
from sqlalchemy import Text
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from agent_relay.domain.rooms.models import CapabilityReference

_capability_references = TypeAdapter(list[CapabilityReference])


class ISODateTime(TypeDecorator[datetime]):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> str | None:
        return value.isoformat() if value is not None else None

    def process_result_value(self, value: str | None, dialect: Dialect) -> datetime | None:
        return datetime.fromisoformat(value) if value is not None else None


class ReceiptMetadata(TypeDecorator[dict[str, object]]):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: dict[str, object] | None, dialect: Dialect) -> str | None:
        return json.dumps(value, ensure_ascii=False) if value is not None else None

    def process_result_value(self, value: str | None, dialect: Dialect) -> dict[str, object] | None:
        if value is None:
            return None
        decoded = json.loads(value)
        if not isinstance(decoded, dict):
            raise ValueError("Receipt metadata must be a JSON object")
        return {str(key): item for key, item in decoded.items()}


class CapabilityReferences(TypeDecorator[tuple[CapabilityReference, ...]]):
    impl = Text
    cache_ok = True

    def process_bind_param(
        self, value: tuple[CapabilityReference, ...] | None, dialect: Dialect
    ) -> str:
        if value is None:
            raise ValueError("Message capabilities cannot be null")
        return json.dumps(
            [reference.model_dump(mode="json") for reference in value], ensure_ascii=False
        )

    def process_result_value(
        self, value: str | None, dialect: Dialect
    ) -> tuple[CapabilityReference, ...]:
        if value is None:
            raise ValueError("Message capabilities cannot be null")
        decoded = json.loads(value)
        if not isinstance(decoded, list):
            raise ValueError("Message capabilities must be a JSON array")
        return tuple(_capability_references.validate_python(decoded))
