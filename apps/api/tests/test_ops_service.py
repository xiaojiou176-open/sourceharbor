from __future__ import annotations

import importlib
import os
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy.exc import DBAPIError


def _load_ops_module():
    os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/sourceharbor-ops-test.db")
    os.environ.setdefault("TEMPORAL_TARGET_HOST", "127.0.0.1:7233")
    os.environ.setdefault("TEMPORAL_NAMESPACE", "default")
    os.environ.setdefault("TEMPORAL_TASK_QUEUE", "sourceharbor-worker")
    os.environ.setdefault("SQLITE_STATE_PATH", "/tmp/sourceharbor-ops-test-state.db")
    module = importlib.import_module("apps.api.app.services.ops")
    return importlib.reload(module)


def test_build_retrieval_gate_blocks_when_corpus_is_effectively_empty() -> None:
    module = _load_ops_module()
    payload = module.build_retrieval_gate(
        videos=0,
        jobs_with_artifacts=0,
        knowledge_cards=0,
        video_embeddings=0,
    )

    assert payload["status"] == "blocked"
    assert "empty" in payload["summary"].lower()


def test_build_retrieval_gate_warns_when_counts_are_unavailable() -> None:
    module = _load_ops_module()
    payload = module.build_retrieval_gate(
        videos=None,
        jobs_with_artifacts=2,
        knowledge_cards=3,
        video_embeddings=4,
    )

    assert payload["status"] == "warn"
    assert payload["details"]["videos"] is None
    assert payload["details"]["semantic_path"] == "implemented_experimental"


def test_build_retrieval_gate_warns_when_embeddings_are_missing() -> None:
    module = _load_ops_module()
    payload = module.build_retrieval_gate(
        videos=3,
        jobs_with_artifacts=2,
        knowledge_cards=5,
        video_embeddings=0,
    )

    assert payload["status"] == "warn"
    assert payload["details"]["keyword_path"] == "ready"
    assert payload["details"]["semantic_path"] == "experimental_without_embeddings"


def test_build_retrieval_gate_ready_when_embeddings_exist() -> None:
    module = _load_ops_module()
    payload = module.build_retrieval_gate(
        videos=3,
        jobs_with_artifacts=2,
        knowledge_cards=5,
        video_embeddings=6,
    )

    assert payload["status"] == "ready"
    assert payload["details"]["semantic_path"] == "ready_experimental"


def test_build_notifications_gate_blocks_without_resend_secrets() -> None:
    module = _load_ops_module()
    payload = module.build_notifications_gate(
        notification_enabled=False,
        config_enabled=False,
        resend_api_key_present=False,
        resend_from_email_present=False,
        to_email=None,
    )

    assert payload["status"] == "blocked"
    assert "Resend provider configuration" in payload["summary"]
    assert payload["details"]["missing_requirements"] == [
        "RESEND_API_KEY",
        "RESEND_FROM_EMAIL",
    ]


def test_build_notifications_gate_identifies_missing_sender_email_separately() -> None:
    module = _load_ops_module()
    payload = module.build_notifications_gate(
        notification_enabled=True,
        config_enabled=True,
        resend_api_key_present=True,
        resend_from_email_present=False,
        to_email="ops@example.com",
    )

    assert payload["status"] == "blocked"
    assert payload["details"]["missing_requirements"] == ["RESEND_FROM_EMAIL"]
    assert "RESEND_FROM_EMAIL" in payload["next_step"]


def test_build_notifications_gate_warns_when_config_is_disabled() -> None:
    module = _load_ops_module()
    payload = module.build_notifications_gate(
        notification_enabled=True,
        config_enabled=False,
        resend_api_key_present=True,
        resend_from_email_present=True,
        to_email="ops@example.com",
    )

    assert payload["status"] == "warn"
    assert "turned off" in payload["summary"]


