# Once — canonical developer task runner.
#
# Self-documenting Makefile. Every public target has a `## description` comment
# on the same line and is grouped under a `##@ Section` header. Run `make` (or
# `make help`) for the full menu.
#
# Compatible with GNU Make 4.x (Linux, macOS Homebrew, Git Bash on Windows).
# Windows users without GNU Make: use `.\tasks.ps1 <target>` instead — see
# CHEATSHEET.md for the equivalence table.

# ── Shell hygiene ──────────────────────────────────────────────────────────
SHELL          := /bin/bash
.SHELLFLAGS    := -eu -o pipefail -c
.DEFAULT_GOAL  := help
MAKEFLAGS      += --no-print-directory --warn-undefined-variables

# ── Project layout ─────────────────────────────────────────────────────────
ROOT_DIR       := $(CURDIR)
BACKEND_DIR    := $(ROOT_DIR)/backend
FRONTEND_DIR   := $(ROOT_DIR)/frontend
EXTENSION_DIR  := $(ROOT_DIR)/extension
VERIFIER_DIR   := $(ROOT_DIR)/verifier
ONCETAX_DIR    := $(ROOT_DIR)/oncetax
SCRIPTS_DIR    := $(ROOT_DIR)/scripts
COV_DIR        := $(ROOT_DIR)/.cov

# ── Tools ──────────────────────────────────────────────────────────────────
PYTHON         ?= python
PIP            ?= pip
NPM            ?= npm
DOCKER         ?= docker
COMPOSE        ?= $(DOCKER) compose
PYTEST         ?= pytest
RUFF           ?= ruff
MYPY           ?= mypy
ALEMBIC        ?= alembic

# Backend venv binaries (created by `make setup`).
VENV           := $(BACKEND_DIR)/.venv
ifeq ($(OS),Windows_NT)
VENV_BIN       := $(VENV)/Scripts
VENV_PY        := $(VENV_BIN)/python.exe
else
VENV_BIN       := $(VENV)/bin
VENV_PY        := $(VENV_BIN)/python
endif

