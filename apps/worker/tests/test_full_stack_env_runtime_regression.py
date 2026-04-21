from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _run_bash(
    script: str, *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        ["bash", "-lc", script],
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_resolve_runtime_route_value_precedence(tmp_path: Path) -> None:
    root = _repo_root()
    (tmp_path / ".runtime-cache" / "run" / "full-stack").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".env").write_text("export API_PORT='3009'\n", encoding="utf-8")
    (tmp_path / ".runtime-cache" / "run" / "full-stack" / "resolved.env").write_text(
        "export API_PORT='18000'\n",
        encoding="utf-8",
    )

    probe = f"""
source "{root}/scripts/lib/load_env.sh"
printf '%s\\n' "$(resolve_runtime_route_value "{tmp_path}" "API_PORT" "" "9000")"
printf '%s\\n' "$(resolve_runtime_route_value "{tmp_path}" "API_PORT" "19000" "9000")"
printf '%s\\n' "$(resolve_runtime_route_value "{tmp_path}" "MISSING_KEY" "" "3000")"
"""
    proc = _run_bash(probe)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines() == ["18000", "19000", "3000"]


def test_resolve_runtime_route_value_with_sources_prefers_snapshot_over_loaded_defaults(
    tmp_path: Path,
) -> None:
    root = _repo_root()
    (tmp_path / ".runtime-cache" / "run" / "full-stack").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".env").write_text(
        "export API_PORT='3009'\nexport SOURCE_HARBOR_API_BASE_URL='http://127.0.0.1:3009'\n",
        encoding="utf-8",
    )
    (tmp_path / ".runtime-cache" / "run" / "full-stack" / "resolved.env").write_text(
        ("export API_PORT='18000'\nexport SOURCE_HARBOR_API_BASE_URL='http://127.0.0.1:18000'\n"),
        encoding="utf-8",
    )

    probe = f"""
source "{root}/scripts/lib/load_env.sh"
printf '%s\\n' "$(resolve_runtime_route_value_with_sources "{tmp_path}" "API_PORT" "" "" "9000" "9000")"
printf '%s\\n' "$(resolve_runtime_route_value_with_sources "{tmp_path}" "SOURCE_HARBOR_API_BASE_URL" "" "" "http://127.0.0.1:9000" "http://127.0.0.1:9000")"
printf '%s\\n' "$(resolve_runtime_route_value_with_sources "{tmp_path}" "API_PORT" "" "19000" "9000" "9000")"
"""
    proc = _run_bash(probe)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines() == [
        "18000",
        "http://127.0.0.1:18000",
        "19000",
    ]


def test_bootstrap_runtime_values_do_not_persist_into_repo_env() -> None:
    script = (_repo_root() / "scripts" / "runtime" / "bootstrap_full_stack.sh").read_text(
        encoding="utf-8"
    )

    assert "write_runtime_resolved_env" in script
    assert 'cat >> "$ROOT_DIR/.env"' not in script
    assert 'upsert_export_env "$ROOT_DIR/.env"' not in script
    assert 'perl -0pi -e "s|export DATABASE_URL=' not in script
    assert "sed -i.bak" not in script


def test_bootstrap_runtime_snapshot_captures_data_plane_and_temporal_truth() -> None:
    script = (_repo_root() / "scripts" / "runtime" / "bootstrap_full_stack.sh").read_text(
        encoding="utf-8"
    )

    assert '"DATABASE_URL=${DATABASE_URL}"' in script
    assert '"CORE_POSTGRES_PORT=${CORE_POSTGRES_PORT}"' in script
    assert '"TEMPORAL_TARGET_HOST=${TEMPORAL_TARGET_HOST}"' in script
    assert '"TEMPORAL_NAMESPACE=${TEMPORAL_NAMESPACE}"' in script
    assert '"TEMPORAL_TASK_QUEUE=${TEMPORAL_TASK_QUEUE}"' in script


def test_bootstrap_tracks_applied_sql_migrations_before_replaying_local_state() -> None:
    script = (_repo_root() / "scripts" / "runtime" / "bootstrap_full_stack.sh").read_text(
        encoding="utf-8"
    )

    assert "sourceharbor_schema_migrations" in script
    assert "migration_name TEXT PRIMARY KEY" in script
    assert 'migration_name="$(basename "$migration")"' in script
    assert "\\i '$ROOT_DIR/$migration'" in script
    assert "INSERT INTO sourceharbor_schema_migrations" in script


