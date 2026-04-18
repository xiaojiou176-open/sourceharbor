# Public Artifact Exposure

This page defines which artifact shapes are safe to expose in the public repository.

## Safe Public Artifact Types

- sanitized markdown examples
- public contract snapshots
- generated proof indexes that do not embed sensitive payloads
- performance samples that are explicitly marked as public and sanitized

## Unsafe Public Artifact Types

- raw operator logs
- customer content
- unsanitized email digests
- private job payloads
- environment files or runtime secrets

## Practical Rule

If an artifact contains real user data, credentials, or sensitive runtime context, it does not belong in the tracked public surface.

If an artifact is meant to explain repository behavior to a newcomer, it should be:

- sanitized
- intentionally named
- stable enough to cite from README or docs

Two special cases matter in the current repo:

- workflow-dispatch readiness receipts may be public-safe to track while still waiting on protected-environment approval
- browser/login proof receipts can explain local operator state without turning third-party account surfaces into public product claims
- generated required-check ledgers and current-state summaries are public-safe only when they stay aligned to the current live branch-protection contract and current HEAD; stale snapshots must be treated as historical
- `docs/public-distribution.md` is the public-safe home for fast-moving package, registry, and directory read-backs; other public docs should cite that ledger instead of carrying their own duplicated version or listing snapshots
- a tracked release-ready artifact or social-preview asset is still an input to public proof, not the same thing as the current remote `main` head or a completed live platform upload
- a tracked registry template, directory packet, or older listing note is still only an input to public proof; without a fresh live registry read-back it must not be cited as a current official listing artifact
- tracked public homepage URLs must also be treated as proof-bearing artifacts: if the committed path casing 404s on the live Pages host, that URL is a broken public artifact rather than an acceptable cosmetic variant
- the repo-managed web runtime workspace under `.runtime-cache/tmp/web-runtime/` is an internal verification substrate, not a public artifact to expose or cite as shipped output
- the temporary `.env.local` written into `.runtime-cache/tmp/web-runtime/workspace/apps/web/` is runtime glue for local browser writes, not a distributable config artifact
- clean proof screenshot packs and mini packs created by repo-owned UI audit helpers are maintainer-local verification artifacts; they may feed local Gemini/UI-audit review, but they are not public distribution assets or release artifacts
- frontstage clean proof packs and mini packs created by repo-owned public-surface audit helpers are maintainer-local verification artifacts too; they support local IA and visual review, not public product claims
- mutation receipts under `.runtime-cache/reports/mutation/` are public-safe only as proof summaries; they must not be mistaken for a published package, release, or registry surface
- repo-owned local core-services logs under `.runtime-cache/logs/local-core/` are runtime diagnostics only; they exist to explain local fallback behavior, not to become public-facing product artifacts
- repo-owned core-services teardown behavior under `./bin/full-stack down` is
  still runtime hygiene only; it cleans repo-local verification state and does
  not create any new public artifact surface
- lightweight proxy-video files generated only to satisfy maintainer-local Gemini input constraints are runtime-only surrogate artifacts; they are part of local verification behavior, not a public distribution surface
- `docs/blueprints/*.md` remain legacy thin stubs inside the tracked tree, but they are no longer part of the public entrypoint or docs-navigation registries; the full working contracts stay in the internal planning ledger and should not surface from visitor-facing routes
- `docs/submission/*.md` and internal UI specs may remain as thin public pointers, but the working submission packets and design handoffs stay in the maintainer-only planning ledger rather than the newcomer-facing docs path

For public presentation files under `docs/assets/`, use the file-level ledger in [public-assets-provenance.md](./public-assets-provenance.md).
