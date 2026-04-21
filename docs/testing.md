# Testing

SourceHarbor uses layered verification.

Think of it like product evidence in layers:

1. **Fast checks** catch broken contracts and fake tests
2. **Doctor** classifies first-run blockers before you burn time on deeper smoke
3. **Core suites** verify Python surfaces and shared behavior
4. **Supervisor clean path** proves the repo-managed operator path locally
5. **Long live smoke** extends into secret and provider gates on purpose

## Start With One Verification Path

| If you want to know... | Start here | What it answers |
| --- | --- | --- |
| **Can I trust the repo locally?** | `./bin/doctor`, `bash scripts/ci/python_tests.sh`, then `./bin/full-stack up` | environment, Python contracts, and the repo-managed operator path |
| **Can I trust a pull request?** | the GitHub required checks below | branch-protected merge truth for code, secrets, and workflow safety |
| **Can I trust public, release, or publish claims?** | the maintainer appendix later on this page | release/publication truth, external lanes, and closeout-grade audits |

## Five-Layer Verification Contract

Think of this like airport checkpoints:

- `pre-commit` is the quick bag scan
- `pre-push` is the fuller gate before you board
- `hosted` is the airline's own security lane on GitHub
- `nightly` is the background sweep that keeps stale risk from piling up
- `manual` is the specialist inspection for release, provider, browser, and public-proof truth

Do not force every heavy check into the default local path. Each layer answers a
different question.

| Layer | Default trigger | Primary entrypoints | What it proves |
| --- | --- | --- | --- |
| `pre-commit` | local edit / commit prep | fast local checks below + web lint | the fastest contributor-side contract stays honest before deeper proof |
| `pre-push` | contributor-side push gate | `.githooks/pre-push` | the default local parity hook stays deterministic and does not silently expand into a full closeout audit |
| `hosted` | GitHub `pull_request` / `push` | `ci.yml`, `pre-commit.yml`, `dependency-review.yml`, `codeql.yml` on PR/push, `trivy.yml`, `trufflehog.yml`, `zizmor.yml` | the branch-protected remote contract for pull requests and `main` |
| `nightly` | hosted `schedule` | `codeql.yml` on `schedule` | thin background security refresh; keep this lane small and do not create a separate weekly governance bucket |
| `manual` | human-triggered or operator-triggered | `./bin/repo-side-strict-ci --mode pre-push`, `./bin/quality-gate --mode pre-push`, `./bin/governance-audit --mode audit`, `./bin/smoke-full-stack --offline-fallback 0`, repo-owned real-profile browser proof, `build-public-api-image.yml`, `build-ci-standard-image.yml`, `release-evidence-attest.yml` | provider/browser/release/publication truth plus closeout-grade repo/public audits |

## Fast Local Checks

```bash
python3 scripts/governance/check_env_contract.py --strict
python3 scripts/governance/check_host_safety_contract.py
python3 scripts/governance/check_host_specific_path_references.py
python3 scripts/governance/check_test_assertions.py
python3 scripts/governance/check_route_contract_alignment.py
python3 scripts/governance/check_public_entrypoint_references.py
python3 scripts/governance/check_public_personal_email_references.py
python3 scripts/governance/check_public_sensitive_surface.py
python3 scripts/governance/check_local_private_ledger_migration.py
python3 scripts/governance/check_external_lane_contract.py
eval "$(bash scripts/ci/prepare_web_runtime.sh --shell-exports)"
( cd "$WEB_RUNTIME_WEB_DIR" && npm run lint )
python3 scripts/runtime/maintain_external_cache.py --json
```

## First-Run Doctor

```bash
./bin/doctor
```

What it tells you:

- env contract vs runtime blockers
- DB target and split-brain risk
- Temporal reachability
- API / worker / web readiness
- write-token and secret gates for live validation

What they cover:

- environment contract drift
- host-safety contract drift for broad kill and desktop-control primitives
- host-specific path and personal-email drift in tracked public text surfaces
- sensitive public wording drift for secret presence, operator-secret stories, and concrete home-cache/profile path details
- placebo test detection
- route and public-entrypoint contract drift
- local-private ledger migration drift
- external-lane contract drift
- web lint regressions

