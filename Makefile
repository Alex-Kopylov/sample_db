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
	uv run python -c "from sample_db.db import init_db; init_db('data/app.db')"

test:
	uv run pytest

run:
	uv run langgraph dev
