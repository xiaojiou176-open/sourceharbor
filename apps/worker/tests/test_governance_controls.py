from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_governance_control_plane_files_exist_and_are_populated() -> None:
    root = _repo_root()
    config_dir = root / "config" / "governance"
    required = [
        "root-allowlist.json",
        "root-denylist.json",
        "public-entrypoints.json",
        "runtime-outputs.json",
        "disk-space-governance.json",
        "logging-contract.json",
        "dependency-boundaries.json",
        "active-upstreams.json",
        "upstream-templates.json",
        "upstream-compat-matrix.json",
    ]

    for name in required:
        path = config_dir / name
        assert path.is_file(), f"missing governance config: {name}"
        payload = json.loads(path.read_text(encoding="utf-8"))
        version = payload.get("version")
        assert isinstance(version, int) and version >= 1

    runtime_outputs = json.loads((config_dir / "runtime-outputs.json").read_text(encoding="utf-8"))
    assert set(runtime_outputs["subdirectories"]) == {
        "run",
        "logs",
        "reports",
        "evidence",
        "tmp",
    }

    logging_contract = json.loads(
        (config_dir / "logging-contract.json").read_text(encoding="utf-8")
    )
    assert set(logging_contract["channels"]) == {
        "app",
        "components",
        "tests",
        "governance",
        "infra",
        "upstreams",
    }

    dependency_boundaries = json.loads(
        (config_dir / "dependency-boundaries.json").read_text(encoding="utf-8")
    )
    assert dependency_boundaries["internal_roots"] == ["apps.", "integrations."]
    for entry in dependency_boundaries["python_rules"]:
        assert "allow_internal_prefixes" in entry
    for entry in dependency_boundaries["frontend_rules"]:
        assert "allow_import_prefixes" in entry
    assert dependency_boundaries["package_purity_rules"]

    upstreams = json.loads((config_dir / "active-upstreams.json").read_text(encoding="utf-8"))
    for entry in upstreams["entries"]:
        assert "evidence_artifact" in entry
        assert "license" in entry
        assert "risk_class" in entry
        assert "integration_surface" in entry
        assert "private_coupling_risk" in entry
        assert "security_posture" in entry

    templates = json.loads((config_dir / "upstream-templates.json").read_text(encoding="utf-8"))
    for entry in templates["entries"]:
        assert entry["kind"] in {"vendor", "fork", "patch"}

    matrix = json.loads((config_dir / "upstream-compat-matrix.json").read_text(encoding="utf-8"))
    for row in matrix["matrix"]:
        assert "verification_entrypoint" in row
        assert "evidence_artifact" in row
        assert "verification_status" in row
        assert "verification_artifacts" in row

    pyproject_text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert '"integrations"' in pyproject_text


def test_governance_gate_script_wires_all_terminal_checks() -> None:
    script = (_repo_root() / "scripts" / "governance" / "gate.sh").read_text(encoding="utf-8")

    assert "--mode pre-commit|pre-push|ci|audit" in script
    assert "python3 scripts/runtime/clean_source_runtime_residue.py --apply" in script
    assert "python3 scripts/governance/check_root_allowlist.py" in script
    assert "python3 scripts/governance/check_public_entrypoint_manifests.py" in script
    assert "python3 scripts/governance/check_public_entrypoint_references.py" in script
    assert "python3 scripts/governance/check_runtime_outputs.py" in script
    assert "python3 scripts/governance/check_disk_space_governance.py" in script
    assert "python3 scripts/governance/check_runtime_artifact_writer_coverage.py" in script
    assert "python3 scripts/governance/check_runtime_metadata_completeness.py" in script
    assert "python3 scripts/governance/check_governance_language.py" in script
    assert "python3 scripts/governance/check_dependency_boundaries.py" in script
    assert "python3 scripts/governance/check_logging_contract.py" in script
    assert "python3 scripts/governance/check_run_manifest_completeness.py" in script
    assert "python3 scripts/governance/check_eval_assets.py" in script
    assert "python3 scripts/governance/check_upstream_governance.py" in script
    assert "python3 scripts/governance/check_upstream_same_run_cohesion.py" in script


