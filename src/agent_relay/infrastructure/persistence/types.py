import json
from datetime import datetime

from sqlalchemy import Text
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


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
