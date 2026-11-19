import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock

import httpx2
import pytest
from fastapi import FastAPI

from conflua.application.dto.member_roles import MemberRoleInput
from conflua.bootstrap.http import create_app
from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.dependencies import create_database

ROLE_PATH = "/api/member-role"
SEEDED_ROLE_NAMES = {
    "高级开发 / 实现者",
    "架构师 / 技术负责人",
    "验证与审查 / 独立把关",
}


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    active = create_database(tmp_path / "roles.sqlite3")
    try:
        yield active
    finally:
        active.close()


@pytest.fixture
def app(database: Database, tmp_path: Path) -> FastAPI:
    return create_app(
        Mock(),
        database=database,
        static_directory=tmp_path,
        session_driver=Mock(),
        queue_driver=Mock(),
        capability_driver=Mock(),
        preferences_service=Mock(),
    )


def request(
    app: FastAPI, method: str, path: str = ROLE_PATH, body: object = None
) -> httpx2.Response:
    async def send() -> httpx2.Response:
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=body)

    return asyncio.run(send())


def test_role_crud(app: FastAPI) -> None:
    assert {role["name"] for role in request(app, "GET").json()} == SEEDED_ROLE_NAMES
    response = request(app, "POST", body={"name": "  Reviewer  ", "prompt": "  Read\nReview  "})
    assert response.status_code == 201
    role = response.json()
    assert role == {"id": role["id"], "name": "Reviewer", "prompt": "Read\nReview"}
    for name in ("reviewer", "Developer"):
        assert request(app, "POST", body={"name": name, "prompt": "Test"}).status_code == 201
    assert {item["name"] for item in request(app, "GET").json()} == SEEDED_ROLE_NAMES | {
        "Developer",
        "Reviewer",
        "reviewer",
    }

    for method, path in (("POST", ROLE_PATH), ("PATCH", f"{ROLE_PATH}/{role['id']}")):
        duplicate = request(app, method, path, {"name": " Developer ", "prompt": "Other"})
        assert duplicate.status_code == 409
        assert duplicate.json()["code"] == "member_role_name_conflict"
        assert duplicate.json()["requestId"] == duplicate.headers["X-Request-Id"]
    assert role in request(app, "GET").json()

    path = f"{ROLE_PATH}/{role['id']}"
    update = request(app, "PATCH", path, {"name": "Editor", "prompt": "Check"})
    assert update.status_code == 200
    assert update.json() == {"id": role["id"], "name": "Editor", "prompt": "Check"}
    deleted = request(app, "DELETE", path)
    assert deleted.status_code == 204 and not deleted.content
    assert {item["name"] for item in request(app, "GET").json()} == SEEDED_ROLE_NAMES | {
        "Developer",
        "reviewer",
    }
    for method in ("PATCH", "DELETE"):
        missing = request(app, method, path, {"name": "Editor", "prompt": "Check"})
        assert missing.status_code == 404
        assert missing.json()["code"] == "member_role_not_found"


@pytest.mark.parametrize(
    ("name", "prompt"),
    [
        (" ", "valid"),
        ("x" * 81, "valid"),
        ("valid", "\n\t"),
        ("valid", "x" * 6001),
        ("valid", "Use [Build](skill:build)"),
        ("valid", ["not plain text"]),
    ],
)
def test_invalid_roles_use_request_validation_contract(
    app: FastAPI, name: str, prompt: object
) -> None:
    response = request(app, "POST", body={"name": name, "prompt": prompt})
    assert response.status_code == 422 and response.json()["code"] == "validation_error"


def test_role_get_reuses_open_request_session(app: FastAPI, database: Database) -> None:
    request_scope = database.request_transaction()
    role_service = app.state.http_dependencies.request_member_role_service(request_scope)
    try:
        created = role_service.create(MemberRoleInput(name="Reviewer", prompt="Test"))
        assert role_service.get(created.id) == created
        assert {role["name"] for role in request(app, "GET").json()} == SEEDED_ROLE_NAMES
    finally:
        request_scope.finish(commit=False)
    assert {role["name"] for role in request(app, "GET").json()} == SEEDED_ROLE_NAMES