def test_wave0_local_env_defaults_use_isolated_core_postgres_and_worker_queue() -> None:
    env_example = (_repo_root() / ".env.example").read_text(encoding="utf-8")

    assert 'export CORE_POSTGRES_PORT="${CORE_POSTGRES_PORT:-15432}"' in env_example
    assert (
        'export DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:${CORE_POSTGRES_PORT}/sourceharbor"'
        in env_example
    )
    assert "export TEMPORAL_TASK_QUEUE=sourceharbor-worker" in env_example


def test_full_stack_uses_runtime_snapshot_for_data_plane_and_worker_signature() -> None:
    script = (_repo_root() / "scripts" / "runtime" / "full_stack.sh").read_text(encoding="utf-8")

    assert 'inherited_api_port="${API_PORT-}"' in script
    assert 'resolve_runtime_route_value_with_sources "$ROOT_DIR" "API_PORT"' in script
    assert 'resolve_runtime_route_value_with_sources "$ROOT_DIR" "CORE_POSTGRES_PORT"' in script
    assert 'resolve_runtime_route_value_with_sources "$ROOT_DIR" "DATABASE_URL"' in script
    assert 'resolve_runtime_route_value_with_sources "$ROOT_DIR" "TEMPORAL_TARGET_HOST"' in script
    assert 'resolve_runtime_route_value_with_sources "$ROOT_DIR" "TEMPORAL_NAMESPACE"' in script
    assert 'resolve_runtime_route_value_with_sources "$ROOT_DIR" "TEMPORAL_TASK_QUEUE"' in script
    assert "normalize_runtime_database_url" in script
    assert (
        'start_one api env DATABASE_URL="$DATABASE_URL" SOURCE_HARBOR_API_KEY="$startup_write_token"'
        in script
    )
    assert (
        'start_one_retry worker 10 2 env DATABASE_URL="$DATABASE_URL" SOURCE_HARBOR_API_KEY="$startup_write_token"'
        in script
    )
    assert 'local next_cli="$WEB_RUNTIME_WEB_DIR/node_modules/next/dist/bin/next"' in script
    assert "exec node ./node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port" in script
    assert 'if [[ "$name" != "api" && "$cmd" != *"$ROOT_DIR"* ]]; then' not in script
    assert "Service-specific regex plus the expected port" in script


def test_live_smoke_bilibili_uses_default_product_subtitle_strategy() -> None:
    script = (_repo_root() / "scripts" / "ci" / "e2e_live_smoke.sh").read_text(encoding="utf-8")

    assert 'SUBTITLE_ASR_ENABLED="$subtitle_asr_enabled"' not in script
    assert 'SUBTITLE_ASR_MODEL="$subtitle_asr_model"' not in script
    assert 'SUBTITLE_TIMEOUT_SECONDS="$subtitle_timeout_seconds"' not in script
    assert 'subtitles = {"asr_fallback_enabled": True}' not in script
    assert (
        'bilibili_job_id="$(process_video "bilibili" "$BILIBILI_SMOKE_URL" "full" "bilibili_full")"'
        in script
    )
    assert (
        'wait_for_terminal_status "$bilibili_job_id" "video_process:bilibili_full" "420"' in script
    )


def test_live_smoke_supports_bilibili_canary_matrix_and_reader_boundary_receipt() -> None:
    script = (_repo_root() / "scripts" / "ci" / "e2e_live_smoke.sh").read_text(encoding="utf-8")
    wrapper = (_repo_root() / "scripts" / "ci" / "smoke_full_stack.sh").read_text(encoding="utf-8")

    assert "--bilibili-canary-matrix <path>" in script
    assert "--bilibili-canary-tier <name>" in script
    assert "--bilibili-canary-limit <n>" in script
    assert "--bilibili-reader-receipt-sample <slug>" in script
    assert '"bilibili_canary_matrix"' in script
    assert '"bilibili_reader_receipt"' in script
    assert 'record_scenario "bilibili_reader_boundary"' in script
    assert '"published_document_ids"' in script
    assert "reader public boundary missing current batch document" in script
    assert "reader navigation boundary missing current batch document" in script
    assert "--live-smoke-bilibili-canary-matrix" in wrapper
    assert "--live-smoke-bilibili-reader-receipt-sample" in wrapper


