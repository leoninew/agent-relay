import os
import subprocess
import sys
from pathlib import Path


def run_logging_script(script: str, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        env={
            **os.environ,
            "PYTHONIOENCODING": "gbk",
            "PYTHONPATH": str(Path(__file__).parents[3] / "src"),
        },
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_logging_takes_over_host_and_uvicorn_without_duplicate_output(tmp_path: Path) -> None:
    result = run_logging_script(
        """
import logging
import sys
from agent_relay.bootstrap.logging import configure_logging
host_handler = logging.StreamHandler(sys.stdout)
logging.getLogger().addHandler(host_handler)
logging.getLogger('uvicorn.error').addHandler(logging.StreamHandler(sys.stdout))
configure_logging()
configure_logging()
assert host_handler not in logging.getLogger().handlers
logging.info('服务启动中 🎯')
logging.getLogger('uvicorn.error').info('server ready')
try:
    raise RuntimeError('diagnostic cause')
except RuntimeError:
    logging.getLogger('agent_relay.http').exception('http request failed')
""",
        tmp_path,
    )
    file_log = (tmp_path / "logs/agent-relay.log").read_text(encoding="utf-8")
    for output in (result.stdout, file_log):
        for message in ("服务启动中 🎯", "server ready", "http request failed"):
            assert output.count(message) == 1
        assert "[INFO] uvicorn.error:" in output
        assert output.count("RuntimeError: diagnostic cause") == 1
    assert result.stderr == ""


def test_logging_rotates_utf8_files_and_bounds_retention(tmp_path: Path) -> None:
    run_logging_script(
        """
import logging
from logging.handlers import RotatingFileHandler
from agent_relay.bootstrap.logging import configure_logging
configure_logging()
handler = next(
    item for item in logging.getLogger().handlers if isinstance(item, RotatingFileHandler)
)
handler.maxBytes = 256
handler.backupCount = 2
for index in range(12):
    logging.info('轮转日志 🎯 %s %s', index, '内容' * 20)
""",
        tmp_path,
    )
    files = sorted((tmp_path / "logs").iterdir())
    assert [path.name for path in files] == [
        "agent-relay.log",
        "agent-relay.log.1",
        "agent-relay.log.2",
    ]
    assert all("轮转日志 🎯" in path.read_text(encoding="utf-8") for path in files)


def test_logging_without_console_keeps_a_single_file_sink(tmp_path: Path) -> None:
    run_logging_script(
        """
import logging
import sys
from agent_relay.bootstrap.logging import configure_logging
sys.stdout = None
sys.stderr = None
configure_logging()
configure_logging()
logging.info('无控制台启动 🎯')
""",
        tmp_path,
    )
    file_log = (tmp_path / "logs/agent-relay.log").read_text(encoding="utf-8")
    assert file_log.count("无控制台启动 🎯") == 1


def test_reload_supervisor_only_configures_console_logging(tmp_path: Path) -> None:
    result = run_logging_script(
        """
import logging
from agent_relay.bootstrap.logging import configure_logging
configure_logging(include_files=False)
logging.getLogger('uvicorn.error').info('reload supervisor ready')
""",
        tmp_path,
    )
    assert result.stdout.count("reload supervisor ready") == 1
    assert not (tmp_path / "logs").exists()
