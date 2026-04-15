# Public Proof

SourceHarbor should not rely on vibes, adjectives, or hidden test folders to justify its public story.

This page defines the public proof ladder.

It is the evidence map for human readers. It is not a machine-rendered current verdict page, and it should not be read as a substitute for commit-sensitive runtime reports.

## Public truth ledgers

Public proof stays on three separate ledgers: release evidence, remote `main` receipts, and external distribution proofs. Each claim below points to the ledger it represents so readers can verify release vs main vs distribution truth without referencing internal planning blueprints.

## Proof Layer 1: Product Surface

These prove that the public narrative maps to visible product surfaces:

- [README.md](../README.md)
- [docs/start-here.md](./start-here.md)
- [docs/runtime-truth.md](./runtime-truth.md)
- [docs/architecture.md](./architecture.md)
- [docs/mcp-quickstart.md](./mcp-quickstart.md)
- `./bin/sourceharbor help`
- the web command center routes, including the reader frontstage at `/reader`
- the API route map
- the MCP tool map

What this layer answers:

- What does SourceHarbor do?
- What can a new operator see?
- What surfaces exist for humans and agents?

## Proof Layer 2: Runnable Local Evidence

These prove that the repo is not just presentation:

```bash
source .runtime-cache/run/full-stack/resolved.env
./bin/full-stack status
curl -sS "${SOURCE_HARBOR_API_BASE_URL}/healthz"
python3 scripts/governance/check_env_contract.py --strict
python3 scripts/governance/check_host_safety_contract.py
python3 scripts/governance/check_test_assertions.py
eval "$(bash scripts/ci/prepare_web_runtime.sh --shell-exports)"
( cd "$WEB_RUNTIME_WEB_DIR" && npm run lint )
```

What this layer answers:

- Does the stack boot locally?
- Are the public contracts wired?
- Are tests and lint gates meaningful?

Local-proof boundary:

- use the repo-managed route snapshot under `.runtime-cache/run/full-stack/resolved.env` as the current local API/Web truth
- do not assume any process already listening on `9000`, `3000`, or `5432` belongs to the clean-path stack
- host Postgres and container Postgres are different data planes; the clean local path is container-first and defaults to `CORE_POSTGRES_PORT=15432`

If you want the stricter long live-smoke lane, run:

```bash
./bin/smoke-full-stack --offline-fallback 0
```

That command goes beyond the base local supervisor proof above. It intentionally
enters provider-backed checks such as YouTube preflight and sender
configuration, so a failure there does not automatically mean the repo-managed
local stack is broken.

## Proof Layer 3: Runtime Artifact Evidence

These prove that a pipeline run leaves inspectable evidence behind:

- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/feed/digests`
- `POST /api/v1/reader/batches/{batch_id}/materialize`
- `GET /api/v1/reader/documents`
- `GET /api/v1/reader/navigation-brief`
- `POST /api/v1/retrieval/search`
- artifact references exposed by job payloads
- source contribution drawer payloads and traceability routes exposed by published reader documents
- step summaries, degradations, and notification retry details

What this layer answers:

- What happened in a run?
- Where did a digest come from?
- Which frozen batch became which published reader document?
- Can an operator inspect failure, degradation, and retry state?

## Proof Layer 4: Release And Remote Evidence

This layer is stricter:

- GitHub Actions on the current `main`
- published releases
- release notes and changelog
- any remote or external distribution proof attached to a release
- live GitHub profile settings such as description, homepage, topics, discussions, and uploaded social preview state
- manual external lanes such as GHCR publishing or release attestation only after protected-environment approval

What this layer answers:

- Can the current public branch back up external distribution claims?
- Is the release surface active and legible?
- Do the live GitHub profile settings still match the tracked repo intent?

Current release-side truth still needs one extra sentence kept explicit:

- the current public repo has a live GitHub Release object
- that release object is current only while it still matches the remote head you
  are describing
- uploaded social preview state is also part of this layer: the tracked asset can
  exist in-repo before the live GitHub upload is performed

Current remote-proof reading rule:

- treat current `main`, latest release, and workflow-dispatch evidence as separate ledgers
- only treat GitHub checks and workflow-dispatch runs as current remote proof when their recorded `headSha` still matches the current remote head
- treat the current branch-protected required-check set as its own live contract; if GitHub protection now requires `CodeQL`, `dependency-review`, `trivy-fs`, `trufflehog`, or `zizmor`, the generated required-checks ledger and any summary docs must match that live set
- live GitHub description, homepage, topics, and discussions should be checked live against `config/public/github-profile.json` before repeating the claim
- workflow-dispatch lanes such as standard-image publish or release attestation can still be blocked by repo policy, account permission, or required approval even when current `main` itself is healthy
- successful current-head workflow-dispatch receipts for release evidence,
  public API image publishing, or strict CI image publishing still belong to the
  external-proof ledger, not the default install story, and they must be
  refreshed whenever `main` moves again
- a fresh GitHub release cut can catch latest release truth back up to current
  `main`, but that does not automatically refresh package registries,
  marketplace directories, or other external listing ledgers
- release-side proof must still be checked against the latest live tag, because current `main` can move ahead again after docs/governance closeout merges
- provider-backed live proof still stays separate from GitHub/release truth
- a tracked social-preview asset path is not the same thing as the asset being uploaded live in GitHub repo settings
- a public bundle or metadata template is not the same thing as an official marketplace, registry, or directory listing

## Future-direction Truth

This page should also protect readers from a different kind of drift:

- a credible spike is not the same thing as a shipped capability
- a workflow that can run locally is not the same thing as hosted readiness
- a sample playground is not the same thing as a live managed product

Current spike-only directions are summarized in
[reference/project-positioning.md](./reference/project-positioning.md).

Those future-direction summaries describe what might be worth exploring next.
They do **not** upgrade the current public proof layer on their own.

Current blocker truth is also more specific than generic "missing secret"
language:

- Gemini-backed lanes already have a recent maintainer-local proof pass; other
  environments still need Gemini access if they want the same layer.
- Resend live delivery is still blocked by sender configuration such as
  `RESEND_FROM_EMAIL`, a verified sender/domain, and a real destination
  mailbox.
- The strict YouTube live-smoke probe is no longer bounded by a generic hard
  `403` story. Recent local proof already covers direct probe, provider canary,
  and strict live-smoke preflight; reopening the full live lane still depends
  on operator-managed YouTube API access.
- The remaining exact action pack now lives in
  [project-status.md](./project-status.md), because the blocker story has been
  narrowed to Resend sender identity and YouTube project/quota policy rather
  than generic secret absence.

If you want the shortest honest board of what is already real, what is still
secret-gated, and what stays in the spike bucket, read
[project-status.md](./project-status.md).

If you want the stable bucket map for CLI, SDK, hosted, autopilot, and
plugin-first positioning, read
[ecosystem-and-big-bet-decisions.md](./reference/ecosystem-and-big-bet-decisions.md).

## What Counts As Publicly Honest

These are fair claims:

- SourceHarbor is a source-first engineering repository
- SourceHarbor exposes API, MCP, web, and worker surfaces
- SourceHarbor can be run locally and inspected end to end
- SourceHarbor has step-level job evidence and artifact access

These require stronger evidence:

- production-ready hosted service
- turnkey managed deployment
- externally verified distribution on every release
- fully current remote distribution proof, including a current tagged release and any release-side verification tied to it

Tracked manifests and public presentation assets are inputs to this layer, not proof on their own.

Historical planning ledgers are archived execution context only. They can explain how the repo arrived here, but they must not be treated as the current public truth for SourceHarbor.

For the shortest current-state summary of what is shipped, what is still gated, and what remains future direction, read [project-status.md](./project-status.md).

## Short Version

SourceHarbor can be boldly presented, but it must stay truthful:

- **sell the result first**
- **show the proof right after**
- **never swap local proof for remote proof**
- **use the runtime truth map when docs, ports, and old memories disagree**
- **use `project-status.md` when you need the current shipped-vs-gated scoreboard**
