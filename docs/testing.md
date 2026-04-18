# Testing

SourceHarbor uses layered verification.

Think of it like product evidence in layers:

1. **Fast checks** catch broken contracts and fake tests
2. **Doctor** classifies first-run blockers before you burn time on deeper smoke
3. **Core suites** verify Python surfaces and shared behavior
4. **Supervisor clean path** proves the repo-managed operator path locally
5. **Long live smoke** extends into secret and provider gates on purpose

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

What it proves:

- the stricter live lane can run after the local supervisor path is already healthy
- YouTube, Resend, and Gemini-backed checks are wired into a repeatable command
- provider-side gates stay explicit instead of being hand-waved as local repo truth

Important boundary:

- passing the supervisor clean path means the repo is locally runnable
- passing the long live-smoke lane requires additional provider and sender conditions
- failing the long live-smoke lane does **not** automatically mean the local bootstrap/up/status path is broken

## Local-Only Login Browser Lane

GitHub-hosted CI stays login-free.

If a browser flow genuinely depends on a real signed-in Chrome session, treat it
as a **local-only** proof lane instead of a hosted CI lane.

SourceHarbor now uses a dedicated isolated Chrome root:

- `SOURCE_HARBOR_CHROME_USER_DATA_DIR`
- single profile directory: `SOURCE_HARBOR_CHROME_PROFILE_DIR`
- single repo-owned Chrome instance
- CDP attach instead of `launch_persistent_context`

Bootstrap and start it with:

```bash
./bin/bootstrap-repo-chrome --json
./bin/start-repo-chrome --json
python3 scripts/runtime/resolve_chrome_profile.py --mode repo-runtime --json
bash scripts/ci/external_playwright_smoke.sh --browser chromium --real-profile --url https://example.com
```

Hosted workflows must not reference `SOURCE_HARBOR_CHROME_*` or try to reuse a
local persistent browser profile.

## Git Hooks

Install hooks with:

```bash
./bin/install-git-hooks
```

Pre-commit and pre-push should block:

- real regressions
- secret leaks
- broken public workflows

## PR-Facing Security And Dependency Checks

These checks now sit on the remote branch-protected pull-request path together
with `python-tests`, `web-lint`, and `pre-commit`. They still answer a
different question from the small local proof path above: they widen
GitHub-side supply-chain, workflow-safety, and secret-scanning coverage rather
than replacing the repo-managed local supervisor proof.

- `dependency-review.yml` inspects pull-request dependency changes
- `codeql.yml` runs code scanning on the tracked languages
- `zizmor.yml` lint-checks GitHub Actions workflow safety
- `trivy.yml` scans the repository filesystem and dependency manifests for high-severity issues
- `trufflehog.yml` scans pushed and pull-request Git history deltas for verified or unknown secrets

Those branch-protected checks are current remote required checks today, so this
page should not describe them as optional or merely advisory.

## External-Proof Workflow-Dispatch Lanes

These still stay outside the default pull-request gate:

- `build-public-api-image.yml`, `build-ci-standard-image.yml`, `release-evidence-attest.yml`, `publish-pypi.yml`, and `publish-mcp-registry.yml` stay in the external-proof lane, not the default pull-request gate
- those external lanes are `workflow_dispatch` only and run behind protected environments so ordinary pull requests never touch their secrets or publication paths
- `publish-pypi.yml` is the repo-side Trusted Publisher lane for the `sourceharbor` package and runs behind protected environment `external-pypi-publish`; its current blocker is the PyPI-side Trusted Publisher mismatch surfaced as `invalid-publisher`
- `publish-mcp-registry.yml` is the repo-side registry refresh lane for `io.github.xiaojiou176-open/sourceharbor-mcp` and runs behind protected environment `external-mcp-registry-publish`; its current first blocker is that live PyPI still serves `sourceharbor==0.1.14`, so the registry refresh refuses to proceed until PyPI reaches `0.1.19`
- all active GitHub workflows run on `ubuntu-latest`; local `repo-side-strict-ci`
  remains a repo-side proof command, not a self-hosted CI runner

Think of them like specialist inspectors after the core exam:

- the required path proves the repo is locally honest and rerunnable
- the branch-protected security and dependency checks widen GitHub-side
  supply-chain and secret coverage without changing the core local-proof contract
- the external lanes prove harder publication claims when you actually need them
- publication or attestation happens only after an owner deliberately opens that lane and approves the protected environment

## Manual Truth Audits And Closeout Lanes

These commands are the closer's toolkit, not the default newcomer path.

Use them when you need remote/public truth, current-proof receipts, or release
and provider evidence that go beyond the ordinary local and PR-facing lanes.

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

Reader-frontstage UI proof note:

- `python3 scripts/runtime/run_reader_clean_ui_audit.py` is the local
  reader-proof lane for current-head screenshot capture plus `/api/v1/ui-audit/run`.
- It captures a clean proof pack into system temp space, hides Next dev-only
  overlay noise from the screenshots, and writes a local `ui-audit-report.json`
  beside the captured images.
- If the full screenshot pack hits a Gemini provider timeout, the runner
  automatically retries with a smaller mini pack so the maintainer-local UI
  review lane can still produce a usable verdict.
- Treat it as a maintainer-local proof helper, not a hosted-distribution claim.

Frontstage UI proof note:

- `python3 scripts/runtime/run_frontstage_clean_ui_audit.py` is the broader
  public-surface lane for `/`, `/feed`, `/subscriptions`, and `/reader/demo`.
- It captures a clean frontstage proof pack into system temp space, hides
  dev-only overlay noise from the screenshots, and submits that pack to
  `/api/v1/ui-audit/run`.
- If the full pack hits a Gemini provider timeout, the runner automatically
  retries with a smaller mini pack so the public-surface audit can still return
  a usable verdict.
- Treat it as a maintainer-local proof helper for frontstage IA and UI quality,
  not as hosted-distribution proof.

Closeout note:

- `./bin/repo-side-strict-ci --mode pre-push` still prefers the repo-owned
  standard-env container path when Docker is healthy.
- If the Docker daemon is unavailable on a maintainer workstation, the wrapper
  now falls back to the host-bootstrapped pre-push quality gate instead of
  failing before the actual repo-side gates even start.
- That host fallback still enforces the same runtime contracts: env
  registration, documentation drift, scratch-space budget, and namespace-aware
  Temporal startup truth.

Mutation-readiness note:

- `repo-side-strict-ci` now prefers a fresh current-commit mutation stats
  artifact at `.runtime-cache/reports/mutation/mutmut-cicd-stats.json` when one
  already exists for the current HEAD.
- If that artifact is missing or stale, the mutation gate reruns
  `scripts/ci/run_mutmut.sh` and rewrites the report before evaluating the
  thresholds.
- The mutation report is expected to carry the real status split (`killed`,
  `survived`, `no_tests`, `timeout`, `not_checked`, `caught_by_type_check`) so
  a failed mutation lane points at an exact leaf instead of a blank
  `killed+survived=0` summary.

What this layer proves:

- the live remote required-check contract still matches the tracked docs
- remote code-scanning and secret-scanning alerts remain clean
- external-proof workflow-dispatch lanes still point at the current public truth
- current-proof, newcomer, and current-state receipts still match the current HEAD
- release/publication truth is being read as its own ledger instead of being mixed into the default local path
- reader route contracts, published-doc navigation surfaces, and public-sensitive wording can be audited without pretending hosted proof already exists

## Public-Proof Boundary

- Passing local checks means the repo is locally credible.
- It does **not** mean a hosted or remote distribution claim is automatically proven for the current `main`.

For the public evidence ladder, read [proof.md](./proof.md).