def test_full_stack_only_falls_back_to_local_dev_tokens_outside_ci() -> None:
    script = (_repo_root() / "scripts" / "runtime" / "full_stack.sh").read_text(encoding="utf-8")

    assert 'local_default_write_token="sourceharbor-local-dev-token"' in script
    assert "ci_mode=\"$(printf '%s' \"${CI:-}\" | tr '[:upper:]' '[:lower:]')\"" in script
    assert (
        'if [[ "$ci_mode" == "1" || "$ci_mode" == "true" || "$ci_mode" == "yes" || "$ci_mode" == "on" || "$github_actions_mode" == "1" || "$github_actions_mode" == "true" || "$github_actions_mode" == "yes" || "$github_actions_mode" == "on" ]]; then'
        in script
    )
    assert 'local_write_token="${SOURCE_HARBOR_API_KEY:-$local_default_write_token}"' in script
    assert (
        'startup_web_session_token="${WEB_ACTION_SESSION_TOKEN:-${startup_write_token:-$local_default_write_token}}"'
        in script
    )
    assert "normalize_database_url_driver()" not in script


def test_full_stack_uses_python_detach_fallback_when_setsid_is_missing() -> None:
    script = (_repo_root() / "scripts" / "runtime" / "full_stack.sh").read_text(encoding="utf-8")

    assert "launch_detached_process()" in script
    assert 'nohup setsid "$@" >"$log_file" 2>&1 < /dev/null &' in script
    assert "preexec_fn=os.setsid" in script
    assert 'launched_pid="$(launch_detached_process "$log_file" "$@")"' in script


def test_core_services_compose_uses_isolated_local_postgres_port_default() -> None:
    compose = (_repo_root() / "infra" / "compose" / "core-services.compose.yml").read_text(
        encoding="utf-8"
    )

    assert "127.0.0.1:${CORE_POSTGRES_PORT:-15432}:5432" in compose


def test_core_services_local_fallback_uses_repo_owned_temporal_db() -> None:
    script = (_repo_root() / "scripts" / "deploy" / "core_services.sh").read_text(encoding="utf-8")

    assert 'TEMPORAL_STATE_DIR="$ROOT_DIR/.runtime-cache/tmp/local-temporal"' in script
    assert 'TEMPORAL_DB_PATH="$TEMPORAL_STATE_DIR/dev.sqlite"' in script
    assert '"--db-filename"' in script
    assert 'db_path = os.environ["TEMPORAL_DB_PATH"]' in script


def test_core_services_does_not_reuse_unhealthy_temporal_listener_by_port_only() -> None:
    script = (_repo_root() / "scripts" / "deploy" / "core_services.sh").read_text(encoding="utf-8")

    assert "temporal_namespace_ready()" in script
    assert '--address "127.0.0.1:${TEMPORAL_PORT}"' in script
    assert "temporal operator namespace describe" in script
    assert "temporal: unhealthy (reused)" in script
    assert (
        "temporal port $TEMPORAL_PORT is occupied by an unhealthy non-repo-owned process" in script
    )
    assert "temporal_listener_is_repo_scoped_start_dev" in script


