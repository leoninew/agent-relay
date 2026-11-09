PNPM := corepack pnpm
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
	$(PNPM) typecheck
	$(PNPM) $(LINT_SCRIPT)
	$(PNPM) $(FORMAT_SCRIPT)

test:
	$(PNPM) test

deps:
	$(PNPM) install --frozen-lockfile
