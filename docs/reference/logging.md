# Logging Contract

SourceHarbor keeps runtime and governance logs under `.runtime-cache/logs/`.

## Required Vocabulary

- `run_id`: ties together one local or CI execution.
- `trace_id`: follows a request or command through the system.
- `request_id`: identifies a single API or task request.
- `upstream_contract_surface`: marks whether an upstream interaction is `public` or `internal`.

## Channel Layout

- app logs: `.runtime-cache/logs/app`
- component logs: `.runtime-cache/logs/components`
- local core-services fallback logs: `.runtime-cache/logs/local-core`
- test logs: `.runtime-cache/logs/tests`
- governance logs: `.runtime-cache/logs/governance`
- infra logs: `.runtime-cache/logs/infra`
- upstream logs: `.runtime-cache/logs/upstreams`

## Runtime Evidence Sidecars

- Runtime evidence written under `.runtime-cache/evidence/**` must carry a sibling `.meta.json` sidecar.
- The sidecar must include:
  - `artifact_path`
  - `created_at`
  - `source_entrypoint`
  - `source_run_id`
  - `verification_scope`
- Evidence-bearing run stores such as UI audit receipts must also register the artifact in `.runtime-cache/reports/evidence-index/<run_id>.json` so governance checks can trace the run without a later backfill pass.

## Failure Receipts

- Long-running helpers that start background services must emit a durable failure receipt before returning non-zero.
- For `full_stack` failures, `.runtime-cache/run/full-stack/last_failure_reason` is the SSOT failure marker.
- For local core-services fallback, Postgres and Temporal must keep their exact
  log files under `.runtime-cache/logs/local-core/` so background-service
  failures stay attributable to repo-owned runtime state instead of vanishing
  into the shell that launched them.
- If a worker/web/api rollback runs after a failed start or readiness gate, the rollback must remove the corresponding `*.pid` receipt instead of leaving stale process markers behind.

`repo-side-strict-ci` now has two honest log-bearing entry modes:

- standard-env container path when Docker is healthy
- host-bootstrapped pre-push quality gate when the Docker daemon itself is
  unavailable on a maintainer workstation

Both modes still write through the same strict-ci governance receipts instead of
creating a second undocumented logging lane.

Repo-managed `full_stack` startup also writes a temporary
`.runtime-cache/tmp/web-runtime/workspace/apps/web/.env.local` overlay for the
web runtime. Treat that file as local runtime state, not as public
documentation, and never commit it or copy it into outward-facing artifacts.

## Why This Exists

The goal is simple: when a run fails, operators should be able to trace it with receipts instead of guesswork.
