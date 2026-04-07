<!-- generated: docs governance control plane -->
# Required Checks

These are the GitHub Actions checks currently enforced by branch protection on the repository's pull-request path.

Local Git hooks may rerun overlapping checks, but they are contributor-side guardrails rather than the remote branch-protection contract.

| Check | Workflow | Why it exists |
| --- | --- | --- |
| `python-tests` | `ci.yml` | Verifies API, worker, and MCP Python surfaces with the documented in-memory SQLite test path. |
| `web-lint` | `ci.yml` | Keeps the web command center lint-clean. |
| `pre-commit` | `pre-commit.yml` | Runs the all-files hygiene gate for YAML, secrets, Ruff, Biome, Markdown, ShellCheck, and Actionlint. |
| `CodeQL` | `codeql.yml` | Runs GitHub code scanning over the tracked Python and JavaScript/TypeScript surfaces. |
| `dependency-review` | `dependency-review.yml` | Blocks pull requests whose dependency changes fail GitHub's dependency review policy. |
| `trivy-fs` | `trivy.yml` | Scans the repository filesystem and dependency manifests for high-severity vulnerabilities. |
| `trufflehog` | `trufflehog.yml` | Scans the pushed and pull-request Git history delta for verified or unknown secrets. |
| `zizmor` | `zizmor.yml` | Lint-checks GitHub Actions workflow safety on the PR-facing workflow set. |
