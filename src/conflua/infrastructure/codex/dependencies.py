from conflua.application.capabilities.ports import CapabilityDriver
from conflua.application.delivery.ports import DeliveryDriver
from conflua.application.members.sessions import SessionDriver
from conflua.infrastructure.codex.driver import CodexDriver


def create_session_driver(command: list[str], timeout: float) -> SessionDriver:
    return CodexDriver(command, timeout)


def create_queue_driver(command: list[str], timeout: float) -> DeliveryDriver:
    return CodexDriver(command, timeout)


def create_capability_driver(command: list[str], timeout: float) -> CapabilityDriver:
    return CodexDriver(command, timeout)
