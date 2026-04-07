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
- public proof ledgers may safely describe release/current-main drift or required-check mismatches, but they must not reveal private tokens, mailbox state, browser-session content, or other operator-only data while doing so
