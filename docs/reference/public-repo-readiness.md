# Public Repo Readiness

SourceHarbor is publicly readable and locally runnable today.

That does **not** automatically mean every remote or release claim is proven for the current `main`.

## What Is Fair To Claim

- the repository exposes API, worker, MCP, and web surfaces
- the local proof path is documented and rerunnable
- the public story is backed by real commands and tests

## What Needs Stronger Evidence

- hosted availability
- release distribution quality
- remote workflow success on the current `main`
- live GitHub profile settings matching `config/public/github-profile.json`
- any external publication or attestation lane that is intentionally kept behind manual dispatch and protected-environment approval

## Current Public-Readiness Reading Rule

Treat these as separate ledgers, not one blended readiness badge:

- tracked repo/docs truth
- current remote `main` truth
- latest release truth
- live GitHub metadata truth
- live provider/browser truth

Two current reading rules are worth keeping explicit:

- a live GitHub Release object can exist while current remote `main` has already moved ahead again
- the live branch-protected required-check set is its own remote contract; if GitHub protection changes, tracked required-check docs and summaries must be refreshed before the repo repeats a "current remote proof" claim

That separation matters because SourceHarbor can honestly advance one layer without pretending all the other layers moved with it.

Read this together with [proof.md](../proof.md) whenever you want to separate local credibility from remote proof.

For the tracked render-only pointer into commit-sensitive remote lanes, see [docs/generated/external-lane-truth-entry.md](../generated/external-lane-truth-entry.md).