# ── ANSI colors (no-op when not a TTY / NO_COLOR set) ──────────────────────
ifeq ($(NO_COLOR),)
C_BOLD := \033[1m
C_DIM  := \033[2m
C_GRN  := \033[32m
C_YEL  := \033[33m
C_CYN  := \033[36m
C_OFF  := \033[0m
endif

.PHONY: help
help: ## Show this help (auto-generated from `## comments`).
	@printf "$(C_BOLD)Once dev tasks$(C_OFF) — usage: $(C_CYN)make <target>$(C_OFF)\n\n"
	@awk 'BEGIN {FS = ":.*?## "} \
		/^##@/ { printf "\n$(C_YEL)%s$(C_OFF)\n", substr($$0, 5); next } \
		/^[a-zA-Z0-9_-]+:.*?## / { printf "  $(C_GRN)%-22s$(C_OFF) %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)
	@printf "\n$(C_DIM)Tip: `make doctor` validates your environment; `make demo` is end-to-end.$(C_OFF)\n"

##@ Setup & environment
.PHONY: setup
setup: ## Bootstrap venvs, npm installs, playwright browsers, pre-commit hooks.
	$(PYTHON) $(SCRIPTS_DIR)/dev_setup.py

.PHONY: doctor
doctor: ## Diagnose local environment (versions, ports, env vars, disk space).
	$(PYTHON) $(SCRIPTS_DIR)/dev_doctor.py

.PHONY: clean
clean: ## Remove caches, venvs, node_modules, build outputs.
	@echo "Cleaning Python caches…"
	@find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache -o -name .mypy_cache -o -name htmlcov -o -name .coverage \) -prune -exec rm -rf {} + 2>/dev/null || true
	@rm -rf $(VENV) $(COV_DIR)
	@echo "Cleaning JS caches…"
	@rm -rf $(FRONTEND_DIR)/node_modules $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/.vite
	@rm -rf $(EXTENSION_DIR)/node_modules $(EXTENSION_DIR)/dist
	@rm -rf $(ONCETAX_DIR)/node_modules $(ONCETAX_DIR)/dist $(ONCETAX_DIR)/.wrangler
	@echo "Done."

##@ Compose stack
.PHONY: up
up: ## docker compose up -d (db, redis, backend, worker, beat, frontend, fixtures).
	$(COMPOSE) up -d --build

.PHONY: down
down: ## docker compose down (preserves volumes).
	$(COMPOSE) down

.PHONY: logs
logs: ## Tail combined logs for all services.
	$(COMPOSE) logs -f --tail=200

.PHONY: ps
ps: ## Show compose service status.
	$(COMPOSE) ps

.PHONY: shell-db
shell-db: ## Open a psql shell on the dev database.
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-once} -d $${POSTGRES_DB:-once}

.PHONY: shell-backend
shell-backend: ## Open a bash shell inside the backend container.
	$(COMPOSE) exec backend bash

##@ Data lifecycle
.PHONY: seed
seed: ## Seed the demo tenant (idempotent).
	$(VENV_PY) $(SCRIPTS_DIR)/seed_demo_tenant.py

.PHONY: reset
reset: ## Nuke local DB volumes, re-migrate, re-seed (destructive).
	$(PYTHON) $(SCRIPTS_DIR)/dev_reset.py

.PHONY: demo
demo: up seed ## End-to-end demo: stack + seed + open browser.
	@$(PYTHON) -c "import webbrowser; webbrowser.open('http://localhost:5173')" 2>/dev/null || true
	@echo "Frontend: http://localhost:5173   API docs: http://localhost:8000/docs   Verifier: http://localhost:8080"

##@ Tests
.PHONY: test
test: test-backend test-frontend test-extension test-verifier ## Run all four test suites.

.PHONY: test-backend
test-backend: ## Backend pytest suite.
	cd $(BACKEND_DIR) && $(PYTEST) -q

.PHONY: test-frontend
test-frontend: ## Frontend vitest/jest suite.
	cd $(FRONTEND_DIR) && $(NPM) test --silent

.PHONY: test-extension
test-extension: ## Extension vitest suite.
	cd $(EXTENSION_DIR) && $(NPM) test --silent

.PHONY: test-verifier
test-verifier: ## Verifier pytest suite.
	cd $(VERIFIER_DIR) && $(PYTEST) -q

.PHONY: test-integration
test-integration: ## Nginx-fixture portal + Playwright submitter smoke tests.
	RUN_INTEGRATION_TESTS=1 cd $(BACKEND_DIR) && $(PYTEST) -q -m integration

.PHONY: test-watch
test-watch: ## Backend pytest in watch mode (pytest-watch / ptw).
	cd $(BACKEND_DIR) && $(PYTEST) -q --looponfail || $(PYTHON) -m pytest_watch

##@ Lint, format, typecheck
.PHONY: lint
lint: ## Run all linters (ruff, eslint, prettier --check, tsc --noEmit).
	$(PYTHON) $(SCRIPTS_DIR)/lint_all.py

.PHONY: fmt
fmt: ## Auto-format Python + TS/JSON/MD/YAML across the repo.
	$(PYTHON) $(SCRIPTS_DIR)/format_all.py

.PHONY: typecheck
typecheck: ## mypy backend + tsc frontend/extension/verifier-types.
	cd $(BACKEND_DIR) && $(MYPY) app || true
	cd $(FRONTEND_DIR) && npx tsc --noEmit
	cd $(EXTENSION_DIR) && npx tsc --noEmit

##@ Migrations
.PHONY: migrate
migrate: ## Apply all pending alembic migrations (head).
	cd $(BACKEND_DIR) && $(ALEMBIC) upgrade head

.PHONY: migrate-new
migrate-new: ## Create a new autogenerate revision (use: make migrate-new MSG="add x").
	@[ -n "$(MSG)" ] || (echo "Usage: make migrate-new MSG=\"description\"" && exit 2)
	cd $(BACKEND_DIR) && $(ALEMBIC) revision --autogenerate -m "$(MSG)"

.PHONY: migrate-down
migrate-down: ## Roll back one alembic revision.
	cd $(BACKEND_DIR) && $(ALEMBIC) downgrade -1

##@ Build
.PHONY: build-backend
build-backend: ## Build the backend Docker image.
	$(DOCKER) build -t once/backend:dev $(BACKEND_DIR)

.PHONY: build-frontend
build-frontend: ## Build the frontend (Vite production bundle).
	cd $(FRONTEND_DIR) && $(NPM) run build

.PHONY: build-extension
build-extension: ## Build the MV3 extension into extension/dist/.
	cd $(EXTENSION_DIR) && $(NPM) run build

.PHONY: build-all
build-all: build-backend build-frontend build-extension ## Build every shippable artifact.

##@ Security & coverage
.PHONY: security
security: ## Run bandit + pip-audit + npm audit (best-effort, non-fatal).
	-cd $(BACKEND_DIR) && bandit -q -r app -x tests
	-cd $(BACKEND_DIR) && pip-audit -q
	-cd $(FRONTEND_DIR) && $(NPM) audit --audit-level=high
	-cd $(EXTENSION_DIR) && $(NPM) audit --audit-level=high

.PHONY: coverage
coverage: ## Run all coverage suites and print a combined report.
	$(PYTHON) $(SCRIPTS_DIR)/coverage_report.py

##@ Docs
.PHONY: docs
docs: ## Lint markdown (prettier --check) and check internal links.
	npx --yes prettier --check "**/*.md" --ignore-path .gitignore || true

##@ Observability
.PHONY: obs-up
obs-up: ## Start the optional observability stack (Prom/Grafana/Loki/Promtail).
	$(COMPOSE) -f ops/observability/docker-compose.observability.yml up -d

.PHONY: obs-down
obs-down: ## Stop the observability stack.
	$(COMPOSE) -f ops/observability/docker-compose.observability.yml down

##@ Realistic seed (L3.2)
.PHONY: seed-realistic
seed-realistic: ## Seed the demo tenant with the realistic 3-month transcript (idempotent).
	$(VENV_PY) $(BACKEND_DIR)/scripts/seed_realistic.py

.PHONY: seed-reset-realistic
seed-reset-realistic: ## Remove ONLY the rows created by seed-realistic (preserves user data).
	$(VENV_PY) $(BACKEND_DIR)/scripts/seed_realistic_reset.py

##@ Performance
.PHONY: perf-smoke
perf-smoke: ## Quick perf smoke (5 users × 60s) — assumes stack is up + seeded.
	$(VENV_PY) -m locust -f tools/perf/locustfile.py --headless -u 5 -r 1 -t 60s --host http://localhost:8000 --csv $(ROOT_DIR)/tools/perf/.last_smoke --html $(ROOT_DIR)/tools/perf/.last_smoke.html --only-summary

.PHONY: perf-baseline
perf-baseline: ## Full baseline (50 users × 5min, ramped) — assumes stack is up + seeded.
	$(VENV_PY) -m locust -f tools/perf/locustfile.py --headless -u 50 -r 2 -t 5m --host http://localhost:8000 --csv $(ROOT_DIR)/tools/perf/.last_baseline --html $(ROOT_DIR)/tools/perf/.last_baseline.html --only-summary

.PHONY: perf-report
perf-report: ## Print the last perf summary side-by-side with the committed baseline.
	$(VENV_PY) tools/perf/compare.py

# Catch-all so a typo prints help instead of failing silently.
.PHONY: %
%:
	@echo "Unknown target: $@" >&2
	@$(MAKE) help
	@exit 2
