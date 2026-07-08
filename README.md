# Database Question Answering Service

LangGraph-backed SQL agent over a tenant-isolated Postgres sample database. The
agent answers natural-language questions by generating SQL, while Postgres
Row-Level Security (RLS) keeps each authenticated customer scoped to their own
rows.

## Two ways to run it

The graph, the JWT auth handler, and the HTTP API are identical in both modes —
only the **server runtime** differs:

| | Develop: `langgraph dev` + LangSmith | Deploy: Aegra |
|---|---|---|
| Command | `mise run run` | `mise run docker-up` |
| Server | LangGraph CLI dev server | [Aegra](https://github.com/ibbybuilds/aegra) (open source) |
| Best for | Iterating locally with rich tooling | Self-hosting / production |
| UI & LLMOps | LangGraph Studio + LangSmith tracing, evals, observability | None (bring your own) |
| State | In-memory (dev server) | Persistent in Postgres |
| Custom JWT auth | Works | Works |
| License / account | LangSmith account (free tier) for the UI | None |

**Why Aegra for deployment.** The official LangGraph Platform server
(`langchain/langgraph-api`) gates **custom authentication behind an Enterprise
self-hosting license** — our JWT→RLS tenancy is exactly that, so the Lite/free
server refuses to start with it. Aegra is an open-source re-implementation of the
same Agent Protocol and `langgraph_sdk` API, so we get persistent threads/runs in
Postgres with **no vendor lock-in, no enterprise subscription, and no license
keys** — just our own infrastructure.

**Why LangSmith is still great for development.** LangSmith is an *optional
observability layer*, not the runtime boundary. During development `langgraph dev`
gives hot reload, the visual **LangGraph Studio**, and — with a free LangSmith
API key — full **LLMOps**: trace every run, inspect each node and SQL tool call,
debug failures, and run evals. Because the same graph and auth code run under both
runtimes, what you debug in LangSmith is what you ship on Aegra.

---

## Prerequisites

- Python 3.12 or newer, and [uv](https://docs.astral.sh/uv/)
- An OpenAI API key
- For dev mode: a local Postgres (`createdb`, `psql`) and a free
  [LangSmith](https://smith.langchain.com/) API key (for the UI/tracing)
- For Aegra mode: Docker with Compose v2 (nothing else)

## Quick start

```bash
mise run setup
```

`mise run setup` installs dependencies, copies `.env.example` to `.env` if
needed, and prints the database provisioning commands. Edit `.env`:

```bash
OPENAI_API_KEY=...
PG_APP_DSN=postgresql://sample_app:sample_app_pw@127.0.0.1:5432/sample_db
PG_AUTH_DSN=postgresql://sample_auth:sample_auth_pw@127.0.0.1:5432/sample_db
JWT_SECRET=<strong local secret>
JWT_ALGORITHM=HS256
```

`.env` is gitignored and must not be committed.

---

## 1. Develop with LangSmith (LLMOps UI)

Use this while building and debugging the agent.

**a. Add your LangSmith key to `.env`** (on top of the values above):

```bash
LANGSMITH_API_KEY=lsv2-...     # free tier is enough
LANGSMITH_TRACING=true         # stream every run to LangSmith
```

**b. Provision a local Postgres** (once), from the repo root:

```bash
createdb sample_db
psql -v ON_ERROR_STOP=1 -d sample_db -f db/00_roles.sql
psql -v ON_ERROR_STOP=1 -d sample_db -f db/01_schema.sql
psql -v ON_ERROR_STOP=1 -d sample_db -f db/02_seed.sql
psql -v ON_ERROR_STOP=1 -d sample_db -f db/03_rls.sql
psql -v ON_ERROR_STOP=1 "postgresql://sample_app:sample_app_pw@127.0.0.1:5432/sample_db" -f db/validate_rls.sql
```

Every row from `db/validate_rls.sql` should print `PASS`. (Prefer not to install
Postgres? Run `mise run docker-up` and point `PG_APP_DSN`/`PG_AUTH_DSN` at
`127.0.0.1:5433` instead.)

**c. Start the dev server:**

```bash
mise run run                   # langgraph dev on http://127.0.0.1:2024
```

This opens **LangGraph Studio** (a visual graph UI) and, with the LangSmith vars
set, streams traces to your LangSmith project for observability, debugging, and
evals. Override the bind address/port with
`HOST=127.0.0.1 PORT=2030 mise run run`.

---

## 2. Run with Aegra only (self-hosted, no LangSmith)

Use this to deploy, or to run the whole stack with nothing but Docker. No
LangSmith account, no license — see [`HOW_TO_TEST_IT_WORKS.md`](HOW_TO_TEST_IT_WORKS.md)
for a full step-by-step test runbook.

**a. Minimal `.env`** — only three values are needed (the Postgres DSNs are
injected by compose):

```bash
OPENAI_API_KEY=...
JWT_SECRET=<strong local secret>
JWT_ALGORITHM=HS256
```

**b. Build and run:**

```bash
mise run docker-up
curl -s http://127.0.0.1:2024/health
mise run docker-e2e           # auth/RLS e2e from host + inside the docker network
```

This starts two containers — `langgraph` (Aegra at `http://127.0.0.1:2024`) and
`postgres` (`pgvector/pg17` at `127.0.0.1:5433`, off 5432 so it never collides
with a local Postgres). Postgres provisions itself on first boot (roles → schema
→ CSV seed → RLS → Aegra state DB). Override host ports with `POSTGRES_HOST_PORT`
/ `LANGGRAPH_HOST_PORT`. Tear down with `mise run docker-down`, or wipe the
volume with `mise run docker-clean`.

---

## Usage

Requests require a bearer JWT. Mint a token for a seeded customer email:

```bash
TOKEN=$(uv run python -m sample_db.mint_token user_007@example.test)
```

Use assistant id `sql_agent`. Both runtimes accept a stateless run and a
thread-based run:

```bash
# Stateless — one call, no thread to manage:
curl -s -X POST http://127.0.0.1:2024/runs/wait \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{
    "assistant_id": "sql_agent",
    "input": {"messages": [{"role": "user", "content": "How many completed orders are there?"}]}
  }'

# Thread-based — keeps conversation state across runs:
THREAD_ID=$(curl -s -X POST http://127.0.0.1:2024/threads \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' \
  | uv run python -c 'import json,sys; print(json.load(sys.stdin)["thread_id"])')

curl -s -X POST "http://127.0.0.1:2024/threads/$THREAD_ID/runs/wait" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"assistant_id":"sql_agent","input":{"messages":[{"role":"user","content":"List my recent orders."}]}}'
```

Even if the model is asked for every customer's data, RLS returns only the
caller's rows. See [`docs/authentication.md`](docs/authentication.md) for the auth
flow and [`docs/docker.md`](docs/docker.md) for the container architecture and the
Aegra rationale.

## Mise tasks

- `mise run setup` — install deps and scaffold `.env`.
- `mise run db` — print the local Postgres provisioning commands.
- `mise run lint` / `mise run format` / `mise run test` — full template lint gate, Ruff format, pytest.
- `mise run run` — start the LangGraph dev server (dev mode).
- `mise run e2e` — start an isolated local server and run the HTTP auth/RLS checks.
- `mise run docker-up` / `mise run docker-down` / `mise run docker-clean` — manage the Aegra stack.
- `mise run docker-e2e` — run the auth/RLS e2e suite from the host and inside the docker network.
- `mise run docker-validate-rls` — run `db/validate_rls.sql` inside the Postgres container.
- `mise run docker-logs` / `mise run docker-psql` — inspect the running stack.
