YARN := corepack yarn
fix ?= 0

LINT_SCRIPT := $(if $(filter 1,$(fix)),lint:fix,lint)
FORMAT_SCRIPT := $(if $(filter 1,$(fix)),format:write,format)

.DEFAULT_GOAL := help

.PHONY: help deps check test

help:
	@printf "Available targets:\n"
	@printf "  make deps             Install locked frontend dependencies\n"
	@printf "  make check            Check types, lint, and format\n"
	@printf "  make check fix=1      Check types, then fix lint and format\n"
	@printf "  make test             Run frontend unit tests\n"

check:
	$(YARN) typecheck
	$(YARN) $(LINT_SCRIPT)
	$(YARN) $(FORMAT_SCRIPT)

test:
	$(YARN) vitest run

deps:
	$(YARN) install --immutable
