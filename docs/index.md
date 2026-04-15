# SourceHarbor Docs

If the README is the storefront, this page is the lobby directory.

## Public ledger summary

This index keeps the approved public ledger front and center: reader-first surfaces, proof ladders, and verification checks stay obvious, while working blueprints stay in the internal planning ledger. Whenever you mention release vs remote vs distribution truth, link to [project-status.md](./project-status.md), [proof.md](./proof.md), or [public-distribution.md](./public-distribution.md) so readers can verify the exact ledger.

SourceHarbor has several layers, but the public entry should stay simple:

1. **See the outcome in under a minute**
2. **Take the no-boot tour**
3. **Run the shortest truthful path**
4. **Inspect the proof**
5. **Dive into architecture only when you need it**

<p>
  <img
    src="./assets/sourceharbor-developer-flywheel.svg"
    alt="SourceHarbor developer flywheel showing source intake, job trace, Search and Ask, MCP and API reuse, and the operator loop."
    width="100%"
  />
</p>

## Why Builders Keep Reading

This is the shortest honest explanation for why the repo feels more product-shaped than script-shaped:

| Builder question | Fastest truthful answer | Where to verify it |
| :-- | :-- | :-- |
| **Can I use this with Codex or Claude Code right now?** | Yes, through the existing MCP and HTTP API surfaces. | [mcp-quickstart.md](./mcp-quickstart.md), [builders.md](./builders.md) |
| **What about OpenClaw?** | There is now a first-cut local OpenClaw starter pack, but it still stays outside the primary front door and outside marketplace positioning. | [compat/openclaw.md](./compat/openclaw.md), [builders.md](./builders.md), [public-skills.md](./public-skills.md) |
| **Is the AI story grounded or just decorative copy?** | Search, Ask, proof, runtime truth, and project status are kept on the same story line. | [proof.md](./proof.md), [project-status.md](./project-status.md), [runtime-truth.md](./runtime-truth.md) |
| **Is there anything worth revisiting after the first run?** | Yes: watchlists, trends, bundles, playground, and use-case pages form the compounder layer. | [runtime-truth.md](./runtime-truth.md), [samples/README.md](./samples/README.md) |

## Start By Goal

| If you want to... | Start here | What you get |
| :-- | :-- | :-- |
| **Understand the product in 3 minutes** | [README.md](../README.md) | The product story, quick value, and star-worthy reasons |
| **Get the fastest no-boot preview** | [see-it-fast.md](./see-it-fast.md) | The command center, digest feed, and job trace path without setup |
| **Run the shortest truthful path** | [start-here.md](./start-here.md) | A result-first local flow ending in jobs, feed, and proof |
| **Open the MCP front door** | [mcp-quickstart.md](./mcp-quickstart.md) | Startup, representative tools, and the relation between MCP, API, and Web |
| **Build on top of SourceHarbor** | [builders.md](./builders.md) | How Codex, Claude Code, OpenClaw, generic MCP clients, API consumers, public packages, and starter packs fit the current repo truth |
| **Open the public starter surface** | [public-skills.md](./public-skills.md) | Public compatibility docs, starter prompts, and runnable examples |
| **Check public distribution status** | [public-distribution.md](./public-distribution.md) | What is bundle-ready, what is submit-ready, and which final steps stay human-only |
| **Grab the public asset pack** | [media-kit.md](./media-kit.md) | Exact social preview path, tracked public visuals, listing copy hooks, and teaser-video prep notes |
| **Try the read-only sample playground** | [samples/README.md](./samples/README.md) | Clearly labeled sample corpus and demo surfaces |
| **Read the site capability ledger** | [site-capability.md](./site-capability.md) | Current read-only capability boundaries, next low-risk deepening work, and human-only edges |
| **Open the compounder layer** | [runtime-truth.md](./runtime-truth.md) | How watchlists, trends, bundles, and sample surfaces fit the current truth |
| **See what is done vs still a bet** | [project-status.md](./project-status.md) | The shortest truthful status board for delivered, gated, sample-only, and future-direction surfaces |
| **Check what is publicly provable today** | [proof.md](./proof.md) | Commands, boundaries, and evidence layers |
| **See what is still a future-direction spike** | [reference/project-positioning.md](./reference/project-positioning.md) | What is worth exploring next without pretending it already exists |
| **Understand the moving parts** | [architecture.md](./architecture.md) | API, worker, MCP, web, and shared surfaces |
| **See how verification works** | [testing.md](./testing.md) | Local checks, CI checks, and smoke paths |
| **Compare SourceHarbor to other repo shapes** | [compare.md](./compare.md) | Differentiation, trade-offs, and why this repo is product-shaped |
| **Scan common questions fast** | [faq.md](./faq.md) | Adoption, scope, hosted-vs-source-first, and proof boundaries |

## Read In Layers

### Layer 1: Product Surface

- [README.md](../README.md)
- [see-it-fast.md](./see-it-fast.md)
- [start-here.md](./start-here.md)

### Layer 2: Public Proof

- [proof.md](./proof.md)
- [testing.md](./testing.md)
- [CHANGELOG.md](../CHANGELOG.md)

### Layer 2.5: Builder Entry

- [builders.md](./builders.md)
- [mcp-quickstart.md](./mcp-quickstart.md)
- [compat/openclaw.md](./compat/openclaw.md)

### Layer 3: System Map

- [architecture.md](./architecture.md)
- [compare.md](./compare.md)

### Layer 4: Community And Contribution

- [CONTRIBUTING.md](../CONTRIBUTING.md)
- [SUPPORT.md](../SUPPORT.md)
- [SECURITY.md](../SECURITY.md)

## First-Hop Route

If you only have one minute, trust these four documents first:

1. `README.md` for the front door and product shape
2. `docs/start-here.md` for the first real run
3. `docs/proof.md` for the evidence ladder and proof boundary
4. `docs/testing.md` for the testing and CI contract

## Truth Route At A Glance

| Surface | Role | Reading rule |
| :-- | :-- | :-- |
| [README.md](../README.md) | Front door | Start here for product shape and navigation, not for commit-sensitive verdicts |
| [start-here.md](./start-here.md) | First real run | Use this when you want the shortest truthful local path |
| [proof.md](./proof.md) | Proof ladder | Use this to understand what is locally provable, what needs remote proof, and where the public boundary stops |
| Operator-generated pointers and ledgers | Secondary maintainer aids | Keep them off the first-hop truth route; use them only after the public ledgers above |
| Maintainer-only planning ledger | Historical execution archive | Treat it as archived planning context, not as the current truth route for public readers |

## Public Trust Links

- [CONTRIBUTING.md](../CONTRIBUTING.md)
- [SUPPORT.md](../SUPPORT.md)
- [SECURITY.md](../SECURITY.md)
- [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md)
- [.github/CODEOWNERS](../.github/CODEOWNERS)
- [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)
- [docs/reference/public-assets-provenance.md](./reference/public-assets-provenance.md)
- [docs/reference/public-artifact-exposure.md](./reference/public-artifact-exposure.md)
