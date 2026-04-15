# Public Privacy And Data Boundary

This page explains what SourceHarbor's public repository should and should not expose.

## Allowed Public Material

- source code
- public contracts
- sanitized samples
- documentation that explains behavior and boundaries

## Material That Must Stay Private

- secrets and tokens
- maintainer personal email addresses or other direct personal contact details
- personal inbox contents
- customer or operator data
- raw runtime logs with sensitive identifiers
- private failure evidence that cannot be safely sanitized
- public wording that discloses secret existence state, winner-key/operator-store narratives, or direct home-cache/profile paths

## Reading Rule

If you are evaluating the repo:

- public screenshots explain surfaces
- public proof pages explain the verification ladder
- private or runtime-only evidence must not be inferred from missing files

The boundary matters because a trustworthy open repository is not the same thing as a data dump.

Two current examples:

- Google Account and Resend may appear in local browser proof flows, but they remain operator/proof surfaces, not public ingestion targets
- login state, sender identity, and secure operator credential updates remain human-only or policy-gated even when the surrounding repo code is already real
- maintainer-local browser proof helpers such as `GITHUB_COOKIE`, `GOOGLE_COOKIE`, `RESEND_COOKIE`, and `YOUTUBE_COOKIE` may exist in `.env`, but they stay local-only secrets and must never be committed or treated as public integration contract
- maintainer-local runtime overlays such as `.runtime-cache/tmp/web-runtime/workspace/apps/web/.env.local` may carry local write-session fallback values; they stay private runtime state and must never be committed, mirrored, or cited as public proof
- public proof ledgers may safely describe release/current-main drift or required-check mismatches, but they must not reveal private tokens, mailbox state, browser-session content, or other operator-only data while doing so
- public proof ledgers may also say that a fresh anonymous registry read-back returned no SourceHarbor entry or that a lowercase Pages homepage path 404s, but they must not fill those gaps with operator-only dashboard screenshots or credential state
- repo-managed runtime workspaces such as `.runtime-cache/tmp/web-runtime/` and mutation debug sandboxes stay local-only verification state; they must be governed and cleaned, not exposed as public repository artifacts
- repo-owned fallback service logs under `.runtime-cache/logs/local-core/` stay private runtime diagnostics; they are meant for maintainer troubleshooting, not for public repo storytelling or artifact publication
- repo-owned proxy-video artifacts created only to satisfy maintainer-local Gemini video input constraints stay private runtime state too; they are not public samples, not media-kit assets, and not proof of redistribution rights
- donor reference trees under the internal `.agents` reference area may contain upstream test idioms or placeholder secret-shaped strings for study purposes; they are internal reference inputs and must not be treated as public SourceHarbor surfaces or fed back into public trust claims
- thin public stubs for submission packets or UI handoffs may stay in `docs/`, but the maintainer-ready packet content and design ledgers must live in the internal planning area rather than the public newcomer path
