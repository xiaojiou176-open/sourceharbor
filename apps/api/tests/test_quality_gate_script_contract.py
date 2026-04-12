from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_quality_gate_preserves_required_existing_semantics() -> None:
    script = (_repo_root() / "scripts" / "governance" / "quality_gate.sh").read_text(
        encoding="utf-8"
    )

    assert 'MUTATION_MIN_SCORE="0.64"' in script
    assert 'MUTATION_MIN_EFFECTIVE_RATIO="0.27"' in script
    assert 'MUTATION_MAX_NO_TESTS_RATIO="0.72"' in script
    assert "Coverage thresholds: total >= 95%, core modules >= 95%." in script
    assert '"LIVE_SMOKE_REQUIRE_SECRETS": "1"' in script
    assert "uv run --with ruff ruff check apps/api apps/worker apps/mcp" in script
    assert "WEB_RUNTIME_WEB_DIR" in script
    assert "run test:coverage" in script
    assert "python3 scripts/governance/check_docs_governance.py" in script
    assert "bash scripts/governance_gate.sh --mode pre-commit" in script
    assert "bash scripts/governance_gate.sh --mode pre-push" in script
    assert 'python3 "$ROOT_DIR/scripts/governance/check_mutation_stats.py"' in script
    assert 'root_dirtiness_snapshot="$TMP_DIR/root-before.json"' in script
    assert (
        'python3 "$ROOT_DIR/scripts/governance/check_root_dirtiness_after_tasks.py" --write-snapshot "$root_dirtiness_snapshot"'
        in script
    )
    assert (
        'python3 "$ROOT_DIR/scripts/governance/check_root_dirtiness_after_tasks.py" --compare-snapshot "$root_dirtiness_snapshot"'
        in script
    )
    assert 'if [[ "${SOURCE_HARBOR_IN_STANDARD_ENV:-0}" == "1" ]]; then' in script
    assert "host.docker.internal:5432/postgres" in script
    assert "host.docker.internal:7233" in script


def test_quality_gate_remains_a_pure_gate_runner_without_owning_container_reexec() -> None:
    script = (_repo_root() / "scripts" / "governance" / "quality_gate.sh").read_text(
        encoding="utf-8"
    )

    assert 'CONTAINERIZED="auto"' in script
    assert "--containerized 0|1|auto" in script
    assert (
        'if [[ "$CONTAINERIZED" != "0" && "$CONTAINERIZED" != "1" && "$CONTAINERIZED" != "auto" ]]; then'
        in script
    )
    assert 'exec "$ROOT_DIR/scripts/ci/run_in_standard_env.sh"' not in script


def test_quality_gate_provides_host_service_defaults_for_api_real_smoke_local() -> None:
    script = (_repo_root() / "scripts" / "governance" / "quality_gate.sh").read_text(
        encoding="utf-8"
    )

    assert (
        'default_api_real_smoke_database_url="postgresql+psycopg://postgres:postgres@host.docker.internal:5432/postgres"'
        in script
    )
    assert (
        'default_api_real_smoke_database_url="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres"'
        in script
    )
    assert 'default_api_real_smoke_temporal_target_host="host.docker.internal:7233"' in script
    assert 'default_api_real_smoke_temporal_target_host="127.0.0.1:7233"' in script
    assert 'export DATABASE_URL="$default_api_real_smoke_database_url"' in script
    assert 'export TEMPORAL_TARGET_HOST="$default_api_real_smoke_temporal_target_host"' in script


def test_quality_gate_uses_minimal_database_url_for_contract_diff_export() -> None:
    script = (_repo_root() / "scripts" / "governance" / "quality_gate.sh").read_text(
        encoding="utf-8"
    )

    assert 'DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///:memory:}" \\' in script
    assert (
        'uv run python scripts/governance/export_api_contract.py --repo-root "$ROOT_DIR" --output "$head_json"'
        in script
    )


def test_quality_gate_reuses_python_test_script_and_excludes_coverage_sidecars() -> None:
    script = (_repo_root() / "scripts" / "governance" / "quality_gate.sh").read_text(
        encoding="utf-8"
    )

    assert 'PYTHON_TESTS_XDIST_WORKERS="${PYTHON_TESTS_XDIST_WORKERS:-0}" \\' in script
    assert "bash scripts/ci/python_tests.sh" in script
    assert (
        "find \"$coverage_dir\" -maxdepth 1 -type f -name '.coverage.*' ! -name '*.meta.json' -print"
        in script
    )
    assert 'uv run coverage combine --keep "${coverage_candidates[@]}" >/dev/null' in script
    assert 'gate_state="$(ps -o stat= -p "$gate_pid" 2>/dev/null | tr -d \'[:space:]\')"' in script
    assert '[[ -n "$gate_state" && "$gate_state" != *Z* ]]' in script


def test_run_mutmut_script_summarizes_meta_statuses_instead_of_trusting_truncated_export() -> None:
    script = (_repo_root() / "scripts" / "ci" / "run_mutmut.sh").read_text(encoding="utf-8")

    assert 'python3 "$ROOT_DIR/scripts/governance/check_mutation_stats.py" \\' in script
    assert "--summarize-mutants \\" in script
    assert '"$WORKSPACE/mutants" \\' in script
    assert '"$WORKSPACE/mutants/mutmut-cicd-stats.json" \\' in script
    assert "mutmut export-cicd-stats" not in script


def test_quality_gate_reuses_fresh_current_commit_mutation_stats_before_rerun() -> None:
    script = (_repo_root() / "scripts" / "governance" / "quality_gate.sh").read_text(
        encoding="utf-8"
    )

    assert 'echo "[quality-gate] mutation gate reusing fresh current-commit stats at $stats_file"' in script
    assert 'if "mutmut_run_exit" not in stats:' in script
    assert 'if str(meta.get("source_entrypoint") or "").strip() != "scripts/ci/run_mutmut.sh":' in script
