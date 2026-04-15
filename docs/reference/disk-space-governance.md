# Disk Space Governance

This is the disk-space runbook for SourceHarbor.

Think of it as a warehouse map, not a trash guide.

The point is to answer four different questions separately:

1. **Does it exist?**
2. **Is it really owned by this repo?**
3. **Can it be rebuilt?**
4. **Is it allowed to be cleaned right now?**

Those are not the same question.

## Canonical Path Model

SourceHarbor uses three path classes:

| Class | Canonical root | What belongs there |
| :-- | :-- | :-- |
| Repo-side runtime | `.runtime-cache/` | short-lived repo-local runtime state |
| User-side repo-owned cache/state | `SOURCE_HARBOR_CACHE_ROOT/` | worker state, pipeline workspace, pipeline artifacts, dedicated browser root, tmp scratch, and managed project envs |
| Shared tool cache | shared system paths such as `~/Library/Caches/ms-playwright` or `~/.cache/uv` | toolchain/browser caches that may be used by multiple repos |

The canonical repo-side web runtime workspace is:

- `.runtime-cache/tmp/web-runtime/workspace/apps/web`

The canonical current-state root is:

- `SOURCE_HARBOR_CACHE_ROOT/`

Treat that root like the live warehouse shelf, not like a disposable staging box.

If it is present, it must be counted into the repo-external-repo-owned audit total.

The canonical mainline Python environment is:

- `${SOURCE_HARBOR_CACHE_ROOT}/project-venv`

If sibling entries match `project-venv*` under the same cache root, treat them as duplicate repo-external envs:

- list them separately from the canonical env
- measure their size and latest modification time
- check whether known entrypoints still reference them
- do **not** auto-promote them into cleanup just because they are rebuildable

Those duplicate envs are not mysterious machine junk, but they are also not automatically safe-clear.

The legacy home-level repo-owned state root and older `video-digestor` paths are
migration/compatibility surfaces only.

They may still exist locally, but they must be treated as:

- **present**
- maybe **still referenced**
- not automatically **cleanable**

Legacy retirement is a separate question from legacy detection.

Use this state machine:

1. **detected**
2. **recently active**
3. **still referenced by local `.env`**
4. **retirement blocked or clear**

## The Four Audit Layers

Every disk report must classify findings into exactly one of these layers:

| Layer | Meaning |
| :-- | :-- |
| `repo-internal` | under the repo root |
| `repo-external-repo-owned` | outside the repo, but clearly generated or owned by this repo |
| `shared-layer` | global cache/toolchain state that other projects may also use |
| `unverified-layer` | objects we know may exist, but could not safely measure or attribute yet |

Examples:

- `.runtime-cache/tmp` → `repo-internal`
- legacy home-level repo-owned state root → `repo-external-repo-owned` legacy-compatible migration input
- `$HOME/Library/Caches/ms-playwright` → `shared-layer`
- Docker named volumes when the daemon is unavailable → `unverified-layer`

## Repo-Internal Residue Map

Second-pass audit output keeps a dedicated repo-internal residue map under `governance.repo_internal_residue`.

It is intentionally descriptive, not a cleanup queue.

The fixed buckets are:

- `proof_scratch`
- `active_logs`
- `local_private_ledgers`
- `tracked_release_evidence`
- `orphan_residue`

Think of these like labeled shelves in the warehouse.

The point is to stop guessing what a leftover path "probably" is.

Examples:

- `proof_scratch` → repo-side image-audit workbenches under `.runtime-cache/tmp/*image-audit*`
- `active_logs` → `.runtime-cache/logs/app`
- `local_private_ledgers` → authoritative `.runtime-cache/evidence/ai-ledgers` plus optional `.agents` compatibility bridge
- `tracked_release_evidence` → `artifacts/releases`
- `orphan_residue` → `apps/web/node_modules.broken.*`

Repo-external duplicate envs are a separate descriptive surface.

Think of them like extra warehouse keys that still open a side room:

- the canonical key is expected
- extra keys should be inventoried and provenance-checked
- only after reference checks are clear should they move toward any verify-first retirement lane

Being listed here does **not** mean the object is safe-clear.

It only means the audit now has a fixed bucket for it.

## Cleanup States

Use these states in order:

| State | What it means in plain language |
| :-- | :-- |
| `exists` | the object is on disk |
| `ownership-confirmed` | we have enough evidence that this repo owns or depends on it |
| `rebuildability-confirmed` | we know how to recreate it safely |
| `cleanup-allowed` | policy and gates both say it may be removed now |