def test_build_notifications_gate_warns_without_recipient_email() -> None:
    module = _load_ops_module()
    payload = module.build_notifications_gate(
        notification_enabled=True,
        config_enabled=True,
        resend_api_key_present=True,
        resend_from_email_present=True,
        to_email="   ",
    )

    assert payload["status"] == "warn"
    assert payload["details"]["to_email_present"] is False


def test_build_notifications_gate_warns_when_env_disables_delivery() -> None:
    module = _load_ops_module()
    payload = module.build_notifications_gate(
        notification_enabled=False,
        config_enabled=True,
        resend_api_key_present=True,
        resend_from_email_present=True,
        to_email="ops@example.com",
    )

    assert payload["status"] == "warn"
    assert "disabled by environment" in payload["summary"]


def test_build_notifications_gate_ready_when_everything_is_present() -> None:
    module = _load_ops_module()
    payload = module.build_notifications_gate(
        notification_enabled=True,
        config_enabled=True,
        resend_api_key_present=True,
        resend_from_email_present=True,
        to_email="ops@example.com",
    )

    assert payload["status"] == "ready"
    assert payload["details"]["to_email_present"] is True


def test_build_ui_audit_gate_stays_ready_when_only_gemini_review_is_missing() -> None:
    module = _load_ops_module()
    payload = module.build_ui_audit_gate(
        artifact_base_root="/tmp",
        gemini_review_enabled=True,
        gemini_api_key_present=False,
    )

    assert payload["status"] == "ready"
    assert "Gemini review layer is blocked" in payload["summary"]


def test_build_computer_use_gate_blocks_without_gemini_key() -> None:
    module = _load_ops_module()
    payload = module.build_computer_use_gate(
        gemini_api_key_present=False,
        model="gemini-2.5-computer-use-preview-10-2025",
    )

    assert payload["status"] == "blocked"
    assert payload["details"]["input_contract"] == "instruction + screenshot_base64 + safety"


def test_build_computer_use_gate_ready_with_provider_secret() -> None:
    module = _load_ops_module()
    payload = module.build_computer_use_gate(
        gemini_api_key_present=True,
        model="gemini-2.5-computer-use-preview-10-2025",
    )

    assert payload["status"] == "ready"
    assert payload["details"]["provider"] == "gemini"


def test_load_repo_browser_proof_handles_missing_invalid_and_empty_site_payloads(
    tmp_path, monkeypatch
) -> None:
    module = _load_ops_module()
    proof_path = tmp_path / "repo-chrome-open-tabs.json"

    monkeypatch.setattr(module, "REPO_ROOT", tmp_path, raising=False)
    monkeypatch.setattr(module, "REPO_BROWSER_PROOF_PATH", proof_path, raising=False)

    missing = module._load_repo_browser_proof()
    assert missing["status"] == "blocked"
    assert missing["artifact_path"] == Path("repo-chrome-open-tabs.json").as_posix()

    proof_path.write_text("{bad-json", encoding="utf-8")
    invalid = module._load_repo_browser_proof()
    assert invalid["status"] == "warn"
    assert invalid["sites"] == []

    proof_path.write_text(
        """
        {
          "generated_at": "2026-04-21T19:40:05Z",
          "site_results": {
            "bilibili_account": "skip-me"
          }
        }
        """,
        encoding="utf-8",
    )
    empty = module._load_repo_browser_proof()
    assert empty["status"] == "warn"
    assert empty["generated_at"] == "2026-04-21T19:40:05Z"
    assert empty["sites"] == []


def test_build_bilibili_account_ops_gate_blocks_when_browser_proof_is_not_authenticated() -> None:
    module = _load_ops_module()

    payload = module.build_bilibili_account_ops_gate(
        repo_browser_proof={
            "artifact_path": ".runtime-cache/reports/runtime/repo-chrome-open-tabs.json",
            "sites": [
                {
                    "label": "bilibili_account",
                    "login_state": "logged_out",
                    "final_url": "https://account.bilibili.com/account/home",
                }
            ],
        },
        bilibili_cookie_present=True,
    )

    assert payload["status"] == "blocked"
    assert payload["details"]["login_state"] == "logged_out"
    assert payload["details"]["cookie_present"] is True


