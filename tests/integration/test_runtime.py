import logging
from collections.abc import Iterator
from pathlib import Path
from shutil import copyfile

import pytest
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from agent_relay.bootstrap.config import load_settings
from agent_relay.bootstrap.http import create_app

pytestmark = pytest.mark.usefixtures("migrated_database")


@pytest.mark.parametrize("field", ["SERVER__PORRT", "GREETNG__PREFIX"])
def test_unknown_configuration_fields_fail_at_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    (tmp_path / "config").mkdir()
    copyfile(Path(__file__).parents[2] / "config/config.yaml", tmp_path / "config/config.yaml")
    monkeypatch.setenv(f"AGENT_RELAY_{field}", "9000")

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        load_settings(tmp_path)


def test_streaming_response_is_logged_after_all_chunks(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.agent_relay.streaming")
    app = create_app(logger)

    def stream() -> Iterator[str]:
        yield "first"
        assert not any(record.getMessage().startswith("Request end") for record in caplog.records)
        yield "second"

    @app.get("/api/stream")
    def streamed_response() -> StreamingResponse:
        return StreamingResponse(stream(), media_type="text/plain")

    with caplog.at_level(logging.INFO, logger=logger.name), TestClient(app) as client:
        response = client.get("/api/stream", headers={"X-Request-Id": "req_stream"})

    assert response.text == "firstsecond"
    assert response.headers["X-Request-Id"] == "req_stream"
    assert sum(record.getMessage().startswith("Request end") for record in caplog.records) == 1


def test_stream_failure_is_logged_without_a_false_completion(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("tests.agent_relay.stream_failure")
    app = create_app(logger)

    def stream() -> Iterator[str]:
        yield "first"
        raise RuntimeError("stream interrupted")

    @app.get("/api/stream")
    def streamed_response() -> StreamingResponse:
        return StreamingResponse(stream(), media_type="text/plain")

    with (
        caplog.at_level(logging.INFO, logger=logger.name),
        TestClient(app) as client,
        pytest.raises(RuntimeError, match="stream interrupted"),
    ):
        client.get("/api/stream", headers={"X-Request-Id": "req_interrupted"})

    assert not any(record.getMessage().startswith("Request end") for record in caplog.records)
    failures = [record for record in caplog.records if record.exc_info is not None]
    assert len(failures) == 1
    fields = vars(failures[0])
    assert fields["request_id"] == "req_interrupted"
    assert fields["status"] == 200
    assert fields["error_kind"] == "internal_error"
