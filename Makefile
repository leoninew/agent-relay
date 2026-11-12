.DEFAULT_GOAL := help

fix ?= 0
profile ?= dev
PNPM ?= $(if $(filter Windows_NT,$(OS)),corepack.cmd,corepack) pnpm
export PNPM

RUFF_CHECK_ARGS := $(if $(filter 1,$(fix)),--fix,)
RUFF_FORMAT_ARGS := $(if $(filter 1,$(fix)),.,--check .)
WEB_LINT_SCRIPT := $(if $(filter 1,$(fix)),lint:fix,lint)
WEB_FORMAT_SCRIPT := $(if $(filter 1,$(fix)),format:write,format)

.PHONY: help deps install check test web desktop binary migrate webapi

help:
	@printf "Available targets:\n"
	@printf "  make deps             Install locked backend and frontend dependencies\n"
	@printf "  make install          Install CLI and publish MCP/skill to Codex\n"
	@printf "  make check [fix=1]    Check backend and frontend types, lint, and format; fix=1 applies fixes\n"
	@printf "  make test             Run backend and frontend unit tests\n"
	@printf "  make web              Start the Vite development server on port 9081\n"
	@printf "  make desktop          Build the frontend and start the WebView application\n"
	@printf "  make binary           Build the Windows GUI and console package and ZIP\n"
	@printf "  make migrate          Upgrade the configured database schema\n"
	@printf "  make webapi           Start the FastAPI development server on port 9080\n"

deps:
	uv sync --all-groups --locked
	cd web && $(PNPM) install --frozen-lockfile

install:
	uv run --locked python scripts/install.py plugin check --codex
	uv tool install --editable . --force
	agent-relay --help
	uv run --locked python scripts/install.py plugin apply --codex
	@printf "Restart Codex sessions to load the installed MCP and skill.\n"

check:
	uv run --locked mypy src tests
	uv run --locked ruff check . $(RUFF_CHECK_ARGS)
	uv run --locked ruff format $(RUFF_FORMAT_ARGS)
	cd web && $(PNPM) run typecheck
	cd web && $(PNPM) run $(WEB_LINT_SCRIPT)
	cd web && $(PNPM) run $(WEB_FORMAT_SCRIPT)

test:
	uv run --locked pytest tests/unit
	cd web && $(PNPM) run test

web:
	cd web && $(PNPM) exec vite --mode "$(profile)"

desktop:
	cd web && $(PNPM) build
	uv run --locked --extra desktop python -m agent_relay.desktop

binary:
	uv sync --all-groups --locked --extra desktop
	cd web && $(PNPM) install --frozen-lockfile && $(PNPM) build
	uv run --locked --no-sync pyinstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller packaging/AgentRelay.spec
	uv run --locked --no-sync python scripts/binary.py

migrate webapi: export AGENT_RELAY_PROFILE = $(profile)
migrate:
	uv run --locked python -m agent_relay.migrate

webapi:
	uv run --locked python -m agent_relay.server
