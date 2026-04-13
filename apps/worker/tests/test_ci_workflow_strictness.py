from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType, SimpleNamespace, TracebackType
from typing import Any

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_module():
    module_path = _repo_root() / "scripts" / "governance" / "check_ci_workflow_strictness.py"
    spec = importlib.util.spec_from_file_location("check_ci_workflow_strictness", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install_web_e2e_import_stubs() -> None:
    playwright_module = ModuleType("playwright")
    sync_api_module = ModuleType("playwright.sync_api")
    sync_api_module.Browser = object
    sync_api_module.Page = object

    class _SyncPlaywrightContext:
        def __enter__(self) -> Any:
            raise AssertionError(
                "sync_playwright stub should not be entered in collection hook contract test"
            )

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> bool:
            return False

    def _sync_playwright_stub() -> _SyncPlaywrightContext:
        return _SyncPlaywrightContext()

    sync_api_module.sync_playwright = _sync_playwright_stub
    playwright_module.sync_api = sync_api_module
    sys.modules.setdefault("playwright", playwright_module)
    sys.modules.setdefault("playwright.sync_api", sync_api_module)

    support_module = ModuleType("support")
    mock_api_module = ModuleType("support.mock_api")
    mock_api_module.MockApiServer = object
    mock_api_module.MockApiState = object
    mock_api_module.start_mock_api_server = lambda: None
    mock_api_module.stop_mock_api_server = lambda running: None

    runtime_utils_module = ModuleType("support.runtime_utils")
    runtime_utils_module.parse_external_web_base_url = lambda value: None
    runtime_utils_module.resolve_worker_id = lambda configured_worker_id, **_: (
        configured_worker_id or "gw0"
    )
    runtime_utils_module.slugify_nodeid = lambda nodeid: nodeid.replace("/", "-")
    runtime_utils_module.wait_http_ok = lambda url: None
    runtime_utils_module.with_free_port_retry = lambda starter, **_: (starter(3000), 3000)
    runtime_utils_module.worker_dist_dir = lambda worker_id: f".next-{worker_id}"

    support_module.mock_api = mock_api_module
    support_module.runtime_utils = runtime_utils_module
    sys.modules.setdefault("support", support_module)
    sys.modules.setdefault("support.mock_api", mock_api_module)
    sys.modules.setdefault("support.runtime_utils", runtime_utils_module)


def test_global_rules_timeout_uses_job_level_not_step_level() -> None:
    module = _load_module()
    block = """  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo lint
"""
    failures: list[str] = []

    module._check_global_rules(
        Path("ci.yml"),
        "name: CI\non:\n  pull_request:\n",
        {"lint": block},
        failures,
    )

    assert "ci.yml: lint: missing timeout-minutes" in failures


def test_global_rules_hosted_jobs_can_fail_without_continue_on_error() -> None:
    module = _load_module()
    hosted_block = """  preflight-fast-hosted:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - run: echo preflight
"""
    required_ci_secrets_block = """  required-ci-secrets:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - run: python3 scripts/governance/check_required_ci_secrets.py --required GEMINI_API_KEY
"""
    failures: list[str] = []

    module._check_global_rules(
        Path("ci.yml"),
        "name: CI\non:\n  pull_request:\n",
        {
            "required-ci-secrets": required_ci_secrets_block,
            "preflight-fast-hosted": hosted_block,
        },
        failures,
    )

    assert (
        "ci.yml: preflight-fast-hosted: hosted jobs must set continue-on-error: true "
        "to allow fallback takeover" not in failures
    )


def test_pre_push_hook_uses_manifest_hashing_and_local_ci_parity() -> None:
    hook_path = Path(__file__).resolve().parents[3] / ".githooks" / "pre-push"
    content = hook_path.read_text(encoding="utf-8")

    assert 'source "$ROOT_DIR/scripts/lib/standard_env.sh"' in content
    assert 'ensure_external_uv_project_environment "$ROOT_DIR"' in content
    assert (
        'WEB_MANIFEST_HASH_FILE=".runtime-cache/run/hooks/web-package-manifests.sha256"' in content
    )
    assert "npm --prefix apps/web ci --no-audit --no-fund >/dev/null" in content
    assert "git diff --quiet -- apps/web/package-lock.json apps/web/package.json" in content
    assert "bash scripts/ci/python_tests.sh" in content
    assert "--ci-dedupe" not in content


def test_ci_workflow_trusted_internal_pr_boundary_guards_self_hosted_bootstrap() -> None:
    workflow = (_repo_root() / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    module = _load_module()
    jobs = dict(module._job_blocks(workflow))

    assert set(jobs) == {"python-tests", "web-lint"}
    assert "trusted-pr-boundary:" not in workflow
    assert "runs-on: ubuntu-latest" in jobs["python-tests"]
    assert "runs-on: ubuntu-latest" in jobs["web-lint"]


def test_current_repo_ci_workflow_strictness_contract_passes() -> None:
    module = _load_module()
    failures: list[str] = []
    workflow_path = _repo_root() / ".github" / "workflows" / "ci.yml"
    workflow = workflow_path.read_text(encoding="utf-8")

    module._check_global_rules(
        workflow_path, workflow, dict(module._job_blocks(workflow)), failures
    )

    assert failures == []


def test_public_hosted_ci_rejects_local_real_chrome_profile_env() -> None:
    module = _load_module()
    workflow = """name: CI
on:
  pull_request:
  push:
    branches:
      - main
jobs:
  python-tests:
    runs-on: ubuntu-latest
    env:
      SOURCE_HARBOR_CHROME_PROFILE_NAME: sourceharbor
      SOURCE_HARBOR_CHROME_CDP_PORT: "9339"
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@1234567890abcdef1234567890abcdef12345678
      - run: python3 scripts/governance/check_env_contract.py --strict
      - run: python3 scripts/governance/check_test_assertions.py
      - run: bash scripts/ci/python_tests.sh
  web-lint:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@1234567890abcdef1234567890abcdef12345678
      - run: bash scripts/ci/prepare_web_runtime.sh
      - run: npm --prefix "$WEB_RUNTIME_WEB_DIR" run lint
"""
    failures: list[str] = []

    module._check_global_rules(
        Path("ci.yml"), workflow, dict(module._job_blocks(workflow)), failures
    )

    assert (
        "ci.yml: hosted PR path must not reference local-only real Chrome profile env `SOURCE_HARBOR_CHROME_PROFILE_NAME`"
        in failures
    )
    assert (
        "ci.yml: hosted PR path must not reference local-only real Chrome profile env `SOURCE_HARBOR_CHROME_CDP_PORT`"
        in failures
    )


def test_build_standard_image_requires_manual_only_protected_environment() -> None:
    module = _load_module()
    workflow = """name: build-ci-standard-image
on:
  workflow_dispatch:
  push:
    branches:
      - main
jobs:
  publish:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@1234567890abcdef1234567890abcdef12345678
        with:
          clean: true
      - run: echo build
"""
    failures: list[str] = []

    module._check_build_standard_image_specific_rules(workflow, failures)

    assert (
        "build-ci-standard-image.yml: external publish lane must be workflow_dispatch only"
        in failures
    )
    assert (
        "build-ci-standard-image.yml: publish: must use protected environment `external-ghcr-publish`"
        in failures
    )


def test_build_public_api_image_requires_manual_only_protected_environment() -> None:
    module = _load_module()
    workflow = """name: build-public-api-image
on:
  workflow_dispatch:
  push:
    branches:
      - main
jobs:
  publish:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@1234567890abcdef1234567890abcdef12345678
        with:
          clean: true
      - run: echo build
"""
    failures: list[str] = []

    module._check_build_public_api_image_specific_rules(workflow, failures)

    assert (
        "build-public-api-image.yml: external publish lane must be workflow_dispatch only"
        in failures
    )
    assert (
        "build-public-api-image.yml: publish: must use protected environment `external-ghcr-publish`"
        in failures
    )


def test_release_evidence_requires_manual_only_protected_environment() -> None:
    module = _load_module()
    workflow = """name: release-evidence-attest
on:
  workflow_dispatch:
    inputs:
      release_tag:
        description: release tag
        required: false
        type: string
  push:
    tags:
      - "v*"
jobs:
  release-evidence:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@1234567890abcdef1234567890abcdef12345678
        with:
          clean: true
      - run: echo attest
"""
    failures: list[str] = []

    module._check_release_evidence_specific_rules(workflow, failures)

    assert (
        "release-evidence-attest.yml: external attestation lane must be workflow_dispatch only"
        in failures
    )
    assert (
        "release-evidence-attest.yml: release-evidence: must use protected environment `external-release-evidence`"
        in failures
    )
    assert (
        "release-evidence-attest.yml: workflow_dispatch.release_tag must stay required for manual attestation runs"
        in failures
    )


def test_global_rules_reusable_workflow_must_define_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    monkeypatch.chdir(tmp_path)
    reusable = tmp_path / ".github" / "workflows" / "no-timeout.yml"
    reusable.parent.mkdir(parents=True, exist_ok=True)
    reusable.write_text(
        """name: reusable
on:
  workflow_call:
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
""",
        encoding="utf-8",
    )
    block = """  preflight-fast-hosted:
    uses: ./.github/workflows/no-timeout.yml
"""
    failures: list[str] = []

    module._check_global_rules(
        Path("ci.yml"),
        "name: CI\non:\n  pull_request:\n",
        {"preflight-fast-hosted": block},
        failures,
    )

    assert (
        "ci.yml: preflight-fast-hosted: reusable workflow ./.github/workflows/no-timeout.yml must define timeout-minutes on runnable jobs"
        in failures
    )


def test_has_needs_dep_ignores_step_list_items() -> None:
    module = _load_module()
    block = """  preflight-fast:
    needs:
      - required-ci-secrets
    steps:
      - run: |
          cat <<'EOF'
          - preflight-fast-hosted
          EOF
"""
    assert module._has_needs_dep(block, "preflight-fast-hosted") is False


def test_has_needs_dep_supports_multiline_flow_style() -> None:
    module = _load_module()
    block = """  preflight-fast:
    needs: [
      preflight-fast-hosted,
      preflight-fast-fallback,
    ]
    runs-on: ubuntu-latest
"""
    assert module._has_needs_dep(block, "preflight-fast-hosted") is True
    assert module._has_needs_dep(block, "preflight-fast-fallback") is True


def test_has_needs_dep_supports_anchor_with_block_list_and_comments() -> None:
    module = _load_module()
    block = """  preflight-fast:
    needs: &preflight_needs
      - preflight-fast-hosted  # hosted chain
      - preflight-fast-fallback
    runs-on: ubuntu-latest
"""
    assert module._has_needs_dep(block, "preflight-fast-hosted") is True
    assert module._has_needs_dep(block, "preflight-fast-fallback") is True


def test_job_level_uses_target_accepts_trailing_comment() -> None:
    module = _load_module()
    block = """  preflight-fast-hosted:
    uses: ./.github/workflows/no-timeout.yml # delegate checks
"""
    assert module._job_level_uses_target(block) == "./.github/workflows/no-timeout.yml"


def test_global_rules_require_checkout_clean_true() -> None:
    module = _load_module()
    workflow = """name: CI
on:
  pull_request:
jobs:
      lint:
        runs-on: ubuntu-latest
        timeout-minutes: 5
        steps:
          - name: Checkout
        uses: actions/checkout@1234567890abcdef1234567890abcdef12345678
          - run: echo lint
  required-ci-secrets:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - run: python3 scripts/governance/check_required_ci_secrets.py --required GEMINI_API_KEY
"""
    failures: list[str] = []

    module._check_global_rules(
        Path("ci.yml"), workflow, dict(module._job_blocks(workflow)), failures
    )

    assert (
        "ci.yml:10: actions/checkout must declare with.clean: true on shared self-hosted runners"
        in failures
    )


def test_global_rules_require_pre_checkout_normalization_for_self_hosted_checkout() -> None:
    module = _load_module()
    workflow = """name: pre-commit
on:
  pull_request:
jobs:
  pre-commit-hosted:
    runs-on: [self-hosted, sourceharbor]
    timeout-minutes: 5
    steps:
      - name: Checkout
        uses: actions/checkout@1234567890abcdef1234567890abcdef12345678
        with:
          clean: true
"""
    failures: list[str] = []

    module._check_global_rules(
        Path("pre-commit.yml"), workflow, dict(module._job_blocks(workflow)), failures
    )

    assert (
        "pre-commit.yml:10: self-hosted checkout must be preceded by "
        "`Normalize self-hosted workspace (pre-checkout)`"
    ) in failures


def test_global_rules_accept_pre_checkout_normalization_for_self_hosted_checkout() -> None:
    module = _load_module()
    workflow = """name: pre-commit
on:
  pull_request:
jobs:
  pre-commit-hosted:
    runs-on: [self-hosted, sourceharbor]
    timeout-minutes: 5
    steps:
      - name: Normalize self-hosted workspace (pre-checkout)
        run: echo normalize
      - name: Checkout
        uses: actions/checkout@1234567890abcdef1234567890abcdef12345678
        with:
          clean: true
"""
    failures: list[str] = []

    module._check_global_rules(
        Path("pre-commit.yml"), workflow, dict(module._job_blocks(workflow)), failures
    )

    assert (
        "self-hosted checkout must be preceded by `Normalize self-hosted workspace (pre-checkout)`"
    ) not in "\n".join(failures)


def test_global_rules_forbid_checkout_workspace_tool_cache_paths() -> None:
    module = _load_module()
    workflow = """name: CI
on:
  pull_request:
env:
  CI_CACHE_ROOT: ${{ runner.temp }}/ci-cache
  PLAYWRIGHT_BROWSERS_PATH: ${{ github.workspace }}/.runtime-cache/tmp/ms-playwright
jobs:
      lint:
        runs-on: ubuntu-latest
        timeout-minutes: 5
        steps:
          - name: Checkout
        uses: actions/checkout@1234567890abcdef1234567890abcdef12345678
        with:
          clean: true
      - name: Cache Playwright browsers
        uses: actions/cache@1234567890abcdef1234567890abcdef12345678
        with:
          path: ${{ github.workspace }}/.runtime-cache/tmp/ms-playwright
  required-ci-secrets:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - run: python3 scripts/governance/check_required_ci_secrets.py --required GEMINI_API_KEY
"""
    failures: list[str] = []

    module._check_global_rules(
        Path("ci.yml"), workflow, dict(module._job_blocks(workflow)), failures
    )

    assert (
        "ci.yml:6: PLAYWRIGHT_BROWSERS_PATH must resolve under runner.temp/CI_CACHE_ROOT, not repo paths or ~/.cache"
        in failures
    )
    assert (
        "ci.yml:17: actions/cache path `${{ github.workspace }}/.runtime-cache/tmp/ms-playwright` must resolve under runner.temp/CI_CACHE_ROOT"
        in failures
    )


def test_global_rules_require_ci_cache_root_for_cached_workflows() -> None:
    module = _load_module()
    workflow = """name: CI
on:
  pull_request:
jobs:
      lint:
        runs-on: ubuntu-latest
        timeout-minutes: 5
        steps:
          - name: Checkout
        uses: actions/checkout@1234567890abcdef1234567890abcdef12345678
        with:
          clean: true
      - name: Cache uv
        uses: actions/cache@1234567890abcdef1234567890abcdef12345678
        with:
          path: ${{ runner.temp }}/ci-cache/uv
  required-ci-secrets:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - run: python3 scripts/governance/check_required_ci_secrets.py --required GEMINI_API_KEY
"""
    failures: list[str] = []

    module._check_global_rules(
        Path("ci.yml"), workflow, dict(module._job_blocks(workflow)), failures
    )

    assert (
        "ci.yml: workflows using actions/cache must declare CI_CACHE_ROOT under runner.temp"
        in failures
    )


def test_global_rules_reject_ci_concurrency_group_with_github_sha() -> None:
    module = _load_module()
    workflow = """name: CI
on:
  workflow_dispatch:
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}-${{ github.sha }}
  cancel-in-progress: true
jobs:
  required-ci-secrets:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - run: python3 scripts/governance/check_required_ci_secrets.py --required GEMINI_API_KEY
"""
    failures: list[str] = []

    module._check_global_rules(
        Path("ci.yml"), workflow, dict(module._job_blocks(workflow)), failures
    )

    assert (
        "ci.yml: top-level concurrency.group must not include github.sha; use a stable workflow/event/ref key"
        in failures
    )


def test_global_rules_allow_ci_concurrency_group_with_manual_run_id() -> None:
    module = _load_module()
    workflow = """name: CI
on:
  workflow_dispatch:
concurrency:
  group: ${{ github.event_name == 'workflow_dispatch' && format('ci-{0}-{1}-{2}', github.workflow, github.ref, github.run_id) || format('ci-{0}-{1}-{2}', github.workflow, github.event_name, github.ref) }}
  cancel-in-progress: true
jobs:
  required-ci-secrets:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - run: python3 scripts/governance/check_required_ci_secrets.py --required GEMINI_API_KEY
"""
    failures: list[str] = []

    module._check_global_rules(
        Path("ci.yml"), workflow, dict(module._job_blocks(workflow)), failures
    )

    assert (
        "ci.yml: top-level concurrency.group must not include github.sha; use a stable workflow/event/ref key"
        not in failures
    )


def test_ci_specific_rules_reject_runner_bootstrap_exact_name_pinning() -> None:
    module = _load_module()
    workflow_text = """concurrency:
  group: runner-health-demo
jobs:
  runner-bootstrap:
    steps:
      - run: echo "not a current-head closure proof"
"""
    blocks = {
        "runner-bootstrap": """  runner-bootstrap:
    runs-on: [self-hosted, sourceharbor]
    timeout-minutes: 30
    steps:
      - run: |
          EXPECTED_RUNNERS_SORTED="pool-core01-01,pool-core01-02"
          echo "must exactly match expected"
""",
    }
    failures: list[str] = []

    module._check_runner_health_specific_rules(workflow_text, blocks, failures)

    assert (
        "runner-health.yml: runner-bootstrap: must not hardcode exact org runner name lists; use label/pattern online thresholds"
        in failures
    )


def test_ci_specific_rules_require_runner_bootstrap_label_threshold_guard() -> None:
    module = _load_module()
    workflow_text = """concurrency:
  group: runner-health-demo
jobs:
  runner-bootstrap:
    steps:
      - run: echo "not a current-head closure proof"
"""
    blocks = {
        "runner-bootstrap": """  runner-bootstrap:
    runs-on: [self-hosted, sourceharbor]
    timeout-minutes: 30
    steps:
      - run: |
          MIN_ONLINE_CORE_RUNNERS=3
          online_count=3
""",
    }
    failures: list[str] = []

    module._check_runner_health_specific_rules(workflow_text, blocks, failures)

    assert (
        "runner-health.yml: runner-bootstrap: missing label-route online threshold guard for sourceharbor"
        in failures
    )


def test_ci_specific_rules_accept_runner_bootstrap_label_threshold_policy() -> None:
    module = _load_module()
    workflow_text = """concurrency:
  group: runner-health-demo
jobs:
  runner-bootstrap:
    steps:
      - run: echo "not a current-head closure proof"
"""
    blocks = {
        "runner-bootstrap": """  runner-bootstrap:
    runs-on: [self-hosted, sourceharbor]
    timeout-minutes: 30
    steps:
      - run: |
          MIN_ONLINE_CORE_RUNNERS="${MIN_ONLINE_CORE_RUNNERS:-3}"
          MIN_ONLINE_LABEL_RUNNERS="${MIN_ONLINE_LABEL_RUNNERS:-1}"
          label_online_count="$(gh api "orgs/${GH_ORG}/actions/runners" --jq "[.runners[] | select((.labels | map(.name) | index(\\"sourceharbor\\")) and .status==\\"online\\")] | length")"
""",
    }
    failures: list[str] = []

    module._check_runner_health_specific_rules(workflow_text, blocks, failures)

    assert (
        "runner-health.yml: runner-bootstrap: must not hardcode exact org runner name lists; use label/pattern online thresholds"
        not in failures
    )
    assert (
        "runner-health.yml: runner-bootstrap: missing pool-core online threshold guard (MIN_ONLINE_CORE_RUNNERS)"
        not in failures
    )
    assert (
        "runner-health.yml: runner-bootstrap: missing label-route online threshold guard for sourceharbor"
        not in failures
    )


def test_ci_specific_rules_aggregate_needs_must_not_be_satisfied_by_comment_text() -> None:
    module = _load_module()
    aggregate_block = """  aggregate-gate:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    if: always()
    needs:
      - quality-gate-pre-push
      - api-real-smoke
      - web-e2e
      - python-tests
    steps:
      - run: echo "- required-ci-secrets"
"""
    blocks = {
        "quality-gate-pre-push": "  quality-gate-pre-push:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n",
        "api-real-smoke": "  api-real-smoke:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n",
        "web-e2e": "  web-e2e:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n",
        "python-tests": "  python-tests:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n",
        "aggregate-gate": aggregate_block,
    }
    failures: list[str] = []

    module._check_ci_specific_rules(blocks, failures)

    assert "ci.yml: aggregate-gate: missing needs dependency `required-ci-secrets`" in failures


def test_ci_specific_rules_aggregate_must_validate_required_ci_secrets_result() -> None:
    module = _load_module()
    aggregate_block = """  aggregate-gate:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    if: always()
    needs:
      - required-ci-secrets
      - quality-gate-pre-push
      - api-real-smoke
      - web-e2e
      - python-tests
    steps:
      - run: echo "aggregate"
"""
    blocks = {
        "quality-gate-pre-push": "  quality-gate-pre-push:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n",
        "api-real-smoke": "  api-real-smoke:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n",
        "web-e2e": "  web-e2e:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n",
        "python-tests": "  python-tests:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n",
        "aggregate-gate": aggregate_block,
    }
    failures: list[str] = []

    module._check_ci_specific_rules(blocks, failures)

    assert (
        "ci.yml: aggregate-gate: must map required-ci-secrets job result into runtime gate logic (results[required_ci_secrets]=...)"
        in failures
    )
    assert (
        "ci.yml: aggregate-gate: must hard-fail when required-ci-secrets result is not success"
        in failures
    )


def test_ci_specific_rules_accepts_stricter_quality_gate_mutation_thresholds() -> None:
    module = _load_module()
    qg_block = """  quality-gate-pre-push:
    runs-on: ubuntu-latest
    container:
      image: ${{ needs.ci-contract.outputs.standard_image_ref }}
    timeout-minutes: 5
    steps:
      - run: |
          ./bin/strict-ci --mode pre-push \
            --ci-dedupe 1 \
            --skip-mutation 1 \
            --mutation-min-score 0.70 \
            --mutation-min-effective-ratio 0.30 \
            --mutation-max-no-tests-ratio 0.70
"""
    blocks = {
        "quality-gate-pre-push": qg_block,
        "api-real-smoke": "  api-real-smoke:\n    runs-on: ubuntu-latest\n    container:\n      image: ${{ needs.ci-contract.outputs.standard_image_ref }}\n    timeout-minutes: 5\n",
        "pr-llm-real-smoke": "  pr-llm-real-smoke:\n    runs-on: ubuntu-latest\n    container:\n      image: ${{ needs.ci-contract.outputs.standard_image_ref }}\n    timeout-minutes: 5\n",
        "web-test-build": "  web-test-build:\n    runs-on: ubuntu-latest\n    container:\n      image: ${{ needs.ci-contract.outputs.standard_image_ref }}\n    timeout-minutes: 5\n",
        "web-e2e": "  web-e2e:\n    runs-on: ubuntu-latest\n    container:\n      image: ${{ needs.ci-contract.outputs.standard_image_ref }}\n    timeout-minutes: 5\n",
        "python-tests": "  python-tests:\n    runs-on: ubuntu-latest\n    container:\n      image: ${{ needs.ci-contract.outputs.standard_image_ref }}\n    timeout-minutes: 5\n",
        "aggregate-gate": """  aggregate-gate:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    if: always()
    needs:
      - required-ci-secrets
      - quality-gate-pre-push
      - api-real-smoke
      - web-e2e
      - python-tests
    steps:
      - run: echo "needs.required-ci-secrets.result"
""",
        "preflight-fast": "",
        "live-smoke": """  live-smoke:
    container:
      image: ${{ needs.ci-contract.outputs.standard_image_ref }}
    services:
      postgres:
    steps:
      - run: ./bin/strict-ci --mode live-smoke
      - run: echo 'GEMINI_API_KEY'
      - run: echo 'RESEND_API_KEY'
      - run: echo 'YOUTUBE_API_KEY'
""",
    }
    failures: list[str] = []

    module._check_ci_specific_rules(blocks, failures)

    assert "ci.yml: quality-gate-pre-push: mutation threshold must be at least 0.64" not in failures
    assert (
        "ci.yml: quality-gate-pre-push: mutation effective ratio floor must be at least 0.27"
        not in failures
    )
    assert (
        "ci.yml: quality-gate-pre-push: mutation no-tests ratio ceiling must be at most 0.72"
        not in failures
    )


def test_ci_specific_rules_rejects_weaker_quality_gate_mutation_thresholds() -> None:
    module = _load_module()
    qg_block = """  quality-gate-pre-push:
    runs-on: ubuntu-latest
    container:
      image: ${{ needs.ci-contract.outputs.standard_image_ref }}
    timeout-minutes: 5
    steps:
      - run: |
          ./bin/strict-ci --mode pre-push \
            --ci-dedupe 1 \
            --skip-mutation 1 \
            --mutation-min-score 0.61 \
            --mutation-min-effective-ratio 0.24 \
            --mutation-max-no-tests-ratio 0.76
"""
    blocks = {
        "quality-gate-pre-push": qg_block,
        "api-real-smoke": "  api-real-smoke:\n    runs-on: ubuntu-latest\n    container:\n      image: ${{ needs.ci-contract.outputs.standard_image_ref }}\n    timeout-minutes: 5\n",
        "pr-llm-real-smoke": "  pr-llm-real-smoke:\n    runs-on: ubuntu-latest\n    container:\n      image: ${{ needs.ci-contract.outputs.standard_image_ref }}\n    timeout-minutes: 5\n",
        "web-test-build": "  web-test-build:\n    runs-on: ubuntu-latest\n    container:\n      image: ${{ needs.ci-contract.outputs.standard_image_ref }}\n    timeout-minutes: 5\n",
        "web-e2e": "  web-e2e:\n    runs-on: ubuntu-latest\n    container:\n      image: ${{ needs.ci-contract.outputs.standard_image_ref }}\n    timeout-minutes: 5\n",
        "python-tests": "  python-tests:\n    runs-on: ubuntu-latest\n    container:\n      image: ${{ needs.ci-contract.outputs.standard_image_ref }}\n    timeout-minutes: 5\n",
        "aggregate-gate": """  aggregate-gate:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    if: always()
    needs:
      - required-ci-secrets
      - quality-gate-pre-push
      - api-real-smoke
      - web-e2e
      - python-tests
    steps:
      - run: echo "needs.required-ci-secrets.result"
""",
        "preflight-fast": "",
        "live-smoke": """  live-smoke:
    container:
      image: ${{ needs.ci-contract.outputs.standard_image_ref }}
    services:
      postgres:
    steps:
      - run: ./bin/strict-ci --mode live-smoke
      - run: echo 'GEMINI_API_KEY'
      - run: echo 'RESEND_API_KEY'
      - run: echo 'YOUTUBE_API_KEY'
""",
    }
    failures: list[str] = []

    module._check_ci_specific_rules(blocks, failures)

    assert "ci.yml: quality-gate-pre-push: mutation threshold must be at least 0.64" in failures
    assert (
        "ci.yml: quality-gate-pre-push: mutation effective ratio floor must be at least 0.27"
        in failures
    )
    assert (
        "ci.yml: quality-gate-pre-push: mutation no-tests ratio ceiling must be at most 0.72"
        in failures
    )


def test_python_tests_job_calls_repo_script_inside_strict_ci_entry() -> None:
    workflow = (_repo_root() / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "UV_PROJECT_ENVIRONMENT:" in workflow
    assert "python3 scripts/governance/check_env_contract.py --strict" in workflow
    assert "python3 scripts/governance/check_test_assertions.py" in workflow
    assert "bash scripts/ci/python_tests.sh" in workflow


def test_python_tests_pipeline_smoke_syncs_dependencies_before_pytest() -> None:
    workflow = (_repo_root() / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    env_index = workflow.index("UV_PROJECT_ENVIRONMENT:")
    pytest_index = workflow.index("bash scripts/ci/python_tests.sh")
    assert env_index < pytest_index


def test_ci_python_tests_script_preserves_backend_coverage_and_junit_contract() -> None:
    script = (_repo_root() / "scripts" / "ci" / "python_tests.sh").read_text(encoding="utf-8")

    assert "mkdir -p .runtime-cache" in script
    assert "uv sync --frozen --extra dev --extra e2e" in script
    assert script.index("uv sync --frozen --extra dev --extra e2e") < script.index(
        "uv run pytest apps/worker/tests apps/api/tests apps/mcp/tests -q -rA"
    )
    assert 'PYTEST_XDIST_WORKERS="${PYTHON_TESTS_XDIST_WORKERS:-2}"' in script
    assert 'PYTEST_XDIST_ARGS=(-n "$PYTEST_XDIST_WORKERS")' in script
    assert (
        'uv run pytest apps/worker/tests apps/api/tests apps/mcp/tests -q -rA "${PYTEST_XDIST_ARGS[@]}"'
        in script
    )
    assert 'PYTHONPATH="$PWD:$PWD/apps/worker"' in script
    assert "DATABASE_URL='sqlite+pysqlite:///:memory:'" in script
    assert "COVERAGE_FILE=.runtime-cache/reports/python/.coverage" in script
    assert 'for marker in ("/apps/", "/integrations/", "/packages/", "/scripts/")' in script
    assert (
        "def merge_file_rows(conn: sqlite3.Connection, source_id: int, target_id: int) -> None:"
        in script
    )
    assert '"update file set path = ? where id = ?",' in script
    assert "(replacement, file_id)," in script
    assert (
        "find .runtime-cache/reports/python -maxdepth 1 -type f -name '.coverage*.meta.json' -delete"
        in script
    )
    assert script.index(
        "find .runtime-cache/reports/python -maxdepth 1 -type f -name '.coverage*.meta.json' -delete"
    ) < script.index("uv run coverage combine --keep .runtime-cache/reports/python >/dev/null")
    assert (
        "find .runtime-cache/reports/python -maxdepth 1 -type f -name '.coverage.*' ! -name '*.meta.json'"
        in script
    )
    assert (
        "COVERAGE_FILE=.runtime-cache/reports/python/.coverage uv run coverage combine --keep .runtime-cache/reports/python >/dev/null"
        in script
    )
    assert script.index(
        "uv run coverage combine --keep .runtime-cache/reports/python >/dev/null"
    ) < script.index("from common import write_runtime_metadata")
    assert (
        "find .runtime-cache/reports/python -maxdepth 1 -type f -name '.coverage.*' -delete"
        in script
    )
    assert script.index(
        "find .runtime-cache/reports/python -maxdepth 1 -type f -name '.coverage.*' -delete"
    ) < script.index("from common import write_runtime_metadata")
    assert "rm -f .runtime-cache/reports/python/.coverage.meta.json" in script
    assert "--data-file=.runtime-cache/reports/python/.coverage" in script
    assert (
        "apps/worker/worker/pipeline/orchestrator.py,*/apps/worker/worker/pipeline/orchestrator.py"
        in script
    )
    assert (
        "apps/worker/worker/pipeline/policies.py,*/apps/worker/worker/pipeline/policies.py"
        in script
    )
    assert "apps/worker/worker/pipeline/runner.py,*/apps/worker/worker/pipeline/runner.py" in script
    assert "apps/worker/worker/pipeline/types.py,*/apps/worker/worker/pipeline/types.py" in script
    assert "apps/api/app/routers/ingest.py,*/apps/api/app/routers/ingest.py" in script
    assert "--cov-report=xml:.runtime-cache/reports/python/python-coverage.xml" in script
    assert "--junitxml=.runtime-cache/reports/python/python-tests-junit.xml" in script
    assert ".runtime-cache/logs/tests/python-tests.log" in script
    assert ".runtime-cache/logs/tests/python-coverage-worker-core.log" in script
    assert ".runtime-cache/logs/tests/python-coverage-api-core.log" in script
    assert '("coverage.json", "python-coverage-summary")' in script
    assert '("python-coverage.xml", "python-coverage-xml")' in script
    assert '("python-tests-junit.xml", "python-tests-junit")' in script
    assert "python skip guard passed" in script
    assert script.count("python3 scripts/runtime/clean_source_runtime_residue.py --apply") >= 3


def test_strict_ci_entry_python_tests_disables_xdist_by_default_for_repo_side_receipt() -> None:
    script = (_repo_root() / "scripts" / "ci" / "strict_entry.sh").read_text(encoding="utf-8")

    assert "python-tests)" in script
    assert (
        "PYTHON_TESTS_XDIST_WORKERS=${PYTHON_TESTS_XDIST_WORKERS:-0} ./scripts/ci/python_tests.sh"
        in script
    )


def test_bootstrap_strict_runtime_uses_run_scoped_hash_file() -> None:
    script = (_repo_root() / "scripts" / "ci" / "bootstrap_strict_ci_runtime.sh").read_text(
        encoding="utf-8"
    )

    assert "mkdir -p .runtime-cache/run/strict-ci" in script
    assert 'web_hash_file=".runtime-cache/run/strict-ci/web-${platform_id}.sha256"' in script


def test_api_real_smoke_job_calls_repo_script_inside_strict_ci_entry() -> None:
    workflow = (_repo_root() / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "api-real-smoke" not in workflow
    assert 'SOURCE_HARBOR_API_KEY: "ci-smoke-write-token"' not in workflow
    assert 'WEB_ACTION_SESSION_TOKEN: "ci-smoke-write-token"' not in workflow


def test_web_e2e_job_calls_repo_script_inside_strict_ci_entry() -> None:
    workflow = (_repo_root() / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    script = (_repo_root() / "scripts" / "ci" / "web_e2e.sh").read_text(encoding="utf-8")

    assert "web-e2e" not in workflow
    assert 'DATABASE_URL="${DATABASE_URL:-}"' in script
    assert 'db_url="postgresql+psycopg://' not in script
    assert "ensure_node_toolchain" in script
    assert 'source "$ROOT_DIR/scripts/ci/bootstrap_strict_ci_runtime.sh"' in script
    assert "install_web_npm_wrapper" not in script
    assert 'wait_for_tcp "$WEB_E2E_TEMPORAL_PORT" "temporal web-e2e" 60' in script
    assert script.index("start_temporal") < script.index("start_api")
    assert script.index("start_temporal") < script.index("start_worker")
    assert "describe_task_queue" in script
    assert "TASK_QUEUE_TYPE_WORKFLOW" in script
    assert "TASK_QUEUE_TYPE_ACTIVITY" in script
    assert "web-e2e worker pollers detected on task queue sourceharbor-worker" in script
    assert "no task queue pollers within 30s" in script
    assert ".runtime-cache/logs/tests/web-e2e-api.log" in script
    assert ".runtime-cache/logs/tests/web-e2e-worker.log" in script
    assert ".runtime-cache/logs/tests/web-e2e-temporal.log" in script
    assert ".runtime-cache/reports/tests/web-e2e-junit-" in script


def test_quality_gate_and_live_smoke_jobs_use_strict_ci_entry_and_contract_container() -> None:
    workflow = (_repo_root() / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "./bin/strict-ci" not in workflow
    assert "--mode pre-push" not in workflow
    assert "--mode live-smoke" not in workflow
    assert "image: ${{ needs.ci-contract.outputs.standard_image_ref }}" not in workflow


def test_runner_bootstrap_uses_minimum_online_runner_capacity_instead_of_exact_name_match() -> None:
    workflow = _repo_root() / ".github" / "workflows" / "runner-health.yml"

    assert workflow.exists() is False


def test_docker_dependent_required_jobs_route_to_core02_runner_subset() -> None:
    workflow = (_repo_root() / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "self-hosted" not in workflow
    assert "core02" not in workflow
    assert workflow.count("runs-on: ubuntu-latest") == 2


def test_ci_workflow_uses_single_reusable_preflight_fast_job() -> None:
    workflow = (_repo_root() / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "  python-tests:\n" in workflow
    assert "  web-lint:\n" in workflow
    assert "uses: ./.github/workflows/_preflight-fast-steps.yml" not in workflow
    assert "preflight-fast-hosted" not in workflow
    assert "preflight-fast-fallback" not in workflow


@dataclass
class _CollectionConfig:
    hook: Any

    def getoption(self, name: str) -> str:
        assert name == "--web-e2e-use-mock-api"
        return ""


@dataclass
class _CollectedTestItem:
    nodeid: str
    fixturenames: list[str] = field(default_factory=list)
    keywords: dict[str, Any] = field(default_factory=dict)
    config: Any = None


def test_web_e2e_mock_only_cases_are_deselected_for_real_api_collection() -> None:
    _install_web_e2e_import_stubs()
    conftest_path = _repo_root() / "apps" / "web" / "tests" / "e2e" / "conftest.py"
    spec = importlib.util.spec_from_file_location("web_e2e_conftest", conftest_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    deselected: list[_CollectedTestItem] = []

    def _pytest_deselected(items: list[_CollectedTestItem]) -> None:
        deselected.extend(items)

    config = _CollectionConfig(hook=SimpleNamespace(pytest_deselected=_pytest_deselected))
    items = [
        _CollectedTestItem(
            nodeid="apps/web/tests/e2e/test_dashboard.py::test_dashboard_empty_subscription_and_tasks_links_with_mock_api",
            config=config,
        ),
        _CollectedTestItem(
            nodeid="apps/web/tests/e2e/test_feed.py::test_feed_filter_submit_and_clear",
            config=config,
        ),
    ]

    module.pytest_collection_modifyitems(config, items)

    assert [item.nodeid for item in items] == [
        "apps/web/tests/e2e/test_feed.py::test_feed_filter_submit_and_clear"
    ]
    assert [item.nodeid for item in deselected] == [
        "apps/web/tests/e2e/test_dashboard.py::test_dashboard_empty_subscription_and_tasks_links_with_mock_api"
    ]
