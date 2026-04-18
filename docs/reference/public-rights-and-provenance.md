# Public Rights And Provenance

This page explains the rights boundary for the public SourceHarbor repository.

## What Is In Scope

- repository source code
- tracked documentation
- generated public-facing contracts that ship with the repo
- sanitized sample assets that are explicitly marked as public

## What Is Out Of Scope

- private credentials
- operator mailboxes
- customer data
- unpublished runtime artifacts
- local agent workspaces
- unreviewed third-party media or logs

## Provenance Rule

Public readers should assume:

- tracked source files are the canonical public implementation
- generated proof pages are summaries, not replacements for source truth
- third-party licenses are summarized in [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md)
- file-level public presentation asset status is tracked in [public-assets-provenance.md](./public-assets-provenance.md)

They should not assume:

- a first-cut starter pack is a registry-published ecosystem product
- a browser proof helper surface is the same thing as a supported source-ingestion lane
- a workflow-dispatch receipt implies the protected environment has already approved or published the result
- a latest tagged release is automatically the same snapshot as the current remote `main`
- a generated required-check ledger remains current after GitHub branch protection adds or removes required checks
- a duplicated README, builder-guide, or status-page sentence about package versions or directory visibility carries fresher provenance than the canonical `docs/public-distribution.md` ledger
- a repo-managed web runtime copy or a local mutation receipt automatically upgrades into public proof of hosted, packaged, or registry-listed distribution
- a registry starter packet, package metadata template, or older repo ledger automatically proves a current Official MCP Registry listing without a fresh anonymous read-back
- a lowercase GitHub Pages URL variant carries the same public provenance as the live deployed homepage path when the actual Pages host only serves the case-correct route
- a repo-managed web runtime `.env.local` file or local write-session fallback token carries any public redistribution rights; it remains maintainer-local runtime state only
- a repo-owned clean proof pack or UI audit runner automatically upgrades into public proof; those artifacts remain maintainer-local verification scaffolding even when they use Gemini or Designer feedback
- a repo-owned frontstage clean proof runner or its tempdir screenshot packs automatically upgrades into public proof; those artifacts remain maintainer-local review scaffolding even when they evaluate the public-facing front door
- a host-bootstrapped strict-CI fallback or repo-owned local core-services fallback changes the rights boundary of the public repo; both are maintainer-local verification behavior, not new public distribution rights
- the fact that `./bin/full-stack down` now tears down repo-owned core services
  during a clean local reset also stays inside maintainer-local verification
  behavior; it does not widen any public runtime or redistribution claim
- a maintainer-local proxy-video artifact used only to make Gemini video ingestion behave honestly under current API constraints changes the public rights boundary; it is still just local verification substrate
- a donor or reference mirror kept in the internal `.agents` reference tree becomes part of SourceHarbor's public provenance; those inputs remain internal study material and do not widen the rights boundary of the public repo
- a thin public blueprint stub means the internal working contract is public; the stub is the public pointer, while the full contract still stays in the internal planning ledger
- a thin public submission-packet or UI-spec stub means the working packet/spec is public; those stubs are only pointers, while the maintainer-ready submission and design handoffs stay in the internal planning ledger

When rights or provenance are unclear, the safer reading is:

- do not treat the material as redistributable until the repo says so explicitly
