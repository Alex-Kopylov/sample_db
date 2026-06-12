# Database Question Answering Service

Python package scaffold for a LangGraph-backed SQL agent over the provisioned
Postgres sample database.

## Quick start

Spin up your own instance in three steps:

```bash
make setup                 # install deps, scaffold .env
# edit .env: OPENAI_API_KEY + Postgres DSNs + JWT settings
make run                   # start the LangGraph API server
```

`make setup` runs `uv sync` and copies `.env.example` to `.env` (when missing).
Fill in your `OPENAI_API_KEY` plus the Postgres DSNs and JWT settings; the
Postgres database itself is provisioned separately (see Setup below). `make run`
then serves the API at `http://127.0.0.1:2024` (docs at `/docs`).

## Setup

Install dependencies:

```bash
uv sync
```

Copy the example environment file, then fill in your OpenAI API key, the Postgres
DSNs, and the JWT settings:

```bash
cp .env.example .env
# then edit .env:
OPENAI_API_KEY=...
PG_APP_DSN=postgresql://sample_app:...@127.0.0.1:5432/sample_db
PG_AUTH_DSN=postgresql://sample_auth:...@127.0.0.1:5432/sample_db
JWT_SECRET=...
JWT_ALGORITHM=HS256
```

## Usage

Start the LangGraph API server:

```bash
make run
```

This runs:

```bash
uv run langgraph dev
```

The API is available at `http://127.0.0.1:2024`. API docs are available at
`http://127.0.0.1:2024/docs`.

Use assistant id `sql_agent`. You can create a thread with `POST /threads` and
then run it with `POST /threads/{id}/runs`, or use stateless `POST /runs`.

Example stateless run:

```bash
curl -s -X POST http://127.0.0.1:2024/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "assistant_id": "sql_agent",
    "input": {
      "messages": [
        {
          "role": "user",
          "content": "How many completed orders are there?"
        }
      ]
    }
  }'
```

The Postgres database is provisioned out-of-band (see `db/` for the schema,
roles, and RLS policies; the CSVs under `data/` hold the sample rows). The graph
does not create or load a database on import. Validate the tenant-isolation
setup with:

```bash
make db                                                  # provisioning/validation notes
psql -U sample_app -d sample_db -f db/validate_rls.sql   # every check must PASS
```

See `docs/authentication.md` for the JWT auth flow and end-to-end testing.
