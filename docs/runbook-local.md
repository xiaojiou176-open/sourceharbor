# Local Runbook

This is the operator runbook for local proof, not a hosted deployment guide.

## What To Run First

1. Copy `.env.example` to `.env`.
2. Install dependencies with:

```bash
set -a
source .env
set +a
UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$SOURCE_HARBOR_CACHE_ROOT/project-venv}" \
  uv sync --frozen --extra dev --extra e2e
```

1. Run `./bin/doctor` to see env/runtime blockers before boot.
2. Boot the stack with `./bin/bootstrap-full-stack` and `./bin/full-stack up`.
3. Use [start-here.md](./start-here.md) to queue the first real job.

Keep the local boot topology honest:

- `./bin/bootstrap-full-stack` now treats the **core stack** and the **reader
  stack** separately.
- The core stack is Postgres + Temporal + API/Web/Worker, and it can use a
  repo-owned local Postgres/Temporal fallback under `.runtime-cache/` when
  Docker is unavailable but local `postgres` / `initdb` / `pg_ctl` /
  `temporal` binaries exist.
- `./bin/full-stack up` can now self-heal this same core layer: if worker
  preflight sees Temporal down, it first attempts the repo-owned
  `core_services.sh up` path before declaring the stack blocked.
- That fallback keeps Temporal state inside the repo-owned SQLite file
  `.runtime-cache/tmp/local-temporal/dev.sqlite` instead of silently borrowing
  a host-global state directory.
- Temporal truth is now two-step: the port must answer, and the namespace must
  be readable. A random unhealthy listener on `7233` does not count as a green
  local fallback.
- The reader stack is still a Docker-only optional lane. If you want it, rerun
  bootstrap with `--with-reader-stack 1` instead of assuming it is part of the
  default first-run contract.

## Where To Look When Something Feels Off

- API health: default is `http://127.0.0.1:9000/healthz` when that port stays free, but current local truth should always be read from `.runtime-cache/run/full-stack/resolved.env`
- Web command center: default is `http://127.0.0.1:3000` only when that port stays free; otherwise trust `.runtime-cache/run/full-stack/resolved.env`
- First-run diagnosis: `./bin/doctor`
- Supervisor view of what is actually running: `./bin/full-stack status`
- Operator diagnostics page: `/ops`
- Python gate: `bash scripts/ci/python_tests.sh`
- Structured full-stack logs: `.runtime-cache/logs/components/full-stack`
- Local core-services fallback logs: `.runtime-cache/logs/local-core`
- Local Temporal fallback SQLite state:
  `.runtime-cache/tmp/local-temporal/dev.sqlite`
- Generated evidence and reports: `.runtime-cache/reports`
- Canonical repo-side web runtime: `.runtime-cache/tmp/web-runtime/workspace/apps/web`
- Repo-managed web runtime env overlay: `.runtime-cache/tmp/web-runtime/workspace/apps/web/.env.local`

That temporary `.env.local` is intentional. It pins the local browser-facing
API base URL and the local write-session fallback into the repo-managed web
runtime so manual intake and other web writes keep working even when local env
profiles contain non-truthy strings like `CI=false`.

Current local video-first note:

- a fresh real YouTube `mode=full` run can now succeed again on the local stack
- the current repo-side path uses:
  - Gemini fast-model `gemini-3-flash-preview`
  - file-upload waiting until Gemini Files is `ACTIVE`
  - a lightweight proxy-video path for oversized raw downloads

- Canonical mutation stats receipt: `.runtime-cache/reports/mutation/mutmut-cicd-stats.json`
- Disk-space audit: `./bin/disk-space-audit`
- Disk-space audit report check: `./bin/disk-space-audit-check`
- Dry-run cleanup planning: `./bin/disk-space-cleanup --wave safe`
- Repo-side runtime maintenance: `./bin/runtime-cache-maintenance`
- External cache maintenance report: `python3 scripts/runtime/maintain_external_cache.py --json`
- Docker hygiene report: `python3 scripts/runtime/docker_hygiene.py --json`
- Legacy-path migration dry-run: `./bin/disk-space-legacy-migration --json`
- Legacy-path migration apply (canonical auto-mappings): `./bin/disk-space-legacy-migration --apply --yes --auto-mappings`
- Local-private ledger migration: `python3 scripts/governance/migrate_local_private_ledgers.py --json`
- Worktree status closure: `python3 scripts/governance/report_worktree_status.py`
  This report now fail-closes to `partial` when no authoritative local-private plan ledger exists yet, instead of exiting without a report.

Do not hand-delete `.runtime-cache/` when local verification expands the repo
footprint. Use `runtime-cache-maintenance` for repo-side maintenance, and use
`disk-space-cleanup --wave ...` only when you are intentionally running a
governed cleanup wave from
[reference/disk-space-governance.md](./reference/disk-space-governance.md).

Current scratch-space rule:

- `.runtime-cache/tmp` is budgeted at `1024MB / 80000 files`
- if repo-managed `web-runtime/`, screenshots, or ad-hoc debug folders push it
  over budget, stop the stack first and clean only rebuildable scratch paths,
  then rerun `./bin/runtime-cache-maintenance`

The two runtime-heavy local caches worth recognizing by name are:

- `.runtime-cache/tmp/web-runtime/` for the repo-managed Next.js workspace copy
- `.runtime-cache/tmp/local-temporal/` for repo-owned Temporal fallback state
- `.runtime-cache/reports/mutation/mutmut-cicd-stats.json` for the latest
  mutation-readiness receipt consumed by repo-side strict CI

If you want a clean local runtime reset before another verification pass, use
`./bin/full-stack down` first; that shutdown path now also attempts to tear down
repo-owned core services instead of leaving Postgres/Temporal residue behind.

If you create an ad-hoc mutation workspace such as `.runtime-cache/tmp/mutation-debug`,
delete it after the debugging turn ends so the `tmp/` budget does not fail-close
future governance runs.

Do not hand-delete the repo-owned external cache root resolved by
`SOURCE_HARBOR_CACHE_ROOT` either.

- `project-venv/` and `state/*.db` are protected runtime objects
- `workspace/`, `artifacts/`, `browser/`, and `tmp/` are governed by TTL,
  quiet-window, and budget rules
- duplicate `project-venv-*` directories are verify-first cleanup candidates,
  not random junk
- repo-scoped Docker hygiene inventories named volumes but keeps them
  verify-first/report-only, and only deletes local debug images after the quiet
  window clears and no repo-owned containers still point at them

## Local Browser Login State

If a local browser proof actually needs login state, SourceHarbor uses a
dedicated browser root instead of your default personal Chrome root:

```bash
./bin/bootstrap-repo-chrome --json
./bin/start-repo-chrome --json
./bin/open-repo-chrome-tabs --site-set login-strong-check --json
python3 scripts/runtime/resolve_chrome_profile.py --mode repo-runtime --json
```

The runtime model is now:

- isolated root: `SOURCE_HARBOR_CHROME_USER_DATA_DIR`
- single repo-owned profile: `SOURCE_HARBOR_CHROME_PROFILE_DIR`
- one real Chrome instance for this repo
- CDP attach for automation and manual reuse
- `./bin/stop-repo-chrome` stops only the repo-owned Chrome instance and keeps other repos' Chrome roots alone
- `./bin/open-repo-chrome-tabs --site-set login-strong-check` opens the current manual-login tab pack:
  - Google Account
  - YouTube
  - Bilibili account center
  - Resend login

Hosted CI stays login-free. Real-profile browser proof is a local-only lane.

When you intentionally keep browser proof sessions in local env files, treat
`BILIBILI_COOKIE`, `GITHUB_COOKIE`, `GOOGLE_COOKIE`, `RESEND_COOKIE`, and `YOUTUBE_COOKIE` as
maintainer-local, read-only proof helpers only. They are not public repo
contract requirements, and they must never be committed, synced to shared
stores, or echoed into runtime artifacts.

## Site Capability Ledger

Treat these as the current local-proof site roles, not as a promise that every
site should become a deep integration target.

| Site | Why it exists in the local runbook | Strongest layer today | Current gate | Verdict |
| --- | --- | --- | --- | --- |
| Google Account | proves repo-owned Chrome login persistence and restart sanity | DOM / page-state proof | local login state when you intentionally run real-profile checks | **already-covered** |
| YouTube | proves the strongest current source + browser proof lane | hybrid: Data API + DOM / page-state proof | shared operator key persistence plus local login state when strict live proof is reopened | **already-covered** |
| Bilibili account center | proves whether the repo-owned profile still has the Bilibili account session needed for stronger local checks | URL / page-state proof today, hybrid later only if account-side automation becomes worth the maintenance cost | human login in the repo-owned profile; `open-repo-chrome-tabs --site-set login-strong-check --json` now classifies redirect-vs-account-home state for the repo-owned browser | **external-blocked** |
| Resend dashboard | proves notification/admin readiness and sender-chain follow-through, not source ingestion | admin UI + provider configuration | human login plus `RESEND_FROM_EMAIL` / sender-domain setup | **external-blocked** |
| RSSHub / RSS sources | source-universe intake coverage lives here, not in browser proof | HTTP / API | source availability and route/feed correctness | **already-covered** |

Do not treat Google Account or Resend as future ingestion targets just because
they are part of the login-check tab set. They are operator proof surfaces.

If you want the longer-lived "what can still be deepened safely" map, read
[site-capability.md](./site-capability.md).

## Quick Diagnosis Loop

1. Re-run the smallest failing command.
2. Check `.runtime-cache/logs/` for the matching component log.
3. Inspect `/api/v1/jobs/<job-id>` or `/api/v1/feed/digests` if the issue is inside a pipeline run.
4. Use [proof.md](./proof.md) to keep local proof separate from remote proof claims.
5. Use [runtime-truth.md](./runtime-truth.md) when Postgres, SQLite, artifacts, and release truth start sounding like one mixed story.
6. Treat `./bin/smoke-full-stack --offline-fallback 0` as the long live-smoke lane, not as the same thing as the local supervisor proof.

When you need the strict repo-side closeout gate from a maintainer workstation,
`./bin/repo-side-strict-ci --mode pre-push` still prefers the standard-env
container path, but it can now fall back to the host-bootstrapped pre-push
quality gate when Docker itself is the only missing layer.

## Boundaries

- Local success means the repo is inspectable and rerunnable on your machine.
- Local success does not automatically prove remote release, hosted availability, or third-party uptime.

For the disk-space map, safe cleanup boundary, and legacy-path migration rules, read [reference/disk-space-governance.md](./reference/disk-space-governance.md).
