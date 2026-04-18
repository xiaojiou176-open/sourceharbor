# Runtime Truth Map

SourceHarbor has multiple truth layers on purpose.

Think of them like different ledgers in the same business:

- Postgres is the business ledger
- SQLite is the step-by-step black box
- artifacts are the human-readable result shelf
- docs are the public map
- live remote proof is the release/public-distribution layer

If you mix those layers together, you start saying things that sound confident but are actually wrong.

## Storage Truth

| Layer | What it is for | What it is not |
| --- | --- | --- |
| **Postgres** | business truth for subscriptions, videos, jobs, ingest runs, knowledge cards, notification deliveries | not the step-by-step execution trace |
| **SQLite** | runtime trace truth for step runs, retries, and local step-level execution details | not the source of business-facing job identity |
| **Artifacts** | human-readable result truth: digest, transcript, outline, knowledge cards, and related files | not the authoritative queue or delivery state |

## Runtime Truth

For local operation, the most important runtime truth file is:

```text
.runtime-cache/run/full-stack/resolved.env
```

That file tells you:

- which API port was actually chosen
- which web port was actually chosen
- which `DATABASE_URL` the managed stack resolved to
- which Temporal queue the worker is actually polling

Use it like a boarding pass, not like a comment in old code. If your terminal, docs, and running services disagree, the resolved runtime snapshot wins for local route truth.

Current cache/state contract:

- repo-side runtime state belongs under `.runtime-cache/`
- repo-owned external cache and persistent state belong under `SOURCE_HARBOR_CACHE_ROOT`
- the legacy home-level `.sourceharbor/` root is now only a migration input, not the canonical runtime target
- repo-owned browser state now uses the path resolved by `SOURCE_HARBOR_CHROME_USER_DATA_DIR`
- local login-dependent browser automation must attach to the repo-owned Chrome instance over CDP instead of second-launching a persistent Chrome context
- shared tool caches such as `~/.cache/uv` and `~/Library/Caches/ms-playwright` are separate shared-layer objects, not repo-exclusive state

## Local Proof vs Remote Proof

| Layer | Safe claim |
| --- | --- |
| **Docs truth** | \"This is how the repo is intended to be run and interpreted.\" |
| **Local runtime truth** | \"This is what the current machine and current stack actually resolved to.\" |
| **Remote proof truth** | \"This is what current `main`, current releases, and live GitHub/distribution surfaces can prove externally.\" |

Do not swap these claims:

- local boot success does **not** prove hosted production readiness
- old releases do **not** prove current `main`
- a screenshot does **not** prove current runtime
- an archive plan does **not** replace current docs truth

## First-Run Truth

The clean local first-run path is:

1. `./bin/doctor`
2. `./bin/bootstrap-full-stack`
3. `./bin/full-stack up`
4. `source .runtime-cache/run/full-stack/resolved.env`
5. `./bin/full-stack status`
6. optional: `./bin/smoke-full-stack --offline-fallback 0`

The long smoke command is stricter than the base first-run path.

It intentionally steps into provider-backed lanes after the local supervisor
path is already up. Treat it like an extended flight check, not like the same
thing as `doctor + up + status`.

One current truth detail matters:

- default `smoke-full-stack` proves the core live product path first
- notification sender identity is a separate external sub-lane
- reader-stack verification is opt-in by default, because Miniflux/Nextflux still stays outside the base core-stack contract
- if you want the smoke run to fail-close on notification readiness too, pass
  `--live-smoke-require-notification-lane 1`
- if you want the smoke run to require the reader stack too, pass `--require-reader 1`

One important split now stays explicit:

- **core stack truth** = Postgres + Temporal + API/Web/Worker reachability
- **reader stack truth** = Miniflux + Nextflux adjunct services

`./bin/bootstrap-full-stack` now keeps those two ledgers separate. It can use a
repo-owned local fallback for the core stack when Docker is unavailable but the
local `postgres` / `initdb` / `pg_ctl` / `temporal` binaries exist. The reader
stack still stays an explicit Docker-only optional lane, so it should not be
treated as a first-run blocker unless you intentionally enabled
`--with-reader-stack 1`.

`./bin/full-stack up` now also has one repo-owned self-heal step:

- if worker preflight sees `TEMPORAL_TARGET_HOST` unreachable, it first tries
  the repo-owned `core_services.sh up` path before declaring the stack blocked
- this is still local operator truth, not hosted/SLO truth, but it removes one
  of the old false negatives where Postgres/Temporal were simply not lifted
  before worker startup

What `./bin/doctor` is for:

- env contract readiness
- DB target and split-brain risk
- Temporal reachability
- API / worker / web readiness
- write-token and secret gates

What `./bin/doctor` is **not** for:

- proving external release health
- replacing full smoke
- pretending missing secrets are implementation bugs

Current video-first local truth:

- a fresh maintainer-local `mode=full` YouTube job can now complete again
- that receipt currently depends on:
  - current Gemini fast-model naming (`gemini-3-flash-preview`)
  - upload-time waiting until Gemini Files leaves `PROCESSING`
  - a lightweight proxy-video path so oversized raw `.webm` media does not
    stall the primary video lane forever
- this should still be described as **local runtime truth** rather than public
  hosted proof

What local browser login state is for:

- local-only browser proof when a flow genuinely depends on a real signed-in Chrome session
- DOM / network / console inspection that must reuse the maintainer's real Chrome profile

What it is **not** for:

- GitHub-hosted CI
- default Playwright E2E
- silently falling back to Playwright's bundled Chromium when login state is required

## Live Hardening Truth

Wave 2 keeps five capabilities honest:

| Capability | Honest status rule |
| --- | --- |
| **Retrieval** | implemented, but quality is not proven until the current DB has non-empty corpus and artifact bindings |
| **Notifications / Reports** | implemented, but live send is still blocked until sender configuration is complete; `RESEND_API_KEY` alone is not enough without `RESEND_FROM_EMAIL` and a verified sender/domain |
| **UI audit** | base audit can run with valid `job_id` or `artifact_root`; Gemini review now has a recent maintainer-local proof pass, but other environments still need Gemini access if they want that extra layer |
| **Computer use** | implemented contract exists and a recent maintainer-local proof pass can reach the provider, but real runs still depend on Gemini access plus a valid screenshot/input contract |
| **Long live smoke** | the strict smoke lane is real, the short repo-managed smoke path now passes again, and YouTube provider validation removed the stale-key `403` story as the main blocker; the remaining end-to-end stop is reopening the lane with operator-managed API access plus complete sender configuration |

## What You Can Say Publicly

These are safe:

- SourceHarbor is source-first and proof-first
- local routes may differ from 9000/3000 and should be read from `resolved.env`
- Postgres, SQLite, and artifacts serve different truth roles
- Reader, Search, Ask, MCP, and ops surfaces point at the same pipeline

These need stronger proof:

- latest release and current `main` may line up again for a while, but
  docs/governance closeout commits can still move `main` ahead before the next
  tag is cut
- external notification delivery is validated
- computer use is live-ready
- semantic retrieval quality is proven

## Read Next

- [start-here.md](./start-here.md)
- [testing.md](./testing.md)
- [proof.md](./proof.md)
- [runbook-local.md](./runbook-local.md)
