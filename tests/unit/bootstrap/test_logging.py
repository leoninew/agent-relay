import sys
from io import BytesIO, TextIOWrapper

from pytest import MonkeyPatch

from agent_relay.bootstrap.logging import configure_console_encoding


def test_console_encoding_supports_unicode_with_gbk_streams(monkeypatch: MonkeyPatch) -> None:
    message = "🎯 服务启动中..."
    stdout_buffer = BytesIO()
    stderr_buffer = BytesIO()
    with (
        TextIOWrapper(stdout_buffer, encoding="gbk") as stdout,
        TextIOWrapper(stderr_buffer, encoding="gbk") as stderr,
    ):
        with monkeypatch.context() as patched:
            patched.setattr(sys, "stdout", stdout)
            patched.setattr(sys, "stderr", stderr)
            configure_console_encoding()
            print(message)
            print(message, file=sys.stderr)
            stdout.flush()
            stderr.flush()

        assert stdout_buffer.getvalue().decode("utf-8").splitlines() == [message]
        assert stderr_buffer.getvalue().decode("utf-8").splitlines() == [message]
