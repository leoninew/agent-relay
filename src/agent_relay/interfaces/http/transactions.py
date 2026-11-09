from typing import Protocol


class RequestTransaction(Protocol):
    def finish(self, *, commit: bool) -> None: ...
