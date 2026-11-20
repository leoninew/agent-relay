import asyncio
from pathlib import Path
from unittest.mock import Mock

import httpx2
import pytest
from fastapi import FastAPI

from conflua.application.dto.member_roles import MemberRoleInput
from conflua.bootstrap.http import create_app
from conflua.infrastructure.persistence.database import Database

pytestmark = pytest.mark.integration

ROLE_PATH = "/api/member-role"


def create_role_app(database: Database, tmp_path: Path) -> FastAPI:
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


def test_role_crud(database: Database, tmp_path: Path) -> None:
    app = create_role_app(database, tmp_path)
    response = request(app, "POST", body={"name": "  Reviewer  ", "prompt": "  Read\nReview  "})
    assert response.status_code == 201
    role = response.json()
    assert role == {"id": role["id"], "name": "Reviewer", "prompt": "Read\nReview"}
    for name in ("reviewer", "Developer"):
        assert request(app, "POST", body={"name": name, "prompt": "Test"}).status_code == 201
    assert {item["name"] for item in request(app, "GET").json()} == {
        "Developer",
        "Reviewer",
        "reviewer",
    }

    path = f"{ROLE_PATH}/{role['id']}"
    update = request(app, "PATCH", path, {"name": "Editor", "prompt": "Check"})
    assert update.status_code == 200
    assert update.json() == {"id": role["id"], "name": "Editor", "prompt": "Check"}
    deleted = request(app, "DELETE", path)
    assert deleted.status_code == 204 and not deleted.content
    assert {item["name"] for item in request(app, "GET").json()} == {
        "Developer",
        "reviewer",
    }


def test_role_get_reuses_open_request_session(file_database: Database, tmp_path: Path) -> None:
    app = create_role_app(file_database, tmp_path)
    request_scope = file_database.request_transaction()
    role_service = app.state.http_dependencies.request_member_role_service(request_scope)
    try:
        created = role_service.create(MemberRoleInput(name="Reviewer", prompt="Test"))
        assert role_service.get(created.id) == created
        assert request(app, "GET").json() == []
        request_scope.finish(commit=True)
    finally:
        request_scope.finish(commit=False)
    assert request(app, "GET").json() == [created.model_dump(by_alias=True)]
