# Database Question Answering Service

LangGraph-backed SQL agent over a tenant-isolated Postgres sample database. The
agent answers natural-language questions by generating SQL, while Postgres
Row-Level Security (RLS) keeps each authenticated customer scoped to their own
rows.

## Prerequisites

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/) for dependency management
- Postgres with `createdb` and `psql` available
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

Use assistant id `sql_agent`. You can create a thread with `POST /threads` and
then run it with `POST /threads/{id}/runs`, or use stateless `POST /runs/wait`:

```bash
curl -s -X POST http://127.0.0.1:2024/runs/wait \
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

## Make targets

- `make setup` installs dependencies and scaffolds `.env`.
- `make db` prints the local Postgres provisioning commands.
- `make lint` runs Ruff, Flake8, and Vulture.
- `make format` formats Python files with Ruff.
- `make test` runs pytest.
- `make run` starts the LangGraph dev server.
- `make e2e` starts an isolated local server and runs the HTTP auth/RLS checks.

`make e2e` refuses to reuse a busy port. Pick another one when needed:

```bash
make e2e E2E_PORT=2031
```

See `docs/authentication.md` for the JWT auth flow and end-to-end testing.