def test_public_entrypoint_registry_tracks_current_public_workflows() -> None:
    registry = (_repo_root() / "config" / "governance" / "public-entrypoints.json").read_text(
        encoding="utf-8"
    )

    assert '".github/workflows/ci.yml"' in registry
    assert '".github/workflows/build-public-api-image.yml"' in registry
    assert '".github/workflows/build-ci-standard-image.yml"' in registry
    assert '".github/workflows/release-evidence-attest.yml"' in registry
    assert "monthly-governance-audit" not in registry
    assert "vendor-governance" not in registry


def test_upstream_verify_entrypoint_includes_same_run_cohesion_guard() -> None:
    script = (_repo_root() / "bin" / "upstream-verify").read_text(encoding="utf-8")

    assert "python3 scripts/governance/check_upstream_same_run_cohesion.py" in script


def test_python_tests_public_entrypoint_uses_managed_uv_environment() -> None:
    root = _repo_root()
    entrypoint = (root / "bin" / "python-tests").read_text(encoding="utf-8")
    repo_side_entrypoint = (root / "bin" / "repo-side-strict-ci").read_text(encoding="utf-8")
    script = (_repo_root() / "scripts" / "ci" / "python_tests.sh").read_text(encoding="utf-8")
    public_entrypoints = (
        _repo_root() / "config" / "governance" / "public-entrypoints.json"
    ).read_text(encoding="utf-8")

    assert 'sourceharbor_entrypoint_bootstrap tests python-tests "" "$@"' in entrypoint
    assert 'exec "$ROOT_DIR/scripts/ci/python_tests.sh" "$@"' in entrypoint
    assert 'source "$ROOT_DIR/scripts/lib/standard_env.sh"' in script
    assert 'ensure_external_uv_project_environment "$ROOT_DIR"' in script
    assert "clean_source_runtime_residue.py --apply" in script
    assert '"bin/python-tests"' in public_entrypoints
    assert '"bin/repo-side-strict-ci"' in public_entrypoints
    assert "if docker info >/dev/null 2>&1; then" in repo_side_entrypoint
    assert (
        'exec "$ROOT_DIR/bin/strict-ci" --debug-build "${FORWARD_ARGS[@]}"' in repo_side_entrypoint
    )
    assert "host fallback only supports --mode pre-push" in repo_side_entrypoint
    assert 'source "$ROOT_DIR/scripts/ci/bootstrap_strict_ci_runtime.sh"' in repo_side_entrypoint
    assert 'exec "$ROOT_DIR/scripts/quality_gate.sh" \\' in repo_side_entrypoint


def test_public_entrypoint_manifest_checker_loads_registry_for_python_tests() -> None:
    script = (
        _repo_root() / "scripts" / "governance" / "check_public_entrypoint_manifests.py"
    ).read_text(encoding="utf-8")

    assert 'load_governance_json("public-entrypoints.json")' in script
    assert "required_public_entrypoints" in script


def test_pr_llm_real_smoke_uses_managed_write_token_and_dev_api_entrypoint() -> None:
    script = (_repo_root() / "scripts" / "ci" / "pr_llm_real_smoke.sh").read_text(encoding="utf-8")

    assert 'SMOKE_WRITE_TOKEN="${SOURCE_HARBOR_API_KEY:-sourceharbor-local-dev-token}"' in script
    assert 'export SOURCE_HARBOR_API_KEY="${SOURCE_HARBOR_API_KEY:-$SMOKE_WRITE_TOKEN}"' in script
    assert (
        'export WEB_ACTION_SESSION_TOKEN="${WEB_ACTION_SESSION_TOKEN:-$SMOKE_WRITE_TOKEN}"'
        in script
    )
    assert "./scripts/runtime/dev_api.sh --host 127.0.0.1 --port 18081 --no-reload" in script


