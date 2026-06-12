HOST ?= 127.0.0.1
PORT ?= 2024
E2E_PORT ?= 2030

.PHONY: setup lint format db test run e2e

setup:
	uv sync
	@test -f .env || cp .env.example .env
	$(MAKE) db
	@echo "Setup complete — fill .env, provision Postgres, then run 'make run'."

lint:
	uv run ruff check .
	uv run flake8 .
	uv run vulture

format:
	uv run ruff format .

db:
	@echo "Provision a local Postgres database from the repo root with:"
	@echo "  createdb sample_db"
	@echo "  psql -v ON_ERROR_STOP=1 -d sample_db -f db/00_roles.sql"
	@echo "  psql -v ON_ERROR_STOP=1 -d sample_db -f db/01_schema.sql"
	@echo "  psql -v ON_ERROR_STOP=1 -d sample_db -f db/02_seed.sql"
	@echo "  psql -v ON_ERROR_STOP=1 -d sample_db -f db/03_rls.sql"
	@echo "  psql -v ON_ERROR_STOP=1 \"postgresql://sample_app:sample_app_pw@127.0.0.1:5432/sample_db\" -f db/validate_rls.sql"

test:
	uv run pytest

run:
	uv run langgraph dev --no-browser --host $(HOST) --port $(PORT)

e2e:
	LC_ALL=C LANG=C PORT=$(E2E_PORT) ./run_e2e.sh
