.PHONY: lint format db test run

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
