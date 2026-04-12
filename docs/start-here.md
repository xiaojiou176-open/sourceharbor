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

If you prefer to install the public wrapper first, the packaged CLI now lives in
`packages/sourceharbor-cli` and delegates into this same repo-local substrate
when you run it inside a checkout:

```bash
npm install --global ./packages/sourceharbor-cli
sourceharbor help
```

## Before You Start

- If you want the **operator path**, stay on this page.
- If you want the **builder/distribution path**, jump to [builders.md](./builders.md) and [public-distribution.md](./public-distribution.md).
- If you want the **API image lane**, treat `ghcr.io/xiaojiou176-open/sourceharbor-api` as a separate builder surface, not the whole product stack.
- Do not treat `ghcr.io/xiaojiou176-open/sourceharbor-ci-standard` as the install story. That image is CI/devcontainer infrastructure.

## What You Should See By The End

- the web command center at the route recorded in `.runtime-cache/run/full-stack/resolved.env`
- the API health endpoint recorded in `.runtime-cache/run/full-stack/resolved.env`, with the canonical default local health URL remaining `http://127.0.0.1:9000/healthz` only when that port is still free
- at least one queued or completed processing job
- a digest feed entry or an inspectable job payload
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

- web command center: `http://127.0.0.1:${WEB_PORT}`
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
- if the snapshot and actual services disagree, run `./bin/full-stack down` and restart the clean path
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

### 5. Inspect the result surfaces

```bash
curl -sS "${SOURCE_HARBOR_API_BASE_URL}/api/v1/videos" | jq
curl -sS "${SOURCE_HARBOR_API_BASE_URL}/api/v1/feed/digests" | jq
curl -sS "${SOURCE_HARBOR_API_BASE_URL}/api/v1/jobs/<job-id>" | jq
curl -sS -X POST "${SOURCE_HARBOR_API_BASE_URL}/api/v1/retrieval/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"summary","top_k":5,"mode":"keyword"}' | jq
```

Open these UI views:

- `/` for the command center
- `/ops` for operator diagnostics and live-hardening gates
- `/subscriptions` for strong-supported video templates plus generalized RSSHub/RSS intake, now staged as a tracked-universe atlas and manual-intake workbench backed by the same template catalog contract that the API and MCP surfaces expose
- `/search` for grounded search across SourceHarbor artifacts
- `/ask` for the story-aware, briefing-backed Ask front door, with a server-owned story page payload over the answer/change/evidence view
- `/reader` for the published-doc frontstage: merged reader docs, singleton polish docs, navigation brief, yellow warning, and source contribution drawer
- `/feed` for the digest reading flow, with source identity cards, affiliation cues, and a direct bridge into the current reader edition whenever that digest already materialized into a published reader document
- `/jobs?job_id=<job-id>` for pipeline trace and artifacts
- `/watchlists` for long-lived tracking objects
- `/trends` for merged stories plus recent evidence runs
- `/briefings` for the summary-first watchlist briefing: current story, then changes, then evidence drill-down, with one canonical selected-story payload and Ask handoff owned by the server
- `/mcp` for the MCP front door and quickstart
- `/settings` for notifications and test sends

## Operator Path: Continuous Intake

If you want the longer-lived workflow instead of one-off processing:

1. Add one or more subscriptions in the web UI or via `POST /api/v1/subscriptions`
2. Use the built-in template split honestly:
   - strong-supported YouTube/Bilibili presets when you want the richer video lane
   - generalized RSSHub / generic RSS intake when the source universe widens
   - do not treat generalized intake as route-by-route RSSHub proof
3. Trigger `POST /api/v1/ingest/poll` to refresh the Track lane and update the pending pool
4. Keep the returned `run_id` so you can inspect `GET /api/v1/ingest/runs/<run-id>`
5. Trigger `POST /api/v1/ingest/consume` when you want the Consume lane to freeze one batch and process queued items
6. Trigger `POST /api/v1/reader/batches/<batch-id>/materialize` when you want the batch to become published reader docs immediately
7. Read the resulting documents in `/reader`
8. Inspect `/trends` when you want the merged-story view over repeated themes
9. Inspect `/briefings` when you want the lower-cognitive-load unified story view for one watchlist; the selected story and Ask handoff should now stay on the same server-owned story truth instead of parallel page aliases
10. Inspect the job page for retries, degradations, and artifact links

That path is what turns SourceHarbor from a one-shot processor into a knowledge intake system.

## Local-Only Dedicated Chrome Root

When a local browser flow genuinely depends on login state, SourceHarbor now
uses its own isolated Chrome root instead of borrowing your default Chrome user
data directory.

Think of it like moving from “sharing a desk in the public lobby” to “having one
dedicated studio for this repo”.

One-time bootstrap:

```bash
./bin/bootstrap-repo-chrome --json
```

That command copies only:

- the source `Local State`
- the source `sourceharbor` profile directory

into the repo-owned target:

- `${SOURCE_HARBOR_CHROME_USER_DATA_DIR}/Local State`
- `${SOURCE_HARBOR_CHROME_USER_DATA_DIR}/${SOURCE_HARBOR_CHROME_PROFILE_DIR}/`

After bootstrap, start exactly one repo-owned Chrome instance:

```bash
./bin/start-repo-chrome --json
./bin/open-repo-chrome-tabs --site-set login-strong-check --json
python3 scripts/runtime/resolve_chrome_profile.py --mode repo-runtime --json
```

From then on, local automation attaches to that single instance over CDP. It
does not second-launch Chrome against the same root.

If you want to reset the repo-owned Chrome session before a fresh manual login
check, use:

```bash
./bin/stop-repo-chrome --json
./bin/start-repo-chrome --json
./bin/open-repo-chrome-tabs --site-set login-strong-check --json
```

Hosted CI stays login-free on purpose:

- GitHub-hosted workflows must not consume `SOURCE_HARBOR_CHROME_*`
- login-dependent browser proof is local-only
- if a browser lane needs real login state, classify it as local proof instead of
  forcing it into hosted CI

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
- For the exhaustive program closeout matrix, read [2026-03-31-program-closeout-matrix.md](./blueprints/2026-03-31-program-closeout-matrix.md).
- Agent autopilot and hosted workspace directions remain spike artifacts, not current operator promises. See [reference/project-positioning.md](./reference/project-positioning.md) and the related files in [blueprints/](./blueprints/).

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
