# Docker Runtime

This compose stack runs the LangGraph SQL agent behind Aegra and a local
pgvector-enabled Postgres instance. The local credentials in compose are for
development only.

```mermaid
flowchart LR
    client[Client or host e2e] --> api[langgraph container<br/>Aegra API :2024]
    e2e[one-shot e2e container] --> api
    api --> sample[(sample_db<br/>app data + RLS)]
    api --> aegra[(aegra<br/>threads + runs)]
    postgres[postgres container<br/>pgvector/pgvector:pg17] --- sample
    postgres --- aegra
```

## Quick Start

```bash
make docker-up
curl -s http://127.0.0.1:2024/health
make docker-e2e
make docker-validate-rls
```

The API is published on `http://127.0.0.1:2024`. Postgres is published on
`localhost:5433` by default because this machine already has local Postgres on
`5432`. Override with `LANGGRAPH_HOST_PORT` or `POSTGRES_HOST_PORT`.

Use `make docker-down` to stop the stack. Use `make docker-clean` to remove the
Postgres volume and force a full database re-init on the next `make docker-up`.

## Why Aegra

The official LangChain standalone Agent Server is designed around a licensed
data plane with Postgres and Redis backing services. The [standalone deployment
docs](https://docs.langchain.com/langsmith/deploy-standalone-server) list
`LANGGRAPH_CLOUD_LICENSE_KEY` as a required variable and describe Postgres as
storing assistants, threads, runs, state, and queue data.

Custom auth is mandatory for this app because the JWT subject determines the
database RLS tenant (see [authentication.md](authentication.md)). LangChain's
[custom auth docs](https://docs.langchain.com/langsmith/custom-auth) show the
expected `@auth.authenticate(headers: dict)` shape and the `langgraph_auth_user`
contract.

The public Postgres runtime path was also not viable for this local stack:
[langchain-ai/langgraph#6709](https://github.com/langchain-ai/langgraph/issues/6709)
documents the missing `langgraph-runtime-postgres` package on PyPI and the
resulting import failure.

The prior implementation notes also referenced
[langchain-ai/langgraph discussion #5391](https://github.com/langchain-ai/langgraph/discussions/5391)
for the custom-auth licensing behavior; GitHub returned 404 for that discussion
during this update, so the official deployment/custom-auth docs above are the
durable references.

Aegra gives this repo the API surface we need without license keys:

- Agent Protocol endpoints compatible with `langgraph_sdk`.
- Postgres persistence for threads and runs.
- Custom `langgraph_sdk.Auth` handlers.
- A single-instance mode with Redis disabled.

The Aegra package used here is `aegra-api==0.9.21`. Current Aegra docs confirm
`aegra.json` config resolution, `AUTH_TYPE=custom`, `DATABASE_URL` precedence,
and `REDIS_BROKER_ENABLED=false` for in-process runs:

- [Configuration](https://docs.aegra.dev/reference/configuration)
- [Authentication](https://docs.aegra.dev/guides/authentication)
- [Environment variables](https://docs.aegra.dev/reference/environment-variables)
- [Worker architecture](https://docs.aegra.dev/guides/worker-architecture)

## Architecture

There is one Postgres container with two databases:

- `sample_db`: business tables, sample CSV rows, roles, grants, and RLS policies.
- `aegra`: Aegra server state, including persisted threads and runs.

The app role DSNs point at `sample_db`:

- `PG_APP_DSN=postgresql://sample_app:sample_app_pw@postgres:5432/sample_db`
- `PG_AUTH_DSN=postgresql://sample_auth:sample_auth_pw@postgres:5432/sample_db`

Aegra uses its own database:

- `DATABASE_URL=postgresql://aegra:aegra_pw@postgres:5432/aegra`

Compose `environment:` values override `env_file: .env`, and both override
anything baked into the image. The Docker image never copies `.env`; secrets
enter only through compose runtime environment.

Redis is intentionally off:

```yaml
REDIS_BROKER_ENABLED: "false"
```

With one Aegra instance, runs execute as in-process asyncio tasks. Add Redis and
set `REDIS_BROKER_ENABLED=true` only when horizontally scaling multiple API
instances or when Redis-backed streaming/recovery semantics are needed.

## Database Init

Postgres runs `/docker-entrypoint-initdb.d` only when the named volume is fresh.
The init order is lexical:

1. `00_roles.sql`: create local dev roles.
2. `01_schema.sql`: create business tables.
3. `02_load_data.sh`: load CSVs with header-aware client-side `\copy`.
4. `03_rls.sql`: enable and force RLS, then grant access.
5. `04_aegra_db.sh`: create the `aegra` role/database and pgvector extension.

Re-run the full init sequence with:

```bash
make docker-clean
make docker-up
```

## Troubleshooting

- Docker daemon blocked or stopped: start OrbStack, then rerun `docker version`.
- Host port `5432` already belongs to local Postgres: this stack publishes
  Postgres on `5433` by default.
- Force an image rebuild: `make docker-build` or `make docker-up`.
- Recreate all database data: `make docker-clean && make docker-up`.
- Follow service logs: `make docker-logs`.

## Related docs

- [README](../README.md) — project overview and the two run modes.
- [authentication.md](authentication.md) — the JWT → RLS tenant-isolation model.
- [HOW_TO_TEST_IT_WORKS.md](../HOW_TO_TEST_IT_WORKS.md) — step-by-step test runbook.
