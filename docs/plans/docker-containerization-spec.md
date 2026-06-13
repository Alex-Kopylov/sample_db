# Spec: Containerize the LangGraph app (Aegra server) + Postgres (sample_db)

Audience: Codex CLI executing autonomously in this worktree.
Worktree root: `/Users/jhonsmith/sample_db/.claude/worktrees/nice-napier-690f51`
This is a **linked git worktree** — NEVER run `git commit/branch/merge/stash/reset`.
Leave all changes uncommitted in the working tree. `git status`/`git diff` are fine.

## Context (already researched — do not re-litigate the architecture)

- The app is a LangGraph SQL agent: graph `sql_agent` at `src/sample_db/agent.py:graph`,
  custom JWT auth wired via `langgraph.json` `"auth"` → `src/sample_db/auth.py:auth`.
  Business data lives in Postgres with row-level security (`db/00_roles.sql`,
  `db/01_schema.sql`, `db/03_rls.sql`); sample rows are CSVs **with headers** in `data/`.
- The official `langchain/langgraph-api` standalone image is **not usable**: custom
  authentication there is enterprise-license-gated (Self-Hosted Lite raises
  `ValueError: Custom authentication is currently available in the Managed Cloud
  version ... or with a self-hosting enterprise license`), and
  `langgraph-runtime-postgres` is not on PyPI (langchain-ai/langgraph#6709).
- **USER DECISION: use Aegra** (https://github.com/ibbybuilds/aegra) — the open-source
  LangGraph Platform alternative (FastAPI + Postgres, Agent Protocol, same
  `langgraph_sdk` client API) — as the server runtime inside the LangGraph container.
  Full thread/run persistence in Postgres, no license keys.
- Verified Aegra facts (from its repo/wiki — re-verify details against the installed
  version, versions move fast):
  - Config file `aegra.json`, same shape as `langgraph.json`: `{"graphs": {...},
    "auth": {"path": "..."}}`. Custom auth via `langgraph_sdk.Auth` IS supported.
  - **Auth handler receives `headers: dict`** (e.g. `async def authenticate(headers)`),
    not an injected `authorization` kwarg. Our handler must be adapted (see D6).
  - **Redis is OPTIONAL**: `REDIS_BROKER_ENABLED=false` → runs execute as in-process
    asyncio tasks. Single-instance deployment = Aegra + Postgres only. We use NO Redis
    container (document the multi-instance/Redis upgrade path in docs).
  - **No stateless `POST /runs/wait`.** Only thread-based:
    `POST /threads` then `POST /threads/{thread_id}/runs/wait` (returns the final
    state values incl. `messages`). Our e2e driver must switch transport (see D7).
  - Persistence: Postgres **with the pgvector extension** (their compose uses
    `pgvector/pgvector:pgXX` images). Connection via `DATABASE_URL` env var (takes
    precedence over `POSTGRES_*` vars). It can share one Postgres instance using its
    own database.
  - Server: PyPI CLI `aegra-cli`; the API app is `aegra_api.main:app` (uvicorn);
    port via `PORT` env or `--port` (default 2026 — we will run on **2024**).
    Healthchecks: `GET /health`, `/ready`, `/live`.
  - Check how Aegra applies its own DB migrations (CLI command or on-startup) and wire
    it so a fresh stack initializes itself (entrypoint may need a migrate step).
- Host machine: macOS, Docker via OrbStack (already being started). Local Postgres 17
  **already listens on host port 5432** — never bind host port 5432.
- Ports: API on host **2024** (and 2024 inside the container, so the in-network URL is
  `http://langgraph:2024`). Postgres host port **`${POSTGRES_HOST_PORT:-5433}`**.

## Prep (do these first)

1. `[ -f .env ] || cp /Users/jhonsmith/sample_db/.env .env` — gitignored; contains real
   `OPENAI_API_KEY`, `JWT_SECRET`, and DSNs pointing at `127.0.0.1:5432` for local dev.
   Leave the DSN values alone; docker overrides them via compose `environment:`.
2. `rm -rf .venv && uv sync` — the copied worktree venv has stale shebangs.
3. `docker version` must succeed; if the daemon is down: `open -a OrbStack`, wait ≤90s.
4. Skim the Aegra repo (clone it to /tmp or read on GitHub) for: exact server package
   name(s) to install, migration command, auth handler invocation, `aegra.json` schema,
   and their reference docker-compose. Trust their source over this spec's details.

## Deliverables

### D1. `Dockerfile` (repo root) — the LangGraph/Aegra service image
- Base `python:3.12-slim`. Install uv via `COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv` (or a pinned tag).
- Layer-cache friendly: copy `pyproject.toml` + `uv.lock` first, sync deps, then copy
  the project. Add the Aegra server package(s) as a dependency (prefer a normal
  `pyproject.toml` dependency + `uv lock` update so local and docker envs match; pin a
  version).
- **Never copy `.env` into the image** — `.dockerignore` must exclude it.
- `EXPOSE 2024`. CMD: run Aegra's API (migrations first if their design needs it),
  listening on `0.0.0.0:2024` — e.g. `uvicorn aegra_api.main:app --host 0.0.0.0 --port 2024`
  or `aegra serve`/entrypoint script, whichever their docs prescribe.
- Healthcheck without curl (slim image): python urllib GET `http://127.0.0.1:2024/health`.
- `.dockerignore`: `.git`, `.venv`, `.env*`, `__pycache__`, `.claude`, `data/`. The
  image MUST still contain `src/`, `aegra.json`, `e2e_auth.py`.

### D2. `aegra.json` (repo root)
- Mirror `langgraph.json`: `sql_agent` graph → `./src/sample_db/agent.py:graph`,
  `auth.path` → `./src/sample_db/auth.py:auth`. Keep `langgraph.json` untouched for
  the local `langgraph dev` flow. If Aegra needs an `AUTH_TYPE`-style env toggle to
  activate custom auth, set it in compose.

### D3. `docker-compose.yml` (repo root)
- `postgres` service: image `pgvector/pgvector:pg17`; `POSTGRES_DB=sample_db`;
  superuser password `${POSTGRES_SUPERUSER_PW:-postgres_dev_pw}`; named volume
  `pgdata:/var/lib/postgresql/data`; init mounts in lexical order into
  `/docker-entrypoint-initdb.d/`:
  - `./db/00_roles.sql` → `00_roles.sql`
  - `./db/01_schema.sql` → `01_schema.sql`
  - `./docker/02_load_data.sh` → `02_load_data.sh` (NEW, see D4)
  - `./db/03_rls.sql` → `03_rls.sql`
  - `./docker/04_aegra_db.sh` → `04_aegra_db.sh` (NEW, see D5)
  - plus `./data:/data:ro` and `./db:/db:ro` (for the validate target);
  - healthcheck `pg_isready -U postgres -d sample_db`;
  - ports `"${POSTGRES_HOST_PORT:-5433}:5432"`.
- `langgraph` service (the Aegra server): `build: .`;
  ports `"${LANGGRAPH_HOST_PORT:-2024}:2024"`; `env_file: .env`; `environment:` overrides:
  - `PG_APP_DSN=postgresql://sample_app:sample_app_pw@postgres:5432/sample_db`
  - `PG_AUTH_DSN=postgresql://sample_auth:sample_auth_pw@postgres:5432/sample_db`
  - `DATABASE_URL=postgresql://aegra:aegra_pw@postgres:5432/aegra` (Aegra's own DB;
    adjust the scheme/driver suffix to what Aegra expects, e.g. `+asyncpg`, per its docs)
  - `REDIS_BROKER_ENABLED=false`, `PORT=2024`, plus whatever auth/config toggles Aegra needs;
  - `depends_on: postgres: condition: service_healthy`; healthcheck `GET /health`.
- `e2e` service: `profiles: ["e2e"]`; same image; `env_file: .env`; `environment:`
  `SERVER_URL=http://langgraph:2024` + the same DSN/JWT vars (Settings needs all fields);
  command runs `e2e_auth.py` with the image's python;
  `depends_on: langgraph: condition: service_healthy`. This proves
  **container-to-container** access through compose-network DNS.
- The `sample_app_pw`/`sample_auth_pw`/`aegra_pw` credentials are local-dev only —
  call that out in docs.

### D4. `docker/02_load_data.sh` — CSV load during postgres initdb
- bash, `set -euo pipefail`; `psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"`
  with client-side `\copy` in FK order: customers, products, orders, order_items —
  `\copy customers FROM '/data/customers.csv' WITH (FORMAT csv, HEADER true)` etc.
- Runs only on a fresh volume (initdb semantics) — fine; `make docker-clean` is the
  documented re-init path. Echo row counts at the end.

### D5. `docker/04_aegra_db.sh` — Aegra's own database
- Create role `aegra` (LOGIN, password `aegra_pw`), database `aegra` owned by it, and
  `CREATE EXTENSION IF NOT EXISTS vector;` inside that database (run as superuser).
  Keep Aegra state fully separate from `sample_db` (RLS world stays pristine).

### D6. Auth handler compatibility (`src/sample_db/auth.py` + tests)
- Adapt the `@auth.authenticate` handler so it works under BOTH runtimes:
  Aegra passes `headers: dict`; `langgraph dev` can also inject `headers`. So change
  the signature to accept headers and extract the Authorization value inside
  (`_extract_bearer_token` logic stays). Handle both `str` and `bytes` keys/values
  (langgraph dev historically passes byte keys) and case-insensitivity.
- **Behavior must not change**: same 401 details, same identity dict
  (`{"identity": str(customer_id), "email": email}`). Verify against Aegra's actual
  auth invocation code (read its source) — if it supports param-name injection of
  `authorization` directly, prefer the minimal change that works on both.
- Update `tests/test_auth.py` minimally to match the new signature; all existing
  assertion intents stay.

### D7. E2E driver transport (`e2e_auth.py`)
- Aegra has no stateless `POST /runs/wait`. Switch the driver to the thread-based
  flow supported by BOTH runtimes: `POST /threads` (empty body or `{}`) then
  `POST /threads/{thread_id}/runs/wait` with the same
  `{"assistant_id": "sql_agent", "input": {...}}` payload; the response is the final
  state (dict with `messages`) — `all_emails_in_state` keeps working.
- Auth semantics preserved: every case performs the full flow with its token; the
  recorded status is the first non-2xx response (so the missing/garbage-token cases
  assert 401/403 on thread creation already). **Assertions and check labels stay
  exactly as they are** (5 checks, same isolation/adversarial logic).
- Must still pass against the LOCAL dev server: `./run_e2e.sh` (it boots
  `langgraph dev` on port 2030 and runs this same driver) — verify it.

### D8. `Makefile` — add targets (keep existing targets working)
- `docker-build`, `docker-up` (`docker compose up -d --build --wait`, then echo the
  URLs), `docker-down`, `docker-clean` (`down -v --remove-orphans`), `docker-logs`,
  `docker-psql` (convenience), and:
- `docker-validate-rls`: run `db/validate_rls.sql` **as `sample_app`** inside the
  postgres container: `docker compose exec -e PGPASSWORD=sample_app_pw postgres
  psql -U sample_app -d sample_db -f /db/validate_rls.sql`.
- `docker-e2e`: BOTH legs — (a) host → localhost:
  `SERVER_URL=http://127.0.0.1:2024 uv run python e2e_auth.py`;
  (b) in-network: `docker compose run --rm e2e`.
- Update `.PHONY`.

### D9. Docs
- `README.md`: add a "Run with Docker" quick-start section (make docker-up; API at
  `http://127.0.0.1:2024`, health at `/health`; Postgres on `localhost:5433`; e2e via
  `make docker-e2e`; teardown/clean; pointer to `docs/docker.md`). Keep the local
  (non-docker) path documented. Update the stateless `/runs` curl example to the
  thread-based flow so it works on both runtimes.
- `docs/docker.md` (new): architecture (mermaid: client → langgraph(Aegra) container →
  postgres container; one-shot e2e container on the compose network); **why Aegra and
  not the official `langgraph-api` image** (custom-auth license gating in Self-Hosted
  Lite — cite docs.langchain.com deploy-standalone-server, langchain-ai/langgraph
  discussion #5391, issue #6709 — and no public postgres runtime); what Aegra gives us
  (Agent Protocol, Postgres persistence of threads/runs, no license); Redis is off
  (`REDIS_BROKER_ENABLED=false`, in-process runs; note when to add Redis); DB layout
  (one Postgres container, two databases: `sample_db` app data + RLS, `aegra` server
  state); env-var precedence (compose `environment:` > `env_file` > image); DB init
  flow (00 roles → 01 schema → 02 CSV load → 03 RLS → 04 aegra db; fresh-volume only;
  `make docker-clean` re-inits); troubleshooting (host 5432 taken by local PG17 ⇒ we
  publish 5433; OrbStack daemon; forcing rebuilds).
- `docs/authentication.md`: short subsection with the Docker variants of the demo
  commands (make docker-up, port 2024, thread-based curl, make docker-e2e). Update the
  inline curl examples to the thread-based flow. Do not rewrite the rest.
- `.env.example`: append docker notes (`POSTGRES_HOST_PORT`, `LANGGRAPH_HOST_PORT`
  optional overrides; DSNs/`DATABASE_URL` are set inside compose — values here are for
  local runs).

## Acceptance criteria — verify EACH yourself; all must pass before you declare done

1. Fresh stack: `make docker-clean && make docker-up` succeeds from scratch;
   `docker compose ps` shows postgres + langgraph healthy.
2. `curl -s http://127.0.0.1:2024/health` → healthy JSON (2xx).
3. Host e2e: `SERVER_URL=http://127.0.0.1:2024 uv run python e2e_auth.py` →
   `5 passed, 0 failed`, exit 0.
4. In-network e2e: `make docker-e2e` runs both legs; the in-network leg targets
   `http://langgraph:2024` and also prints `5 passed, 0 failed`.
5. `make docker-validate-rls` → all 11 checks PASS, zero FAIL lines.
6. Image hygiene: no `.env` in the image; secrets reach the process only via compose
   env. Spot-check: `docker compose exec langgraph sh -lc 'cat .env 2>/dev/null | head'`.
7. Persistence: create a thread via the API (with a valid token), `docker compose
   restart langgraph`, wait healthy, `GET /threads/{id}` still returns it (Aegra state
   survives restarts — that is the point of choosing Aegra; document it truthfully).
8. Local flow intact: `uv run pytest` passes (tests use the LOCAL Postgres on 5432 via
   `.env` — do not repoint `.env`), and `./run_e2e.sh` → `5 passed, 0 failed` against
   the local `langgraph dev` server.
9. `make lint` clean (ruff + flake8 + vulture on the changed files too).
10. Nothing binds host port 5432 (`lsof -nP -iTCP:5432 -sTCP:LISTEN` shows only the
    pre-existing local postgres, not docker).

## Constraints

- No git write operations of any kind.
- Keep diffs surgical: `e2e_auth.py` transport + `auth.py` signature may change as
  specified (D6/D7) with matching minimal test updates; existing
  `db/00_roles.sql`/`01_schema.sql`/`03_rls.sql`/`validate_rls.sql`, `run_e2e.sh`,
  agent/tools/prompts code must NOT change.
- Do not print secret values to logs or docs.
- Each e2e suite costs ~5 real OpenAI calls — run them to verify, don't loop needlessly.
- When Aegra behaves differently than this spec assumes (package names, migration
  step, auth invocation, response shapes), trust the installed Aegra source and its
  repo docs; note the deviation in the done report.

## Done report (print at the end)

- Files created/changed.
- The acceptance checklist with the actual (trimmed) command outputs.
- Any deviations from this spec, with reasons.
