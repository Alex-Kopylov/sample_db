# LangGraph SQL Agent — Implementation Plan

## Context

`sample_db` is the start of a "Database Question Answering Service" (per README). The repo currently has only data and tooling: `schema.sql` (customers, products, orders, order_items), four matching CSVs, a uv-style `pyproject.toml` with zero runtime deps, and lint config (ruff/flake8/vulture). Goal: build the SQL agent from the LangChain tutorial (https://docs.langchain.com/oss/python/langgraph/sql-agent) — the **full custom LangGraph graph** variant — querying a SQLite DB built from this project's own schema + CSVs, exposed via a simple CLI. No Docker; `uv` for everything.

**User decisions:** project's own data (not Chinook) · full custom graph from the docs · Anthropic Claude · CLI interface.

**Prerequisite (user action):** add `ANTHROPIC_API_KEY=...` to `.env` (it currently only has `LANGSMITH_API_KEY`). LangSmith tracing is optional and works automatically if `LANGSMITH_TRACING=true` is set.

## Architecture (mirrors the tutorial)

```
START → list_tables → call_get_schema → get_schema → generate_query ──(no tool call)──→ END
                                                          ↑   └─(tool call)→ check_query → run_query ─┘
```

- **3 tools** (raw `sqlite3`, no SQLAlchemy — same as the tutorial): `sql_db_list_tables`, `sql_db_schema(table_names)`, `sql_db_query(query)`
- **6 nodes**: `list_tables` (predetermined tool call), `call_get_schema` (`bind_tools(..., tool_choice="any")`), `get_schema` (`ToolNode`), `generate_query` (LLM with `run_query` tool bound; answers directly when no query needed), `check_query` (SQL-expert prompt that reviews/rewrites the pending query), `run_query` (`ToolNode`)
- **Model**: `init_chat_model("anthropic:claude-opus-4-8")`. Important: do **not** pass `temperature`/`top_p`/`top_k` — Opus 4.8 rejects sampling params with a 400.
- **Safety** (per the docs' guidance): the agent's query connection is opened **read-only** (`sqlite3.connect("file:data/app.db?mode=ro", uri=True)`) so DML can't execute even if generated; prompts also instruct: SELECT-only, limit 5 rows, no `SELECT *`.

## Files to create / modify

```
pyproject.toml          # add deps + [project.scripts] + hatchling build backend, src layout
src/sample_db/
  __init__.py
  db.py                 # init_db(): build data/app.db from schema.sql + CSVs; get_readonly_connection()
  tools.py              # the 3 @tool functions
  agent.py              # prompts + StateGraph wiring (MessagesState), compiled graph
  cli.py                # entrypoint: `sql-agent "question"` one-shot, or REPL with no args
tests/
  test_db.py            # init creates 4 tables, row counts match CSVs, read-only conn rejects INSERT
  test_tools.py         # list_tables/get_schema/run_query work; run_query can't mutate
Makefile                # add: db, run, test targets
README.md               # short usage section
.gitignore              # data/app.db, .venv, __pycache__ (no .gitignore exists yet)
```

### Details per step

1. **`pyproject.toml`**: dependencies = `langchain`, `langgraph`, `langchain-anthropic`, `python-dotenv`; dev group += `pytest`; add `[build-system]` (hatchling) and `[project.scripts] sql-agent = "sample_db.cli:main"`; `[tool.hatch.build.targets.wheel] packages = ["src/sample_db"]`. Install with `uv sync`.
2. **`db.py`**: `init_db()` runs `schema.sql` via `executescript`, then loads CSVs with stdlib `csv` + `executemany` in FK order (customers, products, orders, order_items). DB lives at `data/app.db`. CLI auto-inits if the file is missing.
3. **`tools.py`**: three `@tool`-decorated functions exactly as the tutorial shapes them; `sql_db_query` uses the read-only connection, catches `sqlite3.Error` and returns the error text (so the agent can self-correct), truncates large results.
4. **`agent.py`**: tutorial's node functions and prompts adapted to SQLite dialect + this schema; `should_continue` conditional edge from `generate_query`; compile without checkpointer (keep v1 simple; human-in-the-loop interrupt is a later iteration).
5. **`cli.py`**: `load_dotenv()`; with an arg → stream the graph for one question and print the final message; without args → simple REPL (`exit`/`quit` to leave). Fail fast with a clear message if `ANTHROPIC_API_KEY` is missing.
6. **Tests**: pure-Python (no LLM calls) against a tmp-path DB — keeps CI/key-free runs green.

## Verification

1. `uv sync` — deps resolve.
2. `uv run pytest` — db + tools tests pass.
3. `make lint` — ruff/flake8/vulture clean.
4. Smoke (needs `ANTHROPIC_API_KEY` in `.env`):
   `uv run sql-agent "Which country has the most customers?"` — expect the graph to walk list_tables → schema → generate → check → run and print a grounded answer.
   `uv run sql-agent "Delete all orders"` — expect a refusal / read-only error, no mutation (verify row counts unchanged).

## Execution routing (per your global CLAUDE.md)

This plan doubles as the spec for dispatch: steps 1–3, 5–6 (scaffolding, db loader, tools, CLI, tests) are mechanical and can go to codex via `/goal`; step 4 (graph wiring + prompts) is the hardest part and can stay in this session. Say the word and I'll route it that way, or implement it all here.


---

# Plan Feedback

I've reviewed this plan and have 3 pieces of feedback:

## 1. (line 9) Feedback on: "ANTHROPIC_API_KEY"
> openai

## 2. (line 20) Feedback on: "init_chat_model("anthropic:claude-opus-4-8")"
> openai latest mini model

## 3. (line 47) Feedback on: "load_dotenv()"
> pydantic base settings

---
