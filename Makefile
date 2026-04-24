# Cratekeeper — local development Makefile
#
# Conventions:
#   - api targets run inside cratekeeper-api/ via `uv`
#   - web targets run inside cratekeeper-web/ via `npm`
#   - cli targets run inside cratekeeper-cli/ via `uv`
#   - db targets manage the shared Postgres container from docker-compose.yml

SHELL := /bin/bash

API_DIR := cratekeeper-api
WEB_DIR := cratekeeper-web
CLI_DIR := cratekeeper-cli

# Allow passing extra args to commands like `make crate ARGS="fetch --help"`
ARGS ?=

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nCratekeeper dev targets\n\nUsage: make <target>\n\nTargets:\n"} \
		/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)

##@ Setup

.PHONY: install
install: install-api install-web install-cli ## Install all dependencies (api, web, cli)

.PHONY: install-api
install-api: ## Install api dependencies (uv sync --all-extras)
	cd $(API_DIR) && uv sync --all-extras

.PHONY: install-web
install-web: ## Install web dependencies (npm install)
	cd $(WEB_DIR) && npm install

.PHONY: install-cli
install-cli: ## Install cli dependencies (uv sync)
	cd $(CLI_DIR) && uv sync

##@ Database

.PHONY: db-up
db-up: ## Start Postgres via docker compose (detached)
	docker compose up -d db

.PHONY: db-down
db-down: ## Stop Postgres container
	docker compose stop db

.PHONY: db-logs
db-logs: ## Tail Postgres logs
	docker compose logs -f db

.PHONY: db-shell
db-shell: ## psql shell into the dev database
	docker compose exec db psql -U dj -d djlib

.PHONY: migrate
migrate: ## Apply Alembic migrations to head
	cd $(API_DIR) && uv run alembic upgrade head

.PHONY: migration
migration: ## Create a new Alembic revision (use MSG="message")
	cd $(API_DIR) && uv run alembic revision --autogenerate -m "$(MSG)"

##@ API (FastAPI backend)

.PHONY: api
api: ## Run API dev server (127.0.0.1:8765)
	cd $(API_DIR) && uv run cratekeeper-api

.PHONY: api-reload
api-reload: ## Run API with uvicorn --reload
	cd $(API_DIR) && uv run uvicorn cratekeeper_api.main:app --host 127.0.0.1 --port 8765 --reload

.PHONY: api-test
api-test: ## Run API pytest suite
	cd $(API_DIR) && uv run pytest -q

.PHONY: api-test-watch
api-test-watch: ## Run API tests matching K=<expr>
	cd $(API_DIR) && uv run pytest -q -k "$(K)"

##@ Web (React + Vite UI)

.PHONY: web
web: ## Run web dev server (vite)
	cd $(WEB_DIR) && npm run dev

.PHONY: web-build
web-build: ## Production build of the web UI
	cd $(WEB_DIR) && npm run build

.PHONY: web-preview
web-preview: ## Preview the production build
	cd $(WEB_DIR) && npm run preview

##@ CLI (cratekeeper pipeline)

.PHONY: crate
crate: ## Run the `crate` CLI (e.g. make crate ARGS="--help")
	cd $(CLI_DIR) && uv run crate $(ARGS)

.PHONY: cli-build
cli-build: ## Build the cratekeeper-cli Docker image (essentia + TF models)
	docker compose build crate

.PHONY: cli-shell
cli-shell: ## Drop into a shell inside the crate container
	docker compose run --rm crate bash

##@ Combined

.PHONY: dev
dev: db-up ## Start db + api + web (api/web in foreground; ctrl-c stops both)
	@trap 'kill 0' INT TERM; \
	$(MAKE) -j2 api web

.PHONY: test
test: api-test ## Run all test suites

##@ Housekeeping

.PHONY: clean
clean: ## Remove build artefacts and caches
	rm -rf $(WEB_DIR)/dist $(WEB_DIR)/node_modules/.vite
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +

.PHONY: nuke
nuke: clean ## Remove node_modules and .venv directories (full reset)
	rm -rf $(WEB_DIR)/node_modules
	rm -rf $(API_DIR)/.venv $(CLI_DIR)/.venv