def test_build_disk_governance_gate_ready_when_runtime_and_duplicate_envs_are_clear() -> None:
    module = _load_ops_module()
    payload = module.build_disk_governance_gate(
        {
            "status": "ready",
            "summary": "Repo-side duplicate runtime and known duplicate project envs are currently within the expected bounds.",
            "next_step": "None.",
            "details": {"repo_tmp_cleanup_ready": False, "duplicate_envs": []},
        }
    )

    assert payload["status"] == "ready"
    assert "within the expected bounds" in payload["summary"]


def test_build_disk_governance_gate_warns_when_repo_tmp_is_present_but_blocked() -> None:
    module = _load_ops_module()
    payload = module.build_disk_governance_gate(
        {
            "status": "warn",
            "summary": "Repo-side web runtime duplicate is present, but repo-tmp cleanup is still gated.",
            "next_step": "Keep the duplicate runtime in place until the repo-tmp safety gates clear.",
            "details": {
                "repo_tmp_cleanup_ready": False,
                "blocking_gates": [{"name": "quiet-window", "detail": "0.5m since latest change"}],
                "duplicate_envs": [
                    {
                        "path": "/tmp/sourceharbor/project-venv-codex",
                        "reference_status": "unreferenced-by-known-entrypoints",
                    }
                ],
            },
        }
    )

    assert payload["status"] == "warn"
    assert "repo-tmp cleanup is still gated" in payload["summary"]
    assert payload["details"]["blocking_gates"] == [
        {"name": "quiet-window", "detail": "0.5m since latest change"}
    ]
    assert payload["details"]["duplicate_envs"][0]["reference_status"] == (
        "unreferenced-by-known-entrypoints"
    )


def test_timestamp_rank_accepts_datetime_instances() -> None:
    module = _load_ops_module()
    service = module.OpsService(SimpleNamespace())

    value = datetime(2026, 4, 4, 12, 0, tzinfo=UTC)

    assert service._timestamp_rank(value) == int(value.timestamp())


