from dataclasses import dataclass


@dataclass(frozen=True)
class ApiResult:
    data: object
    request_id: str | None
