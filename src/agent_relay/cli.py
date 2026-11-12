from agent_relay.bootstrap.logging import configure_console_encoding
from agent_relay.interfaces.cli import main

if __name__ == "__main__":
    configure_console_encoding()
    raise SystemExit(main())
