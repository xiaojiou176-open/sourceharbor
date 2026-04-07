<!-- generated: docs governance control plane -->
# CI Topology

Current deterministic PR-facing CI in this repository is intentionally small and local-proof-first.

- root allowlist entries: `44`
- runtime root: `.runtime-cache`
- CI jobs in `.github/workflows/ci.yml`: `python-tests`, `web-lint`
- Pre-commit workflow jobs in `.github/workflows/pre-commit.yml`: `pre-commit`
- canonical python-tests command: `bash scripts/ci/python_tests.sh`
- pre-push is a contributor-side parity hook: it reruns env contract, placebo assertion guard, `bash scripts/ci/python_tests.sh`, and web lint locally after a deterministic `npm ci` refresh when tracked web manifests drift or `apps/web/node_modules/.bin/next` is missing.
- PR-facing security workflows: `codeql.yml`, `dependency-review.yml`, `zizmor.yml`, `trivy.yml`, `trufflehog.yml`
- GHCR image publish workflow runs on `ubuntu-latest` and sets up Docker Buildx before calling `scripts/ci/build_standard_image.sh`
- release evidence attestation stays in `.github/workflows/release-evidence-attest.yml`.

## Five-layer verification map

| Layer | Primary entrypoints | Reading rule |
| --- | --- | --- |
| `pre-commit` | fast local checks in `docs/testing.md` + `npm run lint` | fastest contributor-side contract before deeper proof |
| `pre-push` | `.githooks/pre-push` | default local parity hook; keep it deterministic instead of turning it into a full closeout audit |
| `hosted` | `ci.yml`, `pre-commit.yml`, `dependency-review.yml`, `codeql.yml` on `pull_request`/`push`, `trivy.yml`, `trufflehog.yml`, `zizmor.yml` | branch-protected GitHub contract for pull requests and `main` |
| `nightly` | `codeql.yml` on `schedule` | background CodeQL refresh; keep it thin and do not create a separate weekly governance bucket |
| `manual` | `./bin/repo-side-strict-ci --mode pre-push`, `./bin/quality-gate --mode pre-push`, `./bin/governance-audit --mode audit`, `./bin/smoke-full-stack --offline-fallback 0`, repo-owned real-profile browser proof, `build-ci-standard-image.yml`, `release-evidence-attest.yml` | provider/browser/release/publication truth plus closeout-grade repo/public audits |
