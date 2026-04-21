# Site Capability Ledger

This page is the shortest truthful answer to:

- which site-level capabilities already have real code or diagnostics behind them
- which ones are still only local/browser/operator proof
- where the safest next read-only deepening work should land
- which last-mile actions stay human-only because they cross an external-account boundary

Use it like a capability ledger, not like a promise that every logged-in site is
already a deep integration target.

## Current Capability Map

| Site | Strongest layer today | Current repo role | What is already real | What still stays bounded |
| --- | --- | --- | --- | --- |
| **Google Account** | DOM / page-state proof | repo-owned Chrome login-persistence anchor | repo-owned browser root, restart persistence, and login sanity checks | stays a proof anchor, not a source adapter or account-automation target |
| **YouTube** | hybrid: Data API + DOM / page-state proof | strongest source lane plus live browser proof target | API probes, strict preflight, comments collector, live-smoke path, and browser-proof runbooks | the strict end-to-end live lane still depends on operator-managed YouTube API access when the lane is reopened |
| **Bilibili account center** | URL / page-state proof today, hybrid later | account-proof anchor for the strong-supported Bilibili source lane | repo-owned Chrome proof with redirect-vs-account-home readback, source intake copy, route-health diagnostics, and cookie-driven richer read-only lanes | stronger proof still depends on human login; account-side writes remain out of scope |
| **Resend dashboard** | admin UI + provider configuration | operator-side notification and sender-identity proof surface | provider-health checks, ops diagnostics, settings routes, and notification readiness gates | sender/domain/mailbox setup remains external provider-admin work |
| **RSSHub / generic RSS** | HTTP / API substrate | generalized source-universe intake substrate | adapters, fetcher, normalizer, runtime probes, and honest intake/front-door copy | route-by-route proof still needs route-level evidence instead of blanket claims |

## Where To Deepen Next

If you want to keep pushing read-only capability work without crossing into
external-account writes, the safest next layer is:

1. **Ledger and docs truth**
   - keep `docs/project-status.md`, `docs/runbook-local.md`, and `docs/runtime-truth.md` aligned
   - keep site-by-site strongest layer, safest method, and proof boundary explicit
2. **Runtime and diagnostics**
   - extend repo-owned Chrome helper flows and safe tab sets
   - improve provider canary / route-health / failure classification outputs
3. **UI truth surfaces**
   - surface the current capability ledger in `/ops` and the intake front door
   - make the proof boundary legible without pretending external steps are already closed

## Human-Only Boundaries

These steps stay human-only or policy-gated even when the surrounding repo code
is already real:

- GitHub social preview upload in repo settings
- Resend sender/domain/mailbox verification
- operator-managed YouTube API access for the live-smoke lane when that lane is reopened
- marketplace / registry submissions that require CAPTCHA, human verification, payment, legal acceptance, or irreversible profile fields

## Read-Only Guardrails

Do not treat these as allowed:

- changing third-party account settings
- exporting sensitive cookies or session material into public artifacts
- scraping private data beyond the minimum operator proof boundary
- turning local browser proof into a public product claim

## Read Next

- [project-status.md](./project-status.md)
- [runbook-local.md](./runbook-local.md)
- [runtime-truth.md](./runtime-truth.md)
- [public-distribution.md](./public-distribution.md)
- [reference/public-privacy-and-data-boundary.md](./reference/public-privacy-and-data-boundary.md)
