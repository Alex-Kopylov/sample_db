.PHONY: setup lint format db test run

setup:
	uv sync
	@test -f .env || cp .env.example .env
	$(MAKE) db
	@echo "Setup complete — add your OPENAI_API_KEY to .env, then run 'make run'."

lint:
	uv run ruff check .
	uv run flake8 .
	uv run vulture

format:
	uv run ruff format .

db:
	@echo "Postgres is provisioned out-of-band. Use db/validate_rls.sql to validate RLS."

test:
	uv run pytest

run:
	uv run langgraph dev