def test_runtime_artifact_writer_coverage_tracks_runtime_target_variables() -> None:
    script = (
        _repo_root() / "scripts" / "governance" / "check_runtime_artifact_writer_coverage.py"
    ).read_text(encoding="utf-8")

    assert "RUNTIME_ASSIGN_RE" in script
    assert "WRITE_TARGET_RE" in script


def test_hosted_workflow_set_is_small_and_explicit() -> None:
    workflow_dir = _repo_root() / ".github" / "workflows"
    names = sorted(path.name for path in workflow_dir.glob("*.yml"))

    assert names == [
        "build-ci-standard-image.yml",
        "build-public-api-image.yml",
        "ci.yml",
        "codeql.yml",
        "dependency-review.yml",
        "pre-commit.yml",
        "release-evidence-attest.yml",
        "trivy.yml",
        "trufflehog.yml",
        "zizmor.yml",
    ]


def test_root_dirtiness_guard_also_protects_runtime_root_closure() -> None:
    script = (
        _repo_root() / "scripts" / "governance" / "check_root_dirtiness_after_tasks.py"
    ).read_text(encoding="utf-8")

    assert "_runtime_root_unknown_children" in script
    assert "runtime root contains undeclared direct children" in script


def test_runtime_cache_maintenance_is_hardened_for_tmp_semantics_and_races() -> None:
    script = (_repo_root() / "scripts" / "runtime" / "prune_runtime_cache.py").read_text(
        encoding="utf-8"
    )

    assert "def _default_created_at" in script
    assert "def _runtime_age_hours" in script
    assert 'if name == "tmp":' in script
    assert '"freshness_window_hours": None' in script
    assert "except FileNotFoundError" in script


def test_runtime_and_logging_contracts_reference_runtime_cache_root() -> None:
    runtime_outputs = (_repo_root() / "config" / "governance" / "runtime-outputs.json").read_text(
        encoding="utf-8"
    )
    logging_contract = (_repo_root() / "config" / "governance" / "logging-contract.json").read_text(
        encoding="utf-8"
    )
    readme = (_repo_root() / "README.md").read_text(encoding="utf-8")
    full_stack = (_repo_root() / "scripts" / "runtime" / "full_stack.sh").read_text(
        encoding="utf-8"
    )

    assert '".runtime-cache"' in runtime_outputs
    assert '".runtime-cache/logs/' in logging_contract
    assert ".runtime-cache/logs/components/full-stack" in readme
    assert 'LOG_DIR="$ROOT_DIR/.runtime-cache/logs/components/full-stack"' in full_stack
    assert "legacy_runtime_patterns" not in runtime_outputs


def test_standard_image_build_path_declares_repository_source_metadata() -> None:
    root = _repo_root()
    dockerfile = (root / ".devcontainer" / "Dockerfile").read_text(encoding="utf-8")
    build_script = (root / "scripts" / "ci" / "build_standard_image.sh").read_text(encoding="utf-8")

    assert (
        'LABEL org.opencontainers.image.source="https://github.com/xiaojiou176-open/sourceharbor"'
        in dockerfile
    )
    assert '--label "org.opencontainers.image.source=${source_repository_url}"' in build_script


def test_governance_language_gate_keeps_llm_prompt_builders_english_first() -> None:
    root = _repo_root()
    script = (root / "scripts" / "governance" / "check_governance_language.py").read_text(
        encoding="utf-8"
    )

    assert '"apps/worker/worker/pipeline/steps/llm_prompts.py"' in script
    strict_section = script.split("STRICT_ENGLISH_PATHS =", 1)[1].split(
        "PRODUCT_OUTPUT_LOCALE_ALLOWLIST_PATHS =", 1
    )[0]
    allowlist_section = script.split("PRODUCT_OUTPUT_LOCALE_ALLOWLIST_PATHS =", 1)[1]
    assert '"apps/worker/worker/pipeline/steps/llm_prompts.py"' in strict_section
    assert '"apps/worker/worker/pipeline/steps/llm_prompts.py"' not in allowlist_section


