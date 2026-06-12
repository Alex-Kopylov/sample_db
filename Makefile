UV_CACHE_DIR ?= .uv-cache
UV = UV_CACHE_DIR=$(UV_CACHE_DIR) uv

HOST ?= 127.0.0.1
PORT ?= 2024
E2E_PORT ?= 2030

.PHONY: setup lint format db test run e2e docker-build docker-up docker-down docker-clean docker-logs docker-psql docker-validate-rls docker-e2e

setup:
	$(UV) sync
	@test -f .env || cp .env.example .env
	$(MAKE) db
	@echo "Setup complete — fill .env, provision Postgres, then run 'make run'."

lint:
	$(UV) run ruff check .
	$(UV) run flake8 .
	$(UV) run vulture

format:
	$(UV) run ruff format .

db:
	@echo "Provision a local Postgres database from the repo root with:"
	@echo "  createdb sample_db"
	@echo "  psql -v ON_ERROR_STOP=1 -d sample_db -f db/00_roles.sql"
	@echo "  psql -v ON_ERROR_STOP=1 -d sample_db -f db/01_schema.sql"
	@echo "  psql -v ON_ERROR_STOP=1 -d sample_db -f db/02_seed.sql"
	@echo "  psql -v ON_ERROR_STOP=1 -d sample_db -f db/03_rls.sql"
	@echo "  psql -v ON_ERROR_STOP=1 \"postgresql://sample_app:sample_app_pw@127.0.0.1:5432/sample_db\" -f db/validate_rls.sql"

test:
	$(UV) run pytest

run:
	$(UV) run langgraph dev --no-browser --host $(HOST) --port $(PORT)

e2e:
	LC_ALL=C LANG=C PORT=$(E2E_PORT) scripts/e2e/run_e2e.sh

docker-build:
	docker compose build

docker-up:
	docker compose up -d --build --wait
	@echo "API: http://$$(docker compose port langgraph 2024)"
	@echo "Health: http://$$(docker compose port langgraph 2024)/health"
	@echo "Postgres: $$(docker compose port postgres 5432)"

docker-down:
	docker compose down --remove-orphans

docker-clean:
	docker compose down -v --remove-orphans

docker-logs:
	docker compose logs -f

docker-psql:
	docker compose exec -e PGPASSWORD=$${POSTGRES_SUPERUSER_PW:-postgres_dev_pw} postgres psql -U postgres -d sample_db

docker-validate-rls:
	docker compose exec -e PGPASSWORD=sample_app_pw postgres psql -U sample_app -d sample_db -f /db/validate_rls.sql

docker-e2e:
	SERVER_URL=http://$$(docker compose port langgraph 2024) $(UV) run python scripts/e2e/e2e_auth.py
	docker compose run --rm --build e2e
