<!-- generated: docs governance control plane -->

# External Lane Truth Entry

This tracked page is a machine-rendered pointer only.

It must not carry current verdict payload. Read the runtime-owned reports directly for commit-sensitive state.

| Lane | Canonical Artifact | Reading Rule |
| --- | --- | --- |
| `remote-platform-integrity` | `.runtime-cache/reports/governance/remote-platform-truth.json` | tracked pointer only; runtime reports decide current state |
| `ghcr-standard-image` | `.runtime-cache/reports/governance/standard-image-publish-readiness.json` | tracked pointer only; runtime reports decide current state |
| `public-api-image` | `.runtime-cache/reports/build-public-api-image/metadata.json` | tracked pointer only; runtime reports decide current state |
| `release-evidence-attestation` | `.runtime-cache/reports/release/release-evidence-attest-readiness.json` | tracked pointer only; runtime reports decide current state |

- tracked page is a machine-rendered pointer only
- current external state must come from `.runtime-cache/reports/**`
- stale successful remote workflows should be treated as `historical`, not promoted to current `verified` wording
