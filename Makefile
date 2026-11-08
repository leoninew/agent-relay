.DEFAULT_GOAL := help

fix ?= 0
profile ?= dev

RUFF_CHECK_ARGS := $(if $(filter 1,$(fix)),--fix,)
RUFF_FORMAT_ARGS := $(if $(filter 1,$(fix)),.,--check .)

.PHONY: help deps install check test web migrate webapi

help:
	@printf "Available targets:\n"
	@printf "  make deps             Install locked backend and frontend dependencies\n"
	@printf "  make install          Install CLI and publish MCP/skill to Codex\n"
	@printf "  make check            Check backend and frontend types, lint, and format\n"
	@printf "  make check fix=1      Apply backend and frontend lint and format fixes\n"
	@printf "  make test             Run backend and frontend unit tests\n"
	@printf "  make web              Start the Vite development server on port 9081\n"
	@printf "  make migrate          Upgrade the configured database schema\n"
	@printf "  make webapi           Start the FastAPI development server on port 9080\n"
	@printf "  profile=dev           Select .env.dev (default); use profile=qa for .env.qa\n"

deps:
	uv sync --all-groups --locked
	cd web && corepack yarn install --immutable

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
	$(MAKE) -C web check fix=$(fix)

test:
	uv run --locked pytest
	$(MAKE) -C web test

web:
	cd web && corepack yarn dev --mode $(profile)

migrate webapi: export AGENT_RELAY_PROFILE = $(profile)
migrate:
	uv run --locked python -m agent_relay.migrate

webapi:
	uv run --locked python -m agent_relay.server
