from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Query

from agent_relay.dependencies import GreetingServiceDependency

router = APIRouter(tags=["greetings"])


@dataclass(frozen=True)
class GreetingResponse:
    text: str


@router.get("/greet")
def greet(
    name: Annotated[str, Query(min_length=1, pattern=r".*\S.*")],
    service: GreetingServiceDependency,
) -> GreetingResponse:
    message = service.greet(name)
    return GreetingResponse(text=message.text)