def test_full_stack_status_handles_stale_pid_metadata(tmp_path: Path) -> None:
    root = _repo_root()
    target_script_dir = tmp_path / "scripts"
    target_lib_dir = target_script_dir / "lib"
    target_runtime_dir = target_script_dir / "runtime"
    target_lib_dir.mkdir(parents=True, exist_ok=True)
    target_runtime_dir.mkdir(parents=True, exist_ok=True)

    full_stack_target = target_script_dir / "full_stack.sh"
    runtime_full_stack_target = target_runtime_dir / "full_stack.sh"
    load_env_target = target_lib_dir / "load_env.sh"
    logging_target = target_runtime_dir / "logging.sh"
    temporal_ready_target = target_lib_dir / "temporal_ready.sh"
    full_stack_target.write_text(
        (root / "scripts" / "full_stack.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    runtime_full_stack_target.write_text(
        (root / "scripts" / "runtime" / "full_stack.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    load_env_target.write_text(
        (root / "scripts" / "lib" / "load_env.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    logging_target.write_text(
        (root / "scripts" / "runtime" / "logging.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (target_runtime_dir / "log_jsonl_event.py").write_text(
        (root / "scripts" / "runtime" / "log_jsonl_event.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    temporal_ready_target.write_text(
        (root / "scripts" / "lib" / "temporal_ready.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    full_stack_target.chmod(0o755)
    runtime_full_stack_target.chmod(0o755)

    pid_file = tmp_path / ".runtime-cache" / "run" / "full-stack" / "api.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(
        (
            "pid=999999\n"
            "pgid=999999\n"
            "service=api\n"
            "signature=api_dev_server\n"
            "started_at=2026-03-08T00:00:00Z\n"
        ),
        encoding="utf-8",
    )

    proc = _run_bash(
        f'"{full_stack_target}" status',
        cwd=tmp_path,
        env={
            "API_PORT": "19090",
            "WEB_PORT": "19091",
            "SOURCE_HARBOR_API_BASE_URL": "http://127.0.0.1:19090",
            "NEXT_PUBLIC_API_BASE_URL": "http://127.0.0.1:19090",
            "API_HEALTH_URL": "http://127.0.0.1:19090/healthz",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert "api: stopped" in proc.stdout
    assert not pid_file.exists()


def test_api_base_resolution_is_unified_across_scripts() -> None:
    root = _repo_root()
    http_api = (root / "scripts" / "lib" / "http_api.sh").read_text(encoding="utf-8")
    daily_digest = (root / "scripts" / "runtime" / "run_daily_digest.sh").read_text(
        encoding="utf-8"
    )
    failure_alerts = (root / "scripts" / "runtime" / "run_failure_alerts.sh").read_text(
        encoding="utf-8"
    )
    ai_feed_sync = (root / "scripts" / "runtime" / "run_ai_feed_sync.sh").read_text(
        encoding="utf-8"
    )
    smoke_full_stack = (root / "scripts" / "ci" / "smoke_full_stack.sh").read_text(encoding="utf-8")

    assert "resolve_http_api_base_url" in http_api
    assert "apply_http_api_base_url" in http_api

    assert 'apply_http_api_base_url "$API_BASE_URL_OVERRIDE" "$ROOT_DIR"' in daily_digest
    assert 'apply_http_api_base_url "$API_BASE_URL_OVERRIDE" "$ROOT_DIR"' in failure_alerts

    assert "resolve_route_value_local" in ai_feed_sync
    assert '"SOURCE_HARBOR_API_BASE_URL"' in ai_feed_sync
    assert "resolve_runtime_route_value" in ai_feed_sync

    assert "resolve_route_value_local" in smoke_full_stack
    assert '"SOURCE_HARBOR_API_BASE_URL"' in smoke_full_stack
    assert "resolve_runtime_route_value_with_sources" in smoke_full_stack
    assert '--api-base-url "$API_BASE"' in smoke_full_stack


def test_smoke_full_stack_prefers_runtime_snapshot_over_loaded_env_defaults(
    tmp_path: Path,
) -> None:
    root = _repo_root()
    (tmp_path / ".runtime-cache" / "run" / "full-stack").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".env").write_text(
        "export SOURCE_HARBOR_API_BASE_URL='http://127.0.0.1:9000'\nexport WEB_PORT='3001'\n",
        encoding="utf-8",
    )
    (tmp_path / ".runtime-cache" / "run" / "full-stack" / "resolved.env").write_text(
        ("export SOURCE_HARBOR_API_BASE_URL='http://127.0.0.1:18000'\nexport WEB_PORT='13000'\n"),
        encoding="utf-8",
    )

    probe = f"""
source "{root}/scripts/lib/load_env.sh"
load_env_file "{tmp_path}/.env" smoke_test
printf '%s\\n' "$(
  resolve_runtime_route_value_with_sources \
    "{tmp_path}" \
    "SOURCE_HARBOR_API_BASE_URL" \
    "" \
    "" \
    "${{SOURCE_HARBOR_API_BASE_URL:-}}" \
    "http://127.0.0.1:9000"
)"
printf '%s\\n' "$(
  resolve_runtime_route_value_with_sources \
    "{tmp_path}" \
    "WEB_PORT" \
    "" \
    "" \
    "${{WEB_PORT:-}}" \
    "3001"
)"
"""
    proc = _run_bash(probe)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines() == [
        "http://127.0.0.1:18000",
        "13000",
    ]


def test_http_api_helper_and_notification_scripts_use_local_write_token_headers() -> None:
    root = _repo_root()
    http_api = (root / "scripts" / "lib" / "http_api.sh").read_text(encoding="utf-8")
    daily_digest = (root / "scripts" / "runtime" / "run_daily_digest.sh").read_text(
        encoding="utf-8"
    )
    failure_alerts = (root / "scripts" / "runtime" / "run_failure_alerts.sh").read_text(
        encoding="utf-8"
    )
    full_stack = (root / "scripts" / "runtime" / "full_stack.sh").read_text(encoding="utf-8")

    assert "X-API-Key: ${SOURCE_HARBOR_API_KEY}" in http_api
    assert "X-Web-Session: ${WEB_ACTION_SESSION_TOKEN}" in http_api
    assert 'export SOURCE_HARBOR_API_KEY="sourceharbor-local-dev-token"' in daily_digest
    assert 'export WEB_ACTION_SESSION_TOKEN="$SOURCE_HARBOR_API_KEY"' in daily_digest
    assert 'export SOURCE_HARBOR_API_KEY="sourceharbor-local-dev-token"' in failure_alerts
    assert 'export WEB_ACTION_SESSION_TOKEN="$SOURCE_HARBOR_API_KEY"' in failure_alerts
    assert 'export NEXT_PUBLIC_WEB_ACTION_SESSION_TOKEN="$local_web_session_token"' in full_stack
    assert 'NEXT_PUBLIC_WEB_ACTION_SESSION_TOKEN="$startup_web_session_token"' in full_stack


def test_smoke_full_stack_defaults_are_strict_for_local_validation() -> None:
    root = _repo_root()
    smoke_full_stack = (root / "scripts" / "ci" / "smoke_full_stack.sh").read_text(encoding="utf-8")

    assert 'LIVE_SMOKE_REQUIRE_SECRETS="1"' in smoke_full_stack
    assert 'LIVE_SMOKE_REQUIRE_NOTIFICATION_LANE="0"' in smoke_full_stack
    assert 'REQUIRE_READER="0"' in smoke_full_stack
    assert "--offline-fallback <0>" in smoke_full_stack
    assert "Deprecated compatibility alias used by docs." in smoke_full_stack
    assert "e2e live smoke require secrets (default: 1)" in smoke_full_stack
    assert "e2e live smoke require notification/provider lane readiness" in smoke_full_stack
    assert "Require reader checks (default: 0)" not in smoke_full_stack
    assert "Require reader-stack checks (default: 0)" in smoke_full_stack
    assert '--require-secrets "$LIVE_SMOKE_REQUIRE_SECRETS"' in smoke_full_stack
    assert '--require-notification-lane "$LIVE_SMOKE_REQUIRE_NOTIFICATION_LANE"' in smoke_full_stack


def test_e2e_live_smoke_defaults_require_secrets_and_keep_opt_out_explicit() -> None:
    root = _repo_root()
    e2e_live_smoke = (root / "scripts" / "ci" / "e2e_live_smoke.sh").read_text(encoding="utf-8")

    assert 'LIVE_SMOKE_REQUIRE_SECRETS="1"' in e2e_live_smoke
    assert 'LIVE_SMOKE_REQUIRE_NOTIFICATION_LANE="0"' in e2e_live_smoke
    assert "Require secrets gate (default: 1)" in e2e_live_smoke
    assert "Require notification/provider lane readiness (default: 0)" in e2e_live_smoke
    assert 'if is_truthy "$LIVE_SMOKE_REQUIRE_SECRETS"; then' in e2e_live_smoke
    assert 'fail "missing required core secrets: ${missing_core[*]}"' in e2e_live_smoke
    assert 'log "SKIP: missing core secrets: ${missing_core[*]}"' in e2e_live_smoke
    assert 'NOTIFICATION_LANE_READY="0"' in e2e_live_smoke
    assert "notification lane degraded: ${NOTIFICATION_LANE_REASON}" in e2e_live_smoke
    assert "Scenario: cleanup workflow API closure" in e2e_live_smoke
    assert 'api_post "/api/v1/workflows/run"' in e2e_live_smoke
    assert '"workflow": "cleanup"' in e2e_live_smoke
    assert 'payload["workflow_name"] == "CleanupWorkspaceWorkflow"' in e2e_live_smoke
    assert 'record_scenario "cleanup_workflow_api" "passed" "status=completed"' in e2e_live_smoke
