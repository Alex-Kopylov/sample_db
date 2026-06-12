# Database Question Answering Service

LangGraph-backed SQL agent over a tenant-isolated Postgres sample database. The
agent answers natural-language questions by generating SQL, while Postgres
Row-Level Security (RLS) keeps each authenticated customer scoped to their own
rows.

## Prerequisites

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/) for dependency management
- Postgres with `createdb` and `psql` available (for the local, non-Docker flow)
- Docker with Compose v2 (for the containerized flow)
- An OpenAI API key

## Quick start

From a clean checkout:

```bash
make setup
```

`make setup` installs dependencies, copies `.env.example` to `.env` if needed,
and prints the local database provisioning commands. Edit `.env` before running
the app:

```bash
OPENAI_API_KEY=...
PG_APP_DSN=postgresql://sample_app:sample_app_pw@127.0.0.1:5432/sample_db
PG_AUTH_DSN=postgresql://sample_auth:sample_auth_pw@127.0.0.1:5432/sample_db
JWT_SECRET=<strong local secret>
JWT_ALGORITHM=HS256
```

`.env` is gitignored and must not be committed.

Provision a local database from the repo root:

```bash
createdb sample_db
psql -v ON_ERROR_STOP=1 -d sample_db -f db/00_roles.sql
psql -v ON_ERROR_STOP=1 -d sample_db -f db/01_schema.sql
psql -v ON_ERROR_STOP=1 -d sample_db -f db/02_seed.sql
psql -v ON_ERROR_STOP=1 -d sample_db -f db/03_rls.sql
psql -v ON_ERROR_STOP=1 "postgresql://sample_app:sample_app_pw@127.0.0.1:5432/sample_db" -f db/validate_rls.sql
```

Every row printed by `db/validate_rls.sql` should be `PASS`.

Run the local verification suite:

```bash
make lint
make test
```

## Run with Docker

Docker runs the same `sql_agent` graph behind [Aegra](https://github.com/ibbybuilds/aegra)
(an open-source LangGraph Platform alternative), with Postgres + pgvector in the
same compose project. The Postgres container provisions itself on first start
(roles → schema → CSV seed → RLS → Aegra state database). Compose requires a
`.env` file (only `OPENAI_API_KEY`, `JWT_SECRET`, and `JWT_ALGORITHM` matter
here — the DSNs are overridden inside compose):

```bash
make setup                 # or: cp .env.example .env
# edit .env: OPENAI_API_KEY + JWT settings
make docker-up
curl -s http://127.0.0.1:2024/health
make docker-e2e
```

The API is published at `http://127.0.0.1:2024`, health is at `/health`, and the
containerized Postgres is published on `127.0.0.1:5433` by default so it does
not conflict with a local Postgres on `5432`. Use `POSTGRES_HOST_PORT` or
`LANGGRAPH_HOST_PORT` to override those host ports.

Stop containers with `make docker-down`. Reinitialize Postgres from scratch with
`make docker-clean && make docker-up`; this drops the named volume and reruns the
init scripts. See `docs/docker.md` for architecture, troubleshooting, and the
Aegra rationale.

## Development vs deployment

Both runtimes serve the same graph, auth handler, and (thread-based) API, so the
intended workflow is:

- **Develop locally** with `make run` (`langgraph dev`): hot reload plus the
  LangGraph Studio web UI at
  `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`.
- **Deploy** with `make docker-up`: Aegra serves the graph with persistent
  threads/runs in Postgres, no LangSmith license required.

The `langgraph` library stays a runtime dependency either way — Aegra replaces
only the platform server, not the graph framework.

## Usage

Start the LangGraph API server:

```bash
make run
```

By default this serves `http://127.0.0.1:2024` with docs at `/docs`. Override
the bind address or port when needed:

```bash
make run HOST=127.0.0.1 PORT=2030
```

Stop the server with `Ctrl-C`.

Requests require a bearer JWT. For local development, mint a token for one of
the seeded customer emails:

```bash
TOKEN=$(uv run python -m sample_db.mint_token user_007@example.test)
```

Use assistant id `sql_agent`. Create a thread, then run it and wait for the
result (this flow works on both the local dev server and the Aegra container):

```bash
THREAD_ID=$(curl -s -X POST http://127.0.0.1:2024/threads \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{}' | uv run python -c 'import json,sys; print(json.load(sys.stdin)["thread_id"])')

curl -s -X POST "http://127.0.0.1:2024/threads/$THREAD_ID/runs/wait" \
  -H "Authorization: Bearer $TOKEN" \
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

The local dev server additionally supports stateless `POST /runs/wait`; the
Aegra container is thread-based only.

## Make targets

- `make setup` installs dependencies and scaffolds `.env`.
- `make db` prints the local Postgres provisioning commands.
- `make lint` runs Ruff, Flake8, and Vulture.
- `make format` formats Python files with Ruff.
- `make test` runs pytest.
- `make run` starts the LangGraph dev server.
- `make e2e` starts an isolated local server and runs the HTTP auth/RLS checks.
- `make docker-up` / `make docker-down` / `make docker-clean` manage the compose stack.
- `make docker-e2e` runs the auth/RLS e2e suite from the host and from inside the docker network.
- `make docker-validate-rls` runs `db/validate_rls.sql` inside the Postgres container.
- `make docker-logs` / `make docker-psql` for inspection.

`make e2e` refuses to reuse a busy port. Pick another one when needed:

```bash
make e2e E2E_PORT=2031
```

See `docs/authentication.md` for the JWT auth flow and end-to-end testing.
