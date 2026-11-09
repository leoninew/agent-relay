from agent_relay.application.delivery.ports import QueueDriver
from agent_relay.application.members.sessions import SessionDriver
from agent_relay.infrastructure.codex.driver import CodexDriver


def create_session_driver(command: list[str], timeout: float) -> SessionDriver:
    return CodexDriver(command, timeout)


def create_queue_driver(command: list[str], timeout: float) -> QueueDriver:
    return CodexDriver(command, timeout)
