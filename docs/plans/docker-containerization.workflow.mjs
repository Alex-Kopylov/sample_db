export const meta = {
  name: 'dockerize-langgraph',
  description: 'Codex implements Docker spec (Aegra server + Postgres); verify e2e from host + inside docker; adversarial review',
  whenToUse: 'Containerize the LangGraph app (Aegra runtime) + Postgres per docs/plans/docker-containerization-spec.md',
  phases: [
    { title: 'Implement', detail: 'codex gpt-5.5 xhigh executes the spec, monitored to completion (fix rounds resume the same codex session)' },
    { title: 'Verify', detail: 'clean stand-up, then parallel: host e2e, in-network e2e, RLS validation, Makefile/docs audit' },
    { title: 'Review', detail: 'adversarial review of the working-tree diff' },
  ],
}

const ROOT = (args && args.root) || '/Users/jhonsmith/sample_db/.claude/worktrees/nice-napier-690f51'
const SPEC = ROOT + '/docs/plans/docker-containerization-spec.md'
const LOG = '/tmp/codex_dockerize.log'
const ERR = '/tmp/codex_dockerize.err'

const VERDICT = {
  type: 'object',
  required: ['ok', 'summary'],
  properties: {
    ok: { type: 'boolean' },
    summary: { type: 'string' },
    failures: { type: 'array', items: { type: 'string' } },
  },
}

const MONITOR_RULES = `
Rules for running Codex CLI:
- Every Bash call that touches codex, docker, uv, or the network MUST set dangerouslyDisableSandbox=true
  (codex inherits this session's sandbox; without it codex cannot reach docker/localhost).
- Write the codex prompt to a temp file first, then launch codex in the BACKGROUND with stdin closed:
  nohup ... </dev/null >${LOG} 2>${ERR} &
- Poll roughly every 60s (sleep 60; tail -5 ${LOG}; kill -0 <pid>) until it exits. Hard cap 50 minutes;
  on timeout report the log tail and stop.
- You only dispatch and monitor — do NOT edit project files yourself, do NOT run any git write command
  (commit/branch/merge/stash). When codex exits, report: exit status, a summary of the last ~50 log lines,
  and the output of: git -C ${ROOT} status --short
Return plain text: what codex did, whether it claims all acceptance criteria pass, and the changed-file list.`

phase('Implement')
const impl = await agent(
  `Dispatch the Docker containerization implementation to Codex CLI in ${ROOT}.

Step 1 — write /tmp/codex_prompt.txt with exactly this content:
/goal Implement the spec at ${SPEC} exactly. Read it fully first, then do the Prep steps, then the Deliverables, then verify EVERY acceptance criterion yourself and print the Done report. Work only inside ${ROOT}. Never run git commit/branch/merge/stash.

Step 2 — launch (single line, background):
cd ${ROOT} && nohup codex exec --skip-git-repo-check -m gpt-5.5 --config model_reasoning_effort="xhigh" --sandbox danger-full-access --full-auto -C ${ROOT} "$(cat /tmp/codex_prompt.txt)" </dev/null >${LOG} 2>${ERR} & echo PID=$!
${MONITOR_RULES}`,
  { label: 'codex-implement' },
)

