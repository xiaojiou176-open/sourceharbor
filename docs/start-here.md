# Start Here

This is the shortest truthful path from clone to visible product value.

If you only want a fast fit check first, go to [see-it-fast.md](./see-it-fast.md).
This page is the **operator boot path**: boot the stack, run one real job,
inspect the result, then stop.

If you want one discoverable repo-local command surface before you memorize
individual entrypoints, start here:

```bash
./bin/sourceharbor help
```

That helper stays intentionally thin. The direct `bin/*` commands below remain
the underlying truth.

## Pick Your Path

- **Fast fit check first:** [see-it-fast.md](./see-it-fast.md)
- **One real local result:** stay on this page
- **Deep operator runbook:** [runbook-local.md](./runbook-local.md)
- **Builder or distribution path:** [builders.md](./builders.md) + [public-distribution.md](./public-distribution.md)

If you specifically want the packaged public wrapper instead of the operator
path, install it after you understand the repo-local flow:

```bash
npm install --global ./packages/sourceharbor-cli
sourceharbor help
```

## What You Should See By The End

- the web reader surfaces at the route recorded in `.runtime-cache/run/full-stack/resolved.env`
- the API health endpoint recorded in `.runtime-cache/run/full-stack/resolved.env`, with the canonical default local health URL remaining `http://127.0.0.1:9000/healthz` only when that port is still free
- at least one queued or completed processing job
- a timeline entry or an inspectable job payload
- at least one published reader document or a truthful “no reader documents yet” frontstage at `/reader`
- a local supervisor check you can rerun before you decide whether to open the long live-smoke lane

## Run Locally: Fastest Result Path

### 1. Install dependencies

```bash
./bin/sourceharbor help
cp .env.example .env
set -a
source .env
set +a
UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$SOURCE_HARBOR_CACHE_ROOT/project-venv}" \
  uv sync --frozen --extra dev --extra e2e
bash scripts/ci/prepare_web_runtime.sh >/dev/null
```

That last command refreshes the repo-managed web runtime workspace under
`.runtime-cache/tmp/web-runtime/workspace/apps/web`. The local web app and the
repo-side quality gates both read from that same runtime copy instead of
building ad-hoc node state in the repo root.

The default local database path is container-first:

- `CORE_POSTGRES_PORT=15432`
- `DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:${CORE_POSTGRES_PORT}/sourceharbor`

This avoids a silent split-brain when your machine already has a host Postgres
on `127.0.0.1:5432`.

### 2. Bootstrap the local stack

```bash
./bin/bootstrap-full-stack
./bin/full-stack up
source .runtime-cache/run/full-stack/resolved.env
```

`./bin/bootstrap-full-stack` now treats the **core stack** and the **reader
stack** as two different floors in the building:

- Postgres + Temporal are the core stack. The helper still prefers Docker
  compose first, but it can now fall back to repo-owned local services under
  `.runtime-cache/` when Docker is unavailable and local `postgres` /
  `initdb` / `pg_ctl` / `temporal` binaries exist.
- Miniflux + Nextflux stay a Docker-only optional reader stack. They no longer
  block the base first-run path by default.

One more current truth detail matters now:

- `./bin/full-stack up` can self-heal the core stack when Temporal is down.
  If worker preflight sees `127.0.0.1:7233` unreachable, it now attempts the
  repo-owned `core_services.sh up` path before failing the whole local startup.

If you explicitly want the reader stack too, opt in on purpose:

```bash
./bin/bootstrap-full-stack --with-reader-stack 1 --reader-env-file env/profiles/reader.local.env
```

Equivalent thin-facade path:

```bash
./bin/sourceharbor bootstrap
./bin/sourceharbor full-stack up
```

Equivalent packaged-CLI path from inside the checkout:

```bash
sourceharbor bootstrap
sourceharbor full-stack up
```

Open:

- web reader surfaces: `http://127.0.0.1:${WEB_PORT}`
- API health: `${SOURCE_HARBOR_API_BASE_URL}/healthz`
- canonical local fallback before any port re-home: `http://127.0.0.1:9000/healthz`

If anything feels off before you continue, run:

```bash
./bin/doctor
```

Or through the thin facade:

```bash
./bin/sourceharbor doctor
```

Why source the runtime snapshot:

- bootstrap/full-stack may move off `9000/3000` when those ports are already occupied
- the snapshot is the repo-managed local truth for API/Web routes
- if the snapshot and actual services disagree, run `./bin/full-stack down` and restart the clean path; that teardown now also attempts to stop repo-owned core services before the next clean boot
- the snapshot records the real core-services route truth even when the helper had to leave Docker and use repo-owned local Postgres/Temporal instead

### 3. Set the local write token

Direct write endpoints require a local write token.

For local development, use:

```bash
export SOURCE_HARBOR_API_KEY="${SOURCE_HARBOR_API_KEY:-sourceharbor-local-dev-token}"
```

If you start the API outside the repo-managed `./bin/full-stack up` path, also
export:

```bash
export WEB_ACTION_SESSION_TOKEN="${WEB_ACTION_SESSION_TOKEN:-$SOURCE_HARBOR_API_KEY}"
```

That keeps direct write calls and web server actions on the same local token
contract instead of creating a false auth blocker.

