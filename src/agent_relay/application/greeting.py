from dataclasses import dataclass


@dataclass(frozen=True)
class GreetingMessage:
    text: str


class GreetingService:
    def __init__(self, prefix: str = "Hello") -> None:
        self._prefix = prefix.strip()

    def greet(self, name: str) -> GreetingMessage:
        return GreetingMessage(text=f"{self._prefix}, {name.strip()}!")
