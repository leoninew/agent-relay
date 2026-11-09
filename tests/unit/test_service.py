from agent_relay.application.greeting import GreetingService


def test_greeting_service_returns_message() -> None:
    service = GreetingService("Hello")

    message = service.greet("Ada")

    assert message.text == "Hello, Ada!"


def test_greeting_service_trims_name() -> None:
    service = GreetingService("Hi")

    message = service.greet("  Ada  ")

    assert message.text == "Hi, Ada!"