## Core Python Test Suite

```bash
bash scripts/ci/python_tests.sh
```

What it covers:

- API services and routers
- worker pipeline logic
- MCP tool contracts
- reader pipeline judge/materialize/repair flows plus reader route surfaces

## Supervisor Clean Path

```bash
./bin/bootstrap-full-stack
./bin/full-stack up
source .runtime-cache/run/full-stack/resolved.env
./bin/full-stack status
curl -sS "${SOURCE_HARBOR_API_BASE_URL}/healthz"
curl -I "http://127.0.0.1:${WEB_PORT}/ops"
```

What it proves:

- the repo-managed local stack can boot
- the runtime route snapshot matches the services you are actually talking to
- API, worker, and web are visible to the local supervisor
- the public quickstart story is grounded in runnable local commands

Important local-truth notes:

- do not assume `9000/3000`; bootstrap/full-stack may move to other free ports and record them in `.runtime-cache/run/full-stack/resolved.env`
- the default local Postgres path is container-first on `CORE_POSTGRES_PORT=15432`
- the repo-owned Temporal fallback keeps its SQLite state in
  `.runtime-cache/tmp/local-temporal/dev.sqlite`
- if your machine already has a host Postgres on `127.0.0.1:5432`, that is a different data plane from the core-services container path
- the repo-managed web runtime also writes `.runtime-cache/tmp/web-runtime/workspace/apps/web/.env.local` so browser-triggered writes keep the same local API base URL and write-session fallback as the supervisor path
- `CI=false` or similar non-truthy env strings must not suppress the maintainer-local `sourceharbor-local-dev-token` fallback during repo-managed full-stack startup
- `./bin/full-stack up` can now self-heal Temporal reachability by trying the
  repo-owned `core_services.sh up` path before failing worker startup
- Temporal preflight now verifies namespace readiness after TCP reachability, so
  an unhealthy reused listener on `7233` still fails closed
- if `127.0.0.1:7233` is already occupied by an unhealthy non-repo-owned
  listener, the local fallback must fail closed instead of reusing that port by
  presence alone
- `.runtime-cache/tmp` remains governed scratch space with a hard budget of
  `1024MB / 80000 files`; if repo-managed `web-runtime/` copies or screenshot
  batches exceed it, clean only rebuildable scratch paths before rerunning the
  closeout gates
- a current local `mode=full` YouTube receipt now depends on:
  - `gemini-3-flash-preview` as the fast-model default
  - Gemini Files waiting until `ACTIVE`
  - the repo-owned lightweight proxy-video path for oversized raw media

## Long Live Smoke Lane

```bash
./bin/smoke-full-stack --offline-fallback 0
```

When you specifically want the Bilibili hardening lane instead of the default
single-sample probe, run the curated canary matrix plus one manual-intake ->
reader boundary receipt:

```bash
./bin/smoke-full-stack \
  --offline-fallback 0 \
  --live-smoke-bilibili-canary-matrix config/runtime/bilibili-live-canary-matrix.json \
  --live-smoke-bilibili-canary-tier core \
  --live-smoke-bilibili-canary-limit 2 \
  --live-smoke-bilibili-reader-receipt-sample science-interview-short \
  --live-smoke-computer-use-skip 1 \
  --live-smoke-computer-use-skip-reason "repo-scoped bilibili current-head receipt"
```

What it proves:

- the stricter live lane can run after the local supervisor path is already healthy
- core video/retrieval/computer-use checks are wired into a repeatable command
- notification and sender-identity proof now stays an explicitly skippable sub-lane instead of collapsing the whole smoke run by default
- reader-stack verification is optional by default, because Miniflux/Nextflux is still a separate floor from the core stack unless you explicitly enable it
- provider-side gates stay explicit instead of being hand-waved as local repo truth
- the Bilibili canary path now has a repo-curated 5-10 sample matrix, adaptive
  ASR selection, and a current-head reader/public-boundary receipt path instead
  of relying on one static sample URL