Large is not enough.

Rebuildable is not enough.

Outside the repo is not enough.

## Cleanup Waves

### Wave 1: Safe

These are rebuildable caches that do not carry current pipeline state:

- `.mypy_cache`
- source-tree `__pycache__`
- small `pytest` and `ruff` index residues
- tiny stale `run/` files that are below the micro-state threshold

Default mode is dry-run:

```bash
./bin/disk-space-cleanup --wave safe
```

Authorized apply requires explicit confirmation:

```bash
./bin/disk-space-cleanup --wave safe --apply --yes
```

### Wave 2: Repo tmp duplicates

These are larger and need extra gates:

- `.runtime-cache/tmp/web-runtime`
- `.runtime-cache/tmp/sourceharbor-verify-venv`
- `.runtime-cache/tmp/sourceharbor-pypi-verify-venv`
- `.runtime-cache/tmp/ws6-test-venv`

Before these can be deleted, the cleanup gate must prove:

1. the path has been quiet for at least 10 minutes
2. explicit runtime lock paths are clear
3. `lsof` does not show active users
4. the configured rebuild command succeeds after deletion

### Wave 3: External history copies

These are repo-owned external history candidates such as:

- `${SOURCE_HARBOR_CACHE_ROOT}/root-venv-backup`
- `${SOURCE_HARBOR_CACHE_ROOT}/codex-ghcr-*`
- `${SOURCE_HARBOR_CACHE_ROOT}/project-venv-*`
- `${SOURCE_HARBOR_CACHE_ROOT}/ws6-test-venv`
- `$HOME/.cache/video-digestor/closure-fix-venv`
- `$HOME/.cache/video-digestor`

They are **verify-first**, not safe-by-name.

They must prove:

1. current `.env`, fallback scripts, and systemd fallbacks do not reference them
2. they are outside the active change window
3. an equivalent mainline environment exists

Even when all three checks currently pass, these objects stay in the **verify-first** bucket.

They do **not** become safe-clear just because the dry-run shows them as eligible.

Eligibility means "may enter an execution wave after review", not "now safe to delete by default".

## Repo-side Proof Scratch

Some repo-side `tmp/` paths are temporary proof workbenches rather than generic cache.

Examples:

- `.runtime-cache/tmp/manual-image-audit`
- `.runtime-cache/tmp/public-image-audit`
- `.runtime-cache/tmp/audit-images`
- `.runtime-cache/tmp/audit-images-direct`
- `.runtime-cache/tmp/image-audit`

Treat these as:

- **repo-internal**
- ownership-confirmed
- maybe rebuildable
- **not automatically cleanup-allowed**

They are proof scratch, not anonymous junk drawers.

## Local Private Ledgers

`.agents/Plans` remains a compatibility bridge.

The authoritative local-private execution ledger root is:

- `.runtime-cache/evidence/ai-ledgers`

Second-pass governance should migrate readable plan ledgers into that authoritative target while preserving the original `.agents/Plans` files.

That migration is a copy-forward step, not a destructive cleanup step.

## Explicit Non-Targets

These are intentionally excluded from automatic cleanup planning:

- `apps/web/node_modules`
- `.venv`
- `${SOURCE_HARBOR_CACHE_ROOT}/project-venv`
- `${SOURCE_HARBOR_CACHE_ROOT}/state`
- `$HOME/Library/Caches/ms-playwright`
- `$HOME/.cache/uv`
- `$HOME/.local/share/uv/python`

Reason:

- some are active mainline dependencies
- some are protected current-state roots
- some are shared caches that can hurt other projects

The legacy home-level `.sourceharbor/` root is also not an automatic cleanup
target. It is a migration input root and drift signal until local environments
have been fully moved under `SOURCE_HARBOR_CACHE_ROOT`.

Legacy `video-digestor` roots are different: once current SourceHarbor state is
canonical under `SOURCE_HARBOR_CACHE_ROOT` and legacy retirement is clear, they
move into the `external-history` verify-first lane instead of staying
permanently excluded.

## Operator Commands

Audit only:

```bash
./bin/disk-space-audit
```

Dry-run a specific cleanup wave:

```bash
./bin/disk-space-cleanup --wave repo-tmp
```

Repo-side runtime maintenance is a different lane from cleanup waves.

Use it when you want to normalize and inspect `.runtime-cache/**` without
manually deleting directories:

