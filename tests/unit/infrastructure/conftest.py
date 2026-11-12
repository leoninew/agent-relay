from typing import Any

import pytest


@pytest.fixture
def skill_payload() -> dict[str, Any]:
    return {
        "data": [
            {
                "cwd": "D:/project",
                "skills": [
                    {
                        "name": "example",
                        "description": "Full description",
                        "path": "D:/project/.agents/skills/example/SKILL.md",
                        "scope": "repo",
                        "enabled": True,
                        "interface": {
                            "displayName": "Example",
                            "shortDescription": "Short description",
                        },
                    }
                ],
                "errors": [],
            }
        ]
    }


@pytest.fixture
def mcp_server() -> dict[str, Any]:
    return {
        "name": "docs",
        "authStatus": "unsupported",
        "runtimeStatus": "connected",
        "tools": {"read": {"name": "read", "description": "Read docs", "inputSchema": {}}},
        "resources": [],
        "resourceTemplates": [],
    }
