from conflua.bootstrap.logging import configure_console_encoding
from conflua.interfaces.cli import main

if __name__ == "__main__":
    configure_console_encoding()
    raise SystemExit(main())
