# Project Positioning

SourceHarbor is a **source-first engineering repository** for AI knowledge intake and MCP-ready long-form source operations.

What that means in plain language:

- the repository is meant to be cloned, inspected, and run
- the strongest proof is local runnable evidence
- the project is not marketed as a turnkey hosted SaaS

The product shape is still real:

- API for ingestion and inspection
- Search / Ask front doors over grounded retrieval
- Watchlists / trends / bundles as the compounder layer
- Worker for pipeline execution
- MCP for agent-facing tooling
- Web command center for operators
- Sample playground and use-case pages as truthful discoverability surfaces

The public promise should stay smaller than the internal engineering ambition. That keeps the repo honest.

## Current Non-promises

SourceHarbor should still **not** be described as:

- a turnkey hosted team workspace
- a managed SaaS product
- an autonomous agent autopilot

Those directions now have explicit internal ledgers instead of implied roadmap
copy. Public docs keep only the stable summary here; the full working contracts
stay in the internal planning ledger used by maintainers.

Two directions are intentionally kept in the "evaluate before promise" bucket:

- Agent Autopilot: worth a human-in-the-loop spike, not ready for product-level claims yet
- Hosted workspace: worth a readiness study, but still incompatible with the current source-first and local-proof-first promise if overclaimed

The same principle also governs builder packaging:

- the repo-local CLI discoverability surface is real now
- thin public CLI / SDK surfaces are now real
- public starter packs are now real, but still first-cut
- plugin-first positioning stays no-go now

If you want the durable ship-now / later / spike-only / no-go ledger for CLI,
SDK, builder ecosystem, hosted, autopilot, and plugin-style expansion, read
[ecosystem-and-big-bet-decisions.md](./ecosystem-and-big-bet-decisions.md).

## Future-Direction Boundaries

These two directions remain real topics, but they are not current public
product promises:

- **Agent Autopilot**: worth a human-in-the-loop exploration slice; not ready
  for shipped-capability copy.
- **Hosted workspace**: worth a readiness study; still incompatible with the
  current source-first and local-proof-first promise if overstated.

Public docs intentionally stop here. If a maintainer needs the full working
contract, the canonical internal copy lives in the internal planning ledger.
Keep those blueprints internal; the
public narrative should always stay summarized in this document and the other
public ledger docs, not lifted directly from the internal execution contracts.