If you stay on the repo-managed `./bin/full-stack up` path, the temporary web
runtime now writes its own `.env.local` under
`.runtime-cache/tmp/web-runtime/workspace/apps/web/` with the resolved
`NEXT_PUBLIC_API_BASE_URL` and the same local write-session fallback. That is
how browser-triggered writes such as manual intake stay aligned with the API
health route even when local env profiles carry `CI=false` style flags.

### 4. Queue a first video job

Replace the sample URL with any public YouTube or Bilibili URL you can access:

```bash
curl -sS -X POST "${SOURCE_HARBOR_API_BASE_URL}/api/v1/videos/process" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${SOURCE_HARBOR_API_KEY}" \
  -d '{
    "video": {
      "platform": "youtube",
      "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    },
    "mode": "full"
  }'
```

What this gives you:

- a `job_id`
- a pipeline run you can inspect
- a future digest or artifact trail tied to that job

Current maintainer-local truth for this lane:

- a fresh local `mode=full` YouTube run can now complete end-to-end again
- the repo had to harden three things to get there:
  - `full-stack up` Temporal self-heal
  - current Gemini fast-model default (`gemini-3-flash-preview`)
  - Gemini file upload waiting plus a lightweight proxy-video path so giant raw
    `.webm` inputs do not stall forever in `FileState.PROCESSING`

### 5. Inspect the result surfaces

```bash
curl -sS "${SOURCE_HARBOR_API_BASE_URL}/api/v1/videos" | jq
curl -sS "${SOURCE_HARBOR_API_BASE_URL}/api/v1/feed/digests" | jq
curl -sS "${SOURCE_HARBOR_API_BASE_URL}/api/v1/jobs/<job-id>" | jq
curl -sS -X POST "${SOURCE_HARBOR_API_BASE_URL}/api/v1/retrieval/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"summary","top_k":5,"mode":"keyword"}' | jq
```

## After Your First Result

Use these off-ramps instead of keeping every deep operator detail on this page:

- **Keep operating SourceHarbor:** `/subscriptions`, `/feed`, `/reader`, `/search`, `/ask`, `/briefings`, `/watchlists`, `/trends`, and `/jobs?job_id=<job-id>`
- **Go from one-off processing to continuous intake:** [runbook-local.md](./runbook-local.md)
- **Verify more than the newcomer path:** [testing.md](./testing.md)
- **Debug runtime truth or local browser/login proof:** [runtime-truth.md](./runtime-truth.md) and [runbook-local.md](./runbook-local.md)
- **Check release vs remote vs distribution truth:** [project-status.md](./project-status.md), [proof.md](./proof.md), and [public-distribution.md](./public-distribution.md)

## Minimum Verification

These are the smallest checks that support the local supervisor story:

```bash
source .runtime-cache/run/full-stack/resolved.env
./bin/full-stack status
curl -sS "${SOURCE_HARBOR_API_BASE_URL}/healthz"
curl -I "http://127.0.0.1:${WEB_PORT}/ops"
python3 scripts/governance/check_env_contract.py --strict
python3 scripts/governance/check_host_safety_contract.py
python3 scripts/governance/check_test_assertions.py
./bin/doctor
eval "$(bash scripts/ci/prepare_web_runtime.sh --shell-exports)"
( cd "$WEB_RUNTIME_WEB_DIR" && npm run lint )
```

That list now also includes a host-safety fence:

- `check_host_safety_contract.py` blocks broad host-control primitives such as `pkill`, `killall`, shell `kill -9`, and desktop-global AppleScript paths.
- exact child-process teardown is still allowed when the code that spawned the child still owns the live handle.

## Optional Long Live Smoke Lane

When you intentionally want the stricter live lane, run:

```bash
./bin/smoke-full-stack --offline-fallback 0
```

That command is not the same thing as the local supervisor proof above. It
continues into external provider checks and can still stop on current
YouTube/Resend/Gemini-side gates even after `bootstrap -> up -> status ->
doctor` is already healthy.

## Boundaries

- This repository is **inspectable and runnable locally**, but not marketed as a turnkey hosted product.
- The repo is **not** one single public skill package; starter packs and plugin-grade bundles are only the builder-facing adoption layer.
- Local proof is different from remote release proof.
- Public screenshots and diagrams are presentation assets, not a substitute for live verification.
- For the shortest delivered-vs-bet summary, read [project-status.md](./project-status.md).
- Agent autopilot and hosted workspace directions remain future-direction topics, not current operator promises. See [reference/project-positioning.md](./reference/project-positioning.md).

## Public Trust Links

- Contribution path: [CONTRIBUTING.md](../CONTRIBUTING.md)
- Support path: [SUPPORT.md](../SUPPORT.md)
- Security path: [SECURITY.md](../SECURITY.md)
- Code of conduct: [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md)
- Code owners: [.github/CODEOWNERS](../.github/CODEOWNERS)
- Third-party notices: [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)
- Rights and provenance: [docs/reference/public-rights-and-provenance.md](./reference/public-rights-and-provenance.md)
- Public asset provenance: [docs/reference/public-assets-provenance.md](./reference/public-assets-provenance.md)
- Privacy and data boundary: [docs/reference/public-privacy-and-data-boundary.md](./reference/public-privacy-and-data-boundary.md)
- Public artifact exposure: [docs/reference/public-artifact-exposure.md](./reference/public-artifact-exposure.md)

For the explicit evidence ladder, go to [proof.md](./proof.md).
For the storage/runtime truth split, read [runtime-truth.md](./runtime-truth.md).
For the full local operator and browser/login runbook, read
[runbook-local.md](./runbook-local.md).