let verification = []
for (let attempt = 0; attempt <= 2; attempt++) {
  const standup = await agent(
    `Bring the docker stack up from the CURRENT working tree in ${ROOT}. Use Bash dangerouslyDisableSandbox=true for all docker/network commands.
Steps: docker version (if the daemon is down: open -a OrbStack and wait up to 90s). Then from ${ROOT}:
make docker-clean (ignore failure if target missing — then docker compose down -v --remove-orphans), then make docker-up (fallback: docker compose up -d --build --wait). Fresh volume matters: the DB init scripts must be exercised.
Verify: curl -s http://127.0.0.1:2024/health returns a healthy 2xx JSON (the server is Aegra; /health, /ready, /live exist) and docker compose ps shows the postgres and langgraph services healthy.
ok=true ONLY if the stack is fully up. List concrete failures otherwise (build errors, unhealthy service, port conflicts).`,
    { label: 'stand-up', phase: 'Verify', schema: VERDICT },
  )

  if (!standup || !standup.ok) {
    verification = [standup || { ok: false, summary: 'stand-up agent died', failures: ['stand-up agent returned null'] }]
  } else {
    verification = await parallel([
      () => agent(
        `E2E leg 1 — from the HOST against localhost. In ${ROOT} (dangerouslyDisableSandbox=true for network/uv):
If .venv is missing run: uv sync. Then run: SERVER_URL=http://127.0.0.1:2024 uv run python e2e_auth.py
ok=true ONLY if it prints "5 passed, 0 failed" and exits 0. Put the PASS/FAIL lines in summary.`,
        { label: 'e2e-host', phase: 'Verify', schema: VERDICT },
      ),
      () => agent(
        `E2E leg 2 — from INSIDE the docker network (container-to-container). In ${ROOT} (dangerouslyDisableSandbox=true):
Run the in-network e2e the Makefile provides (expected: the in-network part of make docker-e2e, i.e. docker compose run --rm e2e).
It must target http://langgraph:2024 via compose-network DNS — verify SERVER_URL in docker compose config — NOT host localhost.
ok=true ONLY on "5 passed, 0 failed". Put the PASS/FAIL lines in summary.`,
        { label: 'e2e-in-docker', phase: 'Verify', schema: VERDICT },
      ),
      () => agent(
        `RLS validation inside the postgres container. In ${ROOT} (dangerouslyDisableSandbox=true):
Run make docker-validate-rls (fallback: docker compose exec -e PGPASSWORD=sample_app_pw postgres psql -U sample_app -d sample_db -f /db/validate_rls.sql).
ok=true ONLY if every check PASSes (expected 11/11) with zero FAIL lines. Include the tally in summary.`,
        { label: 'rls-validate', phase: 'Verify', schema: VERDICT },
      ),
      () => agent(
        `Docs & Makefile audit (read-only; no docker needed). In ${ROOT}: read README.md, docs/docker.md, docs/authentication.md, Makefile, docker-compose.yml, Dockerfile, .dockerignore, .env.example, docker/.
Check: every documented command exists in the Makefile and matches compose reality; ports documented correctly (API 2024, postgres host 5433 by default, nothing binds host 5432); .dockerignore excludes .env; no secret VALUES appear in any tracked file; the local non-docker flow (make run / make test / run_e2e.sh) is still documented and unchanged; README has a Docker quick-start and its curl examples use the thread-based flow (POST /threads then /threads/{id}/runs/wait — Aegra has no stateless /runs/wait); docs/docker.md explains WHY Aegra is used instead of the official langgraph-api image (enterprise license gating of custom auth), the two-databases-in-one-container layout (sample_db + aegra), and that Redis is disabled (in-process runs).
ok=false with concrete failures for any mismatch.`,
        { label: 'docs-audit', phase: 'Verify', schema: VERDICT },
      ),
    ])
  }

  const failed = verification.filter(Boolean).filter((r) => !r.ok)
  if (failed.length === 0) { log('Verification: all green'); break }
  if (attempt === 2) { log('Verification still failing after 2 fix rounds — surfacing to main session'); break }

  log('Verification failures: ' + failed.length + ' — resuming codex for fix round ' + (attempt + 1))
  const failureReport = failed
    .map((f) => '- ' + f.summary + (f.failures && f.failures.length ? ' :: ' + f.failures.join('; ') : ''))
    .join('\n')
  await agent(
    `Resume the SAME codex session to fix verification failures. In ${ROOT}:

Step 1 — write /tmp/codex_fix.txt with:
This is the orchestrator following up. Independent verification of your implementation found these failures:
${failureReport}
Fix them in ${ROOT} (spec: ${SPEC}), re-verify the affected acceptance criteria yourself, and print an updated done report. Never run git commit/branch/merge/stash.

Step 2 — launch (background, resume inherits model/effort/sandbox; no config flags allowed):
cd ${ROOT} && nohup sh -c 'cat /tmp/codex_fix.txt | codex exec --skip-git-repo-check resume --last' </dev/null >${LOG} 2>${ERR} & echo PID=$!
${MONITOR_RULES}`,
    { label: 'codex-fix-' + (attempt + 1), phase: 'Implement' },
  )
}

phase('Review')
const review = await agent(
  `Adversarial review of the working-tree changes in ${ROOT} (git diff + untracked files from git status --short; read every new file fully).
Hunt for: (1) secrets or .env content leaking into the image, compose file, or docs; (2) compose correctness — healthcheck commands actually exist in the images used, depends_on conditions, volume init ordering (00 roles → 01 schema → 02 CSV load → 03 RLS → 04 aegra db), e2e service profile, restart semantics; (3) Dockerfile issues — .env baked in, broken layer caching, healthcheck tooling absent in slim image, Aegra server started without its DB migrations; (4) Makefile bugs — quoting, .PHONY, targets that diverge from docs; (5) port collisions with the local Postgres on host 5432; (6) auth regressions — the adapted auth handler (headers-based) must preserve the exact 401 behaviors and still work under local langgraph dev; e2e_auth.py transport change must not weaken any assertion (5 checks intact); (7) docs that overstate or misstate persistence (threads/runs persist in the aegra database; sample_db stays read-only for the agent).
Severity-tag each finding. ok=true only if there are no high-severity findings.`,
  { label: 'diff-review', schema: VERDICT },
)

return { implementation: impl, verification, review }