def test_get_inbox_aggregates_sections_and_orders_items(monkeypatch) -> None:
    module = _load_ops_module()
    service = module.OpsService(SimpleNamespace())

    monkeypatch.setattr(
        module.Settings,
        "from_env",
        staticmethod(
            lambda: SimpleNamespace(
                notification_enabled=True,
                resend_api_key="rk",
                resend_from_email="from@example.com",
                gemini_api_key="gemini-key",
                gemini_computer_use_model="gemini-2.5-computer-use-preview-10-2025",
                ui_audit_gemini_enabled=True,
            )
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_failed_jobs",
        lambda limit: {
            "status": "ok",
            "total": 1,
            "error": None,
            "items": [
                {
                    "id": "job-1",
                    "title": "AI Weekly",
                    "status": "failed",
                    "pipeline_final_status": "failed",
                    "error_message": "llm failed",
                    "updated_at": "2026-04-01T10:00:00Z",
                }
            ],
        },
    )
    monkeypatch.setattr(
        service,
        "_load_failed_ingest_runs",
        lambda limit: {
            "status": "ok",
            "total": 1,
            "error": None,
            "items": [
                {
                    "id": "run-1",
                    "status": "failed",
                    "error_message": "ingest stalled",
                    "created_at": "2026-04-01T09:00:00Z",
                }
            ],
        },
    )
    monkeypatch.setattr(
        service,
        "_load_notification_deliveries",
        lambda limit: {
            "status": "ok",
            "total": 1,
            "error": None,
            "items": [
                {
                    "id": "delivery-1",
                    "kind": "daily_digest",
                    "status": "failed",
                    "error_message": "smtp timeout",
                    "created_at": "2026-04-01T08:00:00Z",
                }
            ],
        },
    )
    monkeypatch.setattr(
        service,
        "_load_retrieval_counts",
        lambda: {
            "videos": 10,
            "jobs_with_artifacts": 8,
            "knowledge_cards": 12,
            "video_embeddings": 7,
        },
    )
    monkeypatch.setattr(
        service,
        "_load_notification_config",
        lambda: {
            "to_email": "ops@example.com",
            "enabled": True,
            "failure_alert_enabled": True,
            "ui_audit_artifact_base_root": "/tmp/sourceharbor-artifacts",
            "ui_audit_gemini_enabled": True,
        },
    )
    monkeypatch.setattr(
        module.HealthService,
        "get_provider_health",
        lambda self, window_hours: {
            "window_hours": window_hours,
            "providers": [
                {
                    "provider": "gemini",
                    "last_status": "warn",
                    "last_checked_at": "2026-04-01T07:00:00Z",
                    "last_message": "timeout",
                }
            ],
        },
    )
    monkeypatch.setattr(
        module,
        "_load_disk_governance_helpers",
        lambda: (
            lambda *_args, **_kwargs: {"version": 1},
            lambda *_args, **_kwargs: {
                "status": "ready",
                "summary": "Repo-side duplicate runtime and known duplicate project envs are currently within the expected bounds.",
                "next_step": "None.",
                "details": {"repo_tmp_cleanup_ready": False, "duplicate_envs": []},
            },
        ),
    )

    payload = service.get_inbox(limit=5, window_hours=24)

    assert payload["overview"]["attention_items"] == 5
    assert payload["overview"]["notification_or_gate_issues"] == 3
    assert payload["gates"]["notifications"]["status"] == "ready"
    assert payload["gates"]["disk_governance"]["status"] == "ready"
    assert payload["gates"]["computer_use"]["status"] == "ready"
    assert payload["inbox_items"][0]["kind"] == "job_failed"
    assert payload["inbox_items"][0]["action_label"] == "Open job"
    assert {item["kind"] for item in payload["inbox_items"]} == {
        "job_failed",
        "ingest_failed",
        "notification_delivery",
        "provider_health",
        "hardening_gate",
    }


def test_get_inbox_emits_gate_items_with_settings_shortcut(monkeypatch) -> None:
    module = _load_ops_module()
    service = module.OpsService(SimpleNamespace())

    monkeypatch.setattr(
        module.Settings,
        "from_env",
        staticmethod(
            lambda: SimpleNamespace(
                notification_enabled=False,
                resend_api_key="",
                resend_from_email="",
                gemini_api_key="",
                gemini_computer_use_model="gemini-2.5-computer-use-preview-10-2025",
                ui_audit_gemini_enabled=True,
            )
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_failed_jobs",
        lambda limit: {"status": "ok", "total": 0, "error": None, "items": []},
    )
    monkeypatch.setattr(
        service,
        "_load_failed_ingest_runs",
        lambda limit: {"status": "ok", "total": 0, "error": None, "items": []},
    )
    monkeypatch.setattr(
        service,
        "_load_notification_deliveries",
        lambda limit: {"status": "ok", "total": 0, "error": None, "items": []},
    )
    monkeypatch.setattr(
        service,
        "_load_retrieval_counts",
        lambda: {
            "videos": None,
            "jobs_with_artifacts": None,
            "knowledge_cards": None,
            "video_embeddings": None,
        },
    )
    monkeypatch.setattr(
        service,
        "_load_notification_config",
        lambda: {
            "to_email": None,
            "enabled": False,
            "failure_alert_enabled": False,
            "ui_audit_artifact_base_root": "/tmp/sourceharbor-artifacts",
            "ui_audit_gemini_enabled": True,
        },
    )
    monkeypatch.setattr(
        module.HealthService,
        "get_provider_health",
        lambda self, window_hours: {"window_hours": window_hours, "providers": []},
    )
    monkeypatch.setattr(
        module,
        "_load_disk_governance_helpers",
        lambda: (
            lambda *_args, **_kwargs: {"version": 1},
            lambda *_args, **_kwargs: {
                "status": "ready",
                "summary": "Repo-side duplicate runtime and known duplicate project envs are currently within the expected bounds.",
                "next_step": "None.",
                "details": {"repo_tmp_cleanup_ready": False, "duplicate_envs": []},
            },
        ),
    )

    payload = service.get_inbox(limit=5, window_hours=24)
    gate_items = [item for item in payload["inbox_items"] if item["kind"] == "hardening_gate"]

    assert len(gate_items) == 4
    assert any(
        item["href"] == "/settings" and item["action_label"] == "Open settings"
        for item in gate_items
    )
    assert any(
        item["href"] == "#hardening-gates" and item["action_label"] == "Open gate"
        for item in gate_items
    )


def test_get_inbox_surfaces_repo_browser_proof_and_bilibili_account_ops_gate(
    monkeypatch,
) -> None:
    module = _load_ops_module()
    service = module.OpsService(SimpleNamespace())

    monkeypatch.setattr(
        module.Settings,
        "from_env",
        staticmethod(
            lambda: SimpleNamespace(
                notification_enabled=False,
                resend_api_key="",
                resend_from_email="",
                gemini_api_key="",
                gemini_computer_use_model="gemini-2.5-computer-use-preview-10-2025",
                ui_audit_gemini_enabled=True,
                bilibili_cookie="SESSDATA=demo",
            )
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_failed_jobs",
        lambda limit: {"status": "ok", "total": 0, "error": None, "items": []},
    )
    monkeypatch.setattr(
        service,
        "_load_failed_ingest_runs",
        lambda limit: {"status": "ok", "total": 0, "error": None, "items": []},
    )
    monkeypatch.setattr(
        service,
        "_load_notification_deliveries",
        lambda limit: {"status": "ok", "total": 0, "error": None, "items": []},
    )
    monkeypatch.setattr(
        service,
        "_load_retrieval_counts",
        lambda: {
            "videos": 2,
            "jobs_with_artifacts": 2,
            "knowledge_cards": 2,
            "video_embeddings": 1,
        },
    )
    monkeypatch.setattr(
        service,
        "_load_notification_config",
        lambda: {
            "to_email": None,
            "enabled": False,
            "failure_alert_enabled": False,
            "ui_audit_artifact_base_root": "/tmp/sourceharbor-artifacts",
            "ui_audit_gemini_enabled": False,
        },
    )
    monkeypatch.setattr(
        module.HealthService,
        "get_provider_health",
        lambda self, window_hours: {"window_hours": window_hours, "providers": []},
    )
    monkeypatch.setattr(
        module,
        "_load_disk_governance_helpers",
        lambda: (
            lambda *_args, **_kwargs: {"version": 1},
            lambda *_args, **_kwargs: {
                "status": "ready",
                "summary": "Repo-side duplicate runtime and known duplicate project envs are currently within the expected bounds.",
                "next_step": "None.",
                "details": {"repo_tmp_cleanup_ready": False, "duplicate_envs": []},
            },
        ),
    )
    monkeypatch.setattr(
        module,
        "_load_repo_browser_proof",
        lambda: {
            "status": "ready",
            "summary": "Repo-owned browser proof is current.",
            "artifact_path": ".runtime-cache/reports/runtime/repo-chrome-open-tabs.json",
            "generated_at": "2026-04-21T19:40:05Z",
            "sites": [
                {
                    "label": "bilibili_account",
                    "login_state": "authenticated",
                    "final_url": "https://account.bilibili.com/account/home",
                    "proof_kind": "url_page_state",
                }
            ],
        },
        raising=False,
    )

    payload = service.get_inbox(limit=5, window_hours=24)

    assert payload["repo_browser_proof"]["status"] == "ready"
    assert payload["repo_browser_proof"]["sites"][0]["label"] == "bilibili_account"
    assert payload["gates"]["bilibili_account_ops"]["status"] == "ready"
    assert payload["gates"]["bilibili_account_ops"]["details"]["cookie_present"] is True


def test_get_inbox_keeps_disk_governance_gate_warn_when_summary_loading_fails(
    monkeypatch,
) -> None:
    module = _load_ops_module()
    service = module.OpsService(SimpleNamespace())

    monkeypatch.setattr(
        module.Settings,
        "from_env",
        staticmethod(
            lambda: SimpleNamespace(
                notification_enabled=False,
                resend_api_key="",
                resend_from_email="",
                gemini_api_key="",
                gemini_computer_use_model="gemini-2.5-computer-use-preview-10-2025",
                ui_audit_gemini_enabled=True,
            )
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_failed_jobs",
        lambda limit: {"status": "ok", "total": 0, "error": None, "items": []},
    )
    monkeypatch.setattr(
        service,
        "_load_failed_ingest_runs",
        lambda limit: {"status": "ok", "total": 0, "error": None, "items": []},
    )
    monkeypatch.setattr(
        service,
        "_load_notification_deliveries",
        lambda limit: {"status": "ok", "total": 0, "error": None, "items": []},
    )
    monkeypatch.setattr(
        service,
        "_load_retrieval_counts",
        lambda: {
            "videos": 1,
            "jobs_with_artifacts": 1,
            "knowledge_cards": 1,
            "video_embeddings": 1,
        },
    )
    monkeypatch.setattr(
        service,
        "_load_notification_config",
        lambda: {
            "to_email": None,
            "enabled": False,
            "failure_alert_enabled": False,
            "ui_audit_artifact_base_root": "/tmp/sourceharbor-artifacts",
            "ui_audit_gemini_enabled": True,
        },
    )
    monkeypatch.setattr(
        module.HealthService,
        "get_provider_health",
        lambda self, window_hours: {"window_hours": window_hours, "providers": []},
    )
    monkeypatch.setattr(
        module,
        "_load_disk_governance_helpers",
        lambda: (_ for _ in ()).throw(OSError("broken report")),
    )

    payload = service.get_inbox(limit=5, window_hours=24)

    assert payload["gates"]["disk_governance"]["status"] == "warn"
    assert payload["gates"]["disk_governance"]["summary"] == (module.OPS_SECTION_ERROR_MESSAGE)


def test_load_failed_jobs_redacts_db_error_details() -> None:
    module = _load_ops_module()

    class BrokenDb:
        def execute(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
            raise DBAPIError(
                "SELECT 1",
                {},
                Exception("postgresql://ops:super-secret@127.0.0.1:5432/sourceharbor"),
            )

        def rollback(self) -> None:
            return None

    service = module.OpsService(BrokenDb())
    payload = service._load_failed_jobs(limit=5)

    assert payload["status"] == "unavailable"
    assert payload["total"] == 0
    assert payload["error"] == "diagnostic data temporarily unavailable"
    assert "super-secret" not in payload["error"]
    assert payload["items"] == []


def test_load_failed_ingest_runs_redacts_db_error_details() -> None:
    module = _load_ops_module()

    class BrokenDb:
        def execute(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
            raise DBAPIError(
                "SELECT 1",
                {},
                Exception("postgresql://ops:super-secret@127.0.0.1:5432/sourceharbor"),
            )

        def rollback(self) -> None:
            return None

    service = module.OpsService(BrokenDb())
    payload = service._load_failed_ingest_runs(limit=5)

    assert payload["status"] == "unavailable"
    assert payload["total"] == 0
    assert payload["error"] == "diagnostic data temporarily unavailable"
    assert "super-secret" not in payload["error"]
    assert payload["items"] == []


def test_load_notification_deliveries_redacts_db_error_details() -> None:
    module = _load_ops_module()

    class BrokenDb:
        def execute(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
            raise DBAPIError(
                "SELECT 1",
                {},
                Exception("postgresql://ops:super-secret@127.0.0.1:5432/sourceharbor"),
            )

        def rollback(self) -> None:
            return None

    service = module.OpsService(BrokenDb())
    payload = service._load_notification_deliveries(limit=5)

    assert payload["status"] == "unavailable"
    assert payload["total"] == 0
    assert payload["error"] == "diagnostic data temporarily unavailable"
    assert "super-secret" not in payload["error"]
    assert payload["items"] == []