Important boundary:

- passing the supervisor clean path means the repo is locally runnable
- passing the default long live-smoke lane proves the core product path; forcing the notification/provider lane still requires additional sender conditions
- forcing reader-stack verification still requires the reader stack to be enabled and reachable
- failing the long live-smoke lane does **not** automatically mean the local bootstrap/up/status path is broken
- if you specifically want notification/provider closure too, rerun with `--live-smoke-require-notification-lane 1`
- if you specifically want the reader stack checked too, rerun with `--require-reader 1`
- if you specifically want the Bilibili deep lane, use
  `--live-smoke-bilibili-canary-matrix ...` and inspect
  `.runtime-cache/reports/tests/e2e-live-smoke-result.json` for
  `bilibili_canary_matrix` plus `bilibili_reader_receipt`

Current Bilibili failure taxonomy for that diagnostics lane:

- `download_failure`
- `subtitle_missing`
- `asr_quality_insufficient`
- `comments_api_failed`
- `rsshub_route_drift`
- `login_state_missing`
- `risk_control_or_geo_restricted`

## Maintainer Appendix

Everything below this line is maintainer depth, not the newcomer verification
path.

### Local-only login browser lane

GitHub-hosted CI stays login-free. If a browser flow genuinely needs a signed-in
Chrome session, keep it local and repo-scoped:

```bash
./bin/bootstrap-repo-chrome --json
./bin/start-repo-chrome --json
python3 scripts/runtime/resolve_chrome_profile.py --mode repo-runtime --json
bash scripts/ci/external_playwright_smoke.sh --browser chromium --real-profile --url https://example.com
```

For the deeper browser/login runbook, read [runbook-local.md](./runbook-local.md).

### Git hooks

Install hooks with:

```bash
./bin/install-git-hooks
```

Pre-commit and pre-push should keep real regressions, secret leaks, and broken
public workflows out of ordinary pushes.

### PR-facing security and dependency checks

Remote required checks widen the proof surface beyond local boot:

- `dependency-review.yml`
- `codeql.yml`
- `zizmor.yml`
- `trivy.yml`
- `trufflehog.yml`

Treat them as part of the branch-protected pull-request contract, not as
optional extras.

### External-proof workflow-dispatch lanes

These stay outside the default pull-request gate:

- `build-public-api-image.yml`
- `build-ci-standard-image.yml`
- `release-evidence-attest.yml`
- `publish-pypi.yml`
- `publish-mcp-registry.yml`

They run behind protected environments because they prove harder publication or
distribution claims than the default local + PR lanes.

### Manual truth audits and closeout lanes

Use these only when you need remote/public truth, release/publication truth, or
closeout-grade evidence:

```bash
./bin/repo-side-strict-ci --mode pre-push
./bin/quality-gate --mode pre-push
./bin/governance-audit --mode audit
python3 scripts/runtime/run_reader_clean_ui_audit.py
python3 scripts/runtime/run_frontstage_clean_ui_audit.py
python3 scripts/governance/probe_remote_platform_truth.py
python3 scripts/governance/check_remote_required_checks.py
python3 scripts/governance/check_remote_security_alerts.py
python3 scripts/governance/probe_external_lane_workflows.py
python3 scripts/governance/check_current_proof_commit_alignment.py
python3 scripts/governance/render_newcomer_result_proof.py && python3 scripts/governance/check_newcomer_result_proof.py
python3 scripts/governance/render_current_state_summary.py && python3 scripts/governance/check_current_state_summary.py
```

These lanes prove:

- remote required checks and security alerts still match the docs
- external-proof workflows still point at the current public truth
- current-proof, newcomer, and current-state receipts still match the current HEAD
- UI/public-surface audits can run without pretending hosted proof already exists

## Public-Proof Boundary

- Passing local checks means the repo is locally credible.
- It does **not** mean a hosted or remote distribution claim is automatically proven for the current `main`.

For the public evidence ladder, read [proof.md](./proof.md).