```bash
./bin/runtime-cache-maintenance
./bin/runtime-cache-maintenance --apply
```

Repo-owned external cache/state maintenance is a sibling lane:

```bash
python3 scripts/runtime/maintain_external_cache.py --json
python3 scripts/runtime/maintain_external_cache.py --apply
```

Repo-scoped Docker hygiene is another sibling lane:

```bash
python3 scripts/runtime/docker_hygiene.py --json
python3 scripts/runtime/docker_hygiene.py --apply
```

This lane is intentionally narrow:

- it inventories only repo-owned container/image/network patterns
- it inventories repo-owned named volumes but keeps them report-only by default
- it does not prune global Docker cache
- named volumes remain verify-first
- local debug images must clear a quiet window and have no attached containers before cleanup

Local entrypoints may also trigger throttled external cache maintenance under
`SOURCE_HARBOR_CACHE_ROOT`. That lane is conservative by design:

- protected objects such as `project-venv/` and `state/*.db` are budget-only, not auto-delete
- duplicate envs, `workspace/*`, `artifacts/*`, and `tmp/*` are verify-first auto-maintenance candidates
- shared caches like `~/.cache/uv` and `~/Library/Caches/ms-playwright` stay out of repo-owned cleanup
- the browser root resolved by `SOURCE_HARBOR_CHROME_USER_DATA_DIR` is permanent repo-owned browser state: keep it visible in audit, but never put it into TTL/cap auto-maintenance

For operator-first review, treat Ops and disk governance as one story:

- `./bin/disk-space-audit --json` explains what exists and who owns it
- `./bin/disk-space-cleanup --wave repo-tmp --json` explains whether the repo-side duplicate runtime is currently cleanup-eligible
- `/ops` should surface that same repo-side duplicate-runtime and duplicate-env story instead of inventing a separate wording layer

Read the runtime tree with these rules:

- `.runtime-cache/run/*` is live runtime state, not default cleanup
- `.runtime-cache/logs/*` is structured log storage with governed retention, not
  generic trash
- `.runtime-cache/reports/*` is the machine-report layer; keep it as report
  truth unless a cleanup wave explicitly reclassifies it
- `.runtime-cache/evidence/*` is debug and proof evidence with governed
  retention, not a scratch bucket
- `.runtime-cache/tmp/*` is short-lived scratch space, but it only becomes a
  cleanup candidate after the wave gate proves quiet-window, lock-clear, and
  rebuildability conditions

In plain language: do not hand-delete `.runtime-cache/` just because it is
large. Use `runtime-cache-maintenance` for repo-side maintenance, and use
`disk-space-cleanup --wave ...` when you are intentionally executing the
governed cleanup plan.

JSON output for automation:

```bash
./bin/disk-space-audit --json
./bin/disk-space-cleanup --wave safe --json
```

The cleanup JSON keeps these totals separate:

- `safe_clear_bytes`
- `verify_first_bytes`
- `protected_bytes`

This is intentional.

Do not collapse them back into a single "release potential" sentence.

Validate the generated audit report shape:

```bash
./bin/disk-space-audit-check
```

Copy local-private ledgers into the authoritative target:

```bash
python3 scripts/governance/migrate_local_private_ledgers.py --json
```

Dry-run the legacy-path migration plan:

```bash
./bin/disk-space-legacy-migration --json
```

Authorized migration requires explicit source and target mappings:

```bash
./bin/disk-space-legacy-migration \
  --apply --yes \
  --mapping 'PIPELINE_ARTIFACT_ROOT=${PIPELINE_ARTIFACT_ROOT:-legacy-artifacts}::${SOURCE_HARBOR_CACHE_ROOT}/artifacts'
```

For the common "migrate whatever `.env` currently points at into the canonical
targets" case, use:

```bash
./bin/disk-space-legacy-migration --apply --yes --auto-mappings
```

## Important Boundary

These tools are designed to separate:

- **what exists**
- **what is owned**
- **what is rebuildable**
- **what is cleanable right now**

If those four states are collapsed into one sentence, the report is not trustworthy.

The real execution order is fixed:

1. `./bin/disk-space-audit --json`
2. `./bin/disk-space-legacy-migration --json`
3. `./bin/disk-space-cleanup --wave safe --apply --yes`
4. `./bin/disk-space-cleanup --wave repo-tmp --apply --yes`
5. `./bin/disk-space-cleanup --wave external-history --apply --yes` only after legacy retirement is clear