def test_shell_logging_helper_contract_exists_and_is_wired() -> None:
    root = _repo_root()
    helper = (root / "scripts" / "runtime" / "logging.sh").read_text(encoding="utf-8")
    governance_gate = (root / "scripts" / "governance" / "gate.sh").read_text(encoding="utf-8")
    full_stack = (root / "scripts" / "runtime" / "full_stack.sh").read_text(encoding="utf-8")
    api_real_smoke = (root / "scripts" / "ci" / "api_real_smoke_local.sh").read_text(
        encoding="utf-8"
    )
    smoke_llm_real = (root / "scripts" / "ci" / "smoke_llm_real_local.sh").read_text(
        encoding="utf-8"
    )
    external_smoke = (root / "scripts" / "ci" / "external_playwright_smoke.sh").read_text(
        encoding="utf-8"
    )

    assert "sourceharbor_log_init()" in helper
    assert "scripts/runtime/log_jsonl_event.py" in helper
    assert 'source "$ROOT_DIR/scripts/runtime/logging.sh"' in governance_gate
    assert 'sourceharbor_log_init "governance"' in governance_gate
    assert 'sourceharbor_log_init "components" "$SCRIPT_NAME"' in full_stack
    assert 'sourceharbor_log_init "tests" "$SCRIPT_NAME"' in api_real_smoke
    assert 'sourceharbor_log_init "tests" "$SCRIPT_NAME"' in smoke_llm_real
    assert 'sourceharbor_log_init "tests" "$SCRIPT_NAME"' in external_smoke
    assert 'source "$ROOT_DIR/scripts/lib/load_env.sh"' in external_smoke
    assert 'source "$ROOT_DIR/scripts/lib/standard_env.sh"' in external_smoke
    assert 'load_repo_env "$ROOT_DIR" "$SCRIPT_NAME"' in external_smoke
    assert 'ensure_external_uv_project_environment "$ROOT_DIR"' in external_smoke


def test_runtime_jsonl_logging_script_emits_required_fields(tmp_path: Path) -> None:
    root = _repo_root()
    output_path = tmp_path / "governance.jsonl"

    subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "runtime" / "log_jsonl_event.py"),
            "--path",
            str(output_path),
            "--run-id",
            "run-123",
            "--trace-id",
            "trace-123",
            "--request-id",
            "req-123",
            "--component",
            "governance-gate",
            "--channel",
            "governance",
            "--event",
            "start",
            "--severity",
            "info",
            "--message",
            "hello",
        ],
        check=True,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8").strip())
    assert payload["run_id"] == "run-123"
    assert payload["trace_id"] == "trace-123"
    assert payload["request_id"] == "req-123"
    assert payload["component"] == "governance-gate"
    assert payload["channel"] == "governance"
    assert payload["event"] == "start"
    assert payload["severity"] == "info"
    assert payload["ts"]


def test_logging_correlation_gate_tracks_worker_and_mcp_app_surfaces() -> None:
    script = (
        _repo_root() / "scripts" / "governance" / "check_log_correlation_completeness.py"
    ).read_text(encoding="utf-8")

    assert "ADDITIONAL_APP_CORRELATION_TARGETS" in script
    assert ".runtime-cache/logs/app/worker-commands.jsonl" in script
    assert ".runtime-cache/logs/app/mcp-api.jsonl" in script


def test_logging_contract_tracks_optional_app_surfaces() -> None:
    contract = json.loads(
        (_repo_root() / "config" / "governance" / "logging-contract.json").read_text(
            encoding="utf-8"
        )
    )
    optional_targets = contract.get("optional_sample_targets", {})
    assert "app" in optional_targets
    assert ".runtime-cache/logs/app/worker-commands.jsonl" in optional_targets["app"]
    assert ".runtime-cache/logs/app/mcp-api.jsonl" in optional_targets["app"]


