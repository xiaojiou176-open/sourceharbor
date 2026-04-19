# Media Kit

This page is the shortest truthful answer to:

- which public-facing visual assets already exist in the repo
- which file you should upload for GitHub social preview
- what copy hooks are safe for listing pages and launch materials
- which promo assets still stay optional instead of blocker truth

Use it like a tracked asset pack, not like a launch checklist.

## Exact Social Preview Path

If you want to upload the current tracked GitHub social preview asset, use:

```text
<repo-root>/docs/assets/sourceharbor-social-preview.png
```

Supporting source file:

```text
<repo-root>/docs/assets/sourceharbor-social-preview.svg
```

Tracked config pointer:

- `config/public/github-profile.json -> social_preview_asset`

Current truth:

- the PNG is the upload target and is now aligned to GitHub's 1280x640 recommendation
- the SVG remains the tracked source asset
- the live GitHub upload itself is still a manual platform step

## Public Visual Assets Already In The Repo

| Asset | Role | Current use |
| --- | --- | --- |
| `docs/assets/sourceharbor-social-preview.png` | GitHub social preview upload target | manual repo-settings upload asset |
| `docs/assets/sourceharbor-social-preview.svg` | tracked source illustration for the preview | editable source file |
| `docs/assets/sourceharbor-square-icon.png` | square icon for MCP directory submissions and listing tiles | directory-friendly public icon asset |
| `docs/assets/sourceharbor-square-icon.svg` | tracked source illustration for the square icon | editable source file |
| `docs/assets/sourceharbor-mcp-directory-shot-01.png` | MCP directory and listing screenshot asset | submission-friendly product shot derived from the tracked studio preview |
| `docs/assets/sourceharbor-hero.svg` | README/front-door hero | public product-shape asset |
| `docs/assets/sourceharbor-studio-preview.svg` | README studio preview | public front-door asset |
| `docs/assets/sourceharbor-developer-flywheel.svg` | builder/product loop visual | README/docs narrative support |
| `docs/assets/sourceharbor-architecture.svg` | system map | architecture/docs proof support |

## Safe Copy Hooks

These are the strongest honest hooks for listings, marketplace blurbs, and short
promo copy:

- `AI knowledge control tower`
- `source-first`
- `proof-first`
- `YouTube / Bilibili / RSSHub / RSS`
- `grounded search`
- `briefing-backed Ask`
- `MCP server`
- `public CLI / TypeScript SDK`
- `plugin-grade bundles`
- `starter packs`

## Do Not Overclaim In Promo Copy

Keep these boundaries explicit:

- do not say SourceHarbor is already officially listed everywhere
- do not say OpenClaw is registry-published today
- do not say Codex has an official directory listing today
- do not say Claude Code is already live-listed if you only have submission-ready assets
- do not turn sample/demo proof into hosted or production proof
- do not imply a hosted workspace or autopilot product exists now

## What Still Stays Optional

These help public polish, but they are not repo-side engineering blockers:

- teaser or promo video
- release media pack
- launch thread copy
- marketplace screenshots beyond the tracked social preview asset

## Read Next

- [public-distribution.md](./public-distribution.md)
- [project-status.md](./project-status.md)
- [proof.md](./proof.md)
- [reference/public-assets-provenance.md](./reference/public-assets-provenance.md)
