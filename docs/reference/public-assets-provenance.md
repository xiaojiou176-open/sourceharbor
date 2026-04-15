<!-- generated: scripts/governance/render_public_asset_provenance.py; do not edit directly -->

# Public Asset Provenance

This file is the machine-rendered file-level ledger for public presentation assets that ship with the repository.

The goal is simple:

- make every tracked public presentation asset addressable by path
- record the current provenance granularity instead of assuming it
- keep public readers from confusing `tracked in the repo` with `fully documented rights chain`

## Current Asset Ledger

| Asset | Kind | Role | Public Surfaces | Provenance Status | Rights Basis | Sanitization | Published Status | Follow-up |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `docs/assets/sourceharbor-hero.svg` | `svg` | `hero` | `README.md`<br>`docs/see-it-fast.md` | `repository-tracked-source-file` | `maintainer-assertion-required` | `non-runtime-illustration` | `currently-published-in-repo` | `yes` |
| `docs/assets/sourceharbor-architecture.svg` | `svg` | `architecture-diagram` | `docs/architecture.md` | `repository-tracked-source-file` | `maintainer-assertion-required` | `non-runtime-illustration` | `currently-published-in-repo` | `yes` |
| `docs/assets/sourceharbor-studio-preview.svg` | `svg` | `readme-front-door-preview` | `README.md` | `repository-tracked-source-file` | `maintainer-assertion-required` | `non-runtime-illustration` | `currently-published-in-repo` | `yes` |
| `docs/assets/sourceharbor-developer-flywheel.svg` | `svg` | `builder-flywheel` | `README.md`<br>`docs/index.md` | `repository-tracked-source-file` | `maintainer-assertion-required` | `non-runtime-illustration` | `currently-published-in-repo` | `yes` |
| `docs/assets/sourceharbor-builder-loop.svg` | `svg` | `builder-loop` | `docs/see-it-fast.md` | `repository-tracked-source-file` | `maintainer-assertion-required` | `non-runtime-illustration` | `currently-published-in-repo` | `yes` |
| `docs/assets/sourceharbor-social-preview.svg` | `svg` | `social-preview-source` | `config/public/github-profile.json` | `repository-tracked-source-file` | `maintainer-assertion-required` | `non-runtime-illustration` | `repository-declared-profile-asset-source` | `yes` |
| `docs/assets/sourceharbor-social-preview.png` | `png` | `social-preview-upload` | `config/public/github-profile.json` | `repository-tracked-derived-file` | `maintainer-assertion-required` | `non-runtime-illustration` | `repository-declared-profile-asset` | `yes` |
| `docs/assets/sourceharbor-square-icon.svg` | `svg` | `directory-square-icon-source` | `config/public/mcp-directory-profile.json`<br>`docs/media-kit.md` | `repository-tracked-source-file` | `maintainer-assertion-required` | `non-runtime-illustration` | `currently-published-in-repo` | `yes` |
| `docs/assets/sourceharbor-square-icon.png` | `png` | `directory-square-icon` | `config/public/mcp-directory-profile.json`<br>`docs/media-kit.md` | `repository-tracked-derived-file` | `maintainer-assertion-required` | `non-runtime-illustration` | `currently-published-in-repo` | `yes` |
| `docs/assets/sourceharbor-mcp-directory-shot-01.png` | `png` | `directory-screenshot` | `config/public/mcp-directory-profile.json`<br>`docs/public-distribution.md`<br>`docs/media-kit.md` | `repository-tracked-derived-file` | `maintainer-assertion-required` | `non-runtime-illustration` | `currently-published-in-repo` | `yes` |

## Reading Notes

- `repository-tracked-source-file` means the asset source file is present in the repository today.
- `maintainer-assertion-required` means this ledger still needs an explicit maintainer-backed rights statement before broader redistribution claims should rely on it.
- `non-runtime-illustration` means the asset is a deliberate presentation illustration rather than a captured runtime artifact.