def test_render_manifest_tracks_current_generated_docs() -> None:
    manifest = json.loads(
        (_repo_root() / "config" / "docs" / "render-manifest.json").read_text(encoding="utf-8")
    )
    generated_docs = manifest.get("generated_docs", [])
    paths = {entry.get("path") for entry in generated_docs if isinstance(entry, dict)}
    assert paths == {
        "docs/generated/governance-dashboard.md",
        "docs/generated/ci-topology.md",
        "docs/generated/required-checks.md",
        "docs/generated/external-lane-truth-entry.md",
    }


def test_ghcr_readiness_script_tracks_manifest_probe() -> None:
    script = (
        _repo_root() / "scripts" / "ci" / "check_standard_image_publish_readiness.sh"
    ).read_text(encoding="utf-8")

    assert "probe_registry_manifest()" in script
    assert "manifest unknown" in script
    assert '"manifest_probe"' in script
    assert "https://ghcr.io/token" in script
    assert 'requested_scope = f"repository:{repo_path}:pull,push"' in script


def test_runtime_outputs_contract_has_no_legacy_ui_audit_children() -> None:
    runtime_outputs = json.loads(
        (_repo_root() / "config" / "governance" / "runtime-outputs.json").read_text(
            encoding="utf-8"
        )
    )
    serialized = json.dumps(runtime_outputs, ensure_ascii=False)

    assert '"ui-audit"' not in serialized
    assert '"ui-audit-runs"' not in serialized


def test_logging_sample_generator_and_contract_checker_pass() -> None:
    root = _repo_root()

    subprocess.run(
        [sys.executable, str(root / "scripts" / "governance" / "generate_logging_samples.py")],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [sys.executable, str(root / "scripts" / "governance" / "check_logging_contract.py")],
        cwd=root,
        check=True,
    )


def test_disk_space_governance_defaults_and_docs_are_wired() -> None:
    root = _repo_root()
    policy = json.loads(
        (root / "config" / "governance" / "disk-space-governance.json").read_text(encoding="utf-8")
    )
    env_example = (root / ".env.example").read_text(encoding="utf-8")
    runbook = (root / "docs" / "runbook-local.md").read_text(encoding="utf-8")
    checker = (root / "scripts" / "governance" / "check_disk_space_governance.py").read_text(
        encoding="utf-8"
    )
    host_paths = (
        root / "scripts" / "governance" / "check_host_specific_path_references.py"
    ).read_text(encoding="utf-8")

    assert "audit_targets" in policy
    assert "cleanup_waves" in policy
    assert 'export CORE_POSTGRES_PORT="${CORE_POSTGRES_PORT:-15432}"' in env_example
    assert (
        'export DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:${CORE_POSTGRES_PORT}/sourceharbor"'
        in env_example
    )
    assert "export TEMPORAL_TASK_QUEUE=sourceharbor-worker" in env_example
    assert (
        'export SOURCE_HARBOR_CACHE_ROOT="${SOURCE_HARBOR_CACHE_ROOT:-$HOME/.cache/sourceharbor}"'
        in env_example
    )
    assert "${UV_PROJECT_ENVIRONMENT:-$SOURCE_HARBOR_CACHE_ROOT/project-venv}" in env_example
    assert "${PIPELINE_ARTIFACT_ROOT:-$SOURCE_HARBOR_CACHE_ROOT/artifacts}" in env_example
    assert "${PIPELINE_WORKSPACE_DIR:-$SOURCE_HARBOR_CACHE_ROOT/workspace}" in env_example
    assert (
        "${SOURCE_HARBOR_CHROME_USER_DATA_DIR:-$SOURCE_HARBOR_CACHE_ROOT/browser/chrome-user-data}"
        in env_example
    )
    assert "${SOURCE_HARBOR_CHROME_PROFILE_DIR:-Profile 1}" in env_example
    assert "${SOURCE_HARBOR_CHROME_CDP_PORT:-9339}" in env_example
    assert "$HOME/.sourceharbor" not in env_example
    assert "video-digestor" not in env_example
    assert "disk-space-governance.md" in runbook
    assert "[disk-space-governance]" in checker
    assert ".cache/sourceharbor" in host_paths
