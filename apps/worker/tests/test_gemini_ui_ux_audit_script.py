from __future__ import annotations

import importlib.util
import json
import sys
import types as pytypes
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[3] / "scripts" / "ci" / "gemini_ui_ux_audit.py"
    spec = importlib.util.spec_from_file_location("gemini_ui_ux_audit", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_audit_report_accepts_fenced_json_with_prefix_and_caps_issue_count() -> None:
    module = _load_module()

    parsed = module._extract_audit_report(
        """
        Analysis preview:
        ```json
        {
          "summary": "Primary CTA hierarchy is mostly consistent.",
          "issues": [
            {
              "severity": "warning",
              "file": "apps/web/app/page.tsx",
              "line": 42,
              "category": "ux",
              "message": "Secondary action visually competes with primary CTA.",
              "suggestion": "Reduce secondary button emphasis."
            },
            {
              "severity": "error",
              "file": "apps/web/components/nav.tsx",
              "line": 7,
              "category": "a11y",
              "message": "Icon button has no accessible name.",
              "suggestion": "Add aria-label to the control."
            },
            {
              "severity": "warning",
              "file": "apps/web/components/route-transition.tsx",
              "line": 21,
              "category": "motion",
              "message": "Reduced motion preference is ignored.",
              "suggestion": "Respect prefers-reduced-motion."
            },
            {
              "severity": "error",
              "file": "apps/web/app/feed/page.tsx",
              "line": 18,
              "category": "ux",
              "message": "Loading state lacks deterministic skeleton.",
              "suggestion": "Render fixed-height placeholders."
            }
          ]
        }
        ```
        trailing note ignored
        """
    )

    assert parsed["summary"] == "Primary CTA hierarchy is mostly consistent."
    assert len(parsed["issues"]) == module.MAX_ISSUES_PER_BATCH
    assert parsed["issues"][0]["severity"] == "error"
    assert parsed["issues"][0]["file"] == "apps/web/components/nav.tsx"


def test_extract_audit_report_falls_back_to_legacy_issue_lines() -> None:
    module = _load_module()

    parsed = module._extract_audit_report(
        "SUMMARY|Looks solid overall\n"
        "ISSUE|error|apps/web/app/page.tsx|18|a11y|Missing button label|Add accessible label\n"
    )

    assert parsed["summary"] == "Looks solid overall"
    assert parsed["issues"][0]["severity"] == "error"
    assert parsed["issues"][0]["category"] == "a11y"


def test_main_converts_invalid_response_format_to_blocking_issue(
    monkeypatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    frontend_file = tmp_path / "apps/web/app/page.tsx"
    frontend_file.parent.mkdir(parents=True, exist_ok=True)
    frontend_file.write_text(
        "export default function Page(){return <main>Hello</main>;}", encoding="utf-8"
    )
    report_path = tmp_path / "ui-audit-report.json"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_UI_UX_AUDIT_REPORT_PATH", str(report_path))
    monkeypatch.setattr(module.sys, "argv", ["gemini_ui_ux_audit.py"])

    fake_google = pytypes.ModuleType("google")
    fake_genai = pytypes.ModuleType("google.genai")

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

    class FakeGenerateContentConfig:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    fake_types = pytypes.ModuleType("google.genai.types")
    fake_types.GenerateContentConfig = FakeGenerateContentConfig
    fake_genai.Client = FakeClient
    fake_genai.types = fake_types
    fake_google.genai = fake_genai

    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)

    attempts = [
        {
            "model": "gemini-3.1-pro-preview",
            "status": "failed",
            "reason_code": "invalid_response_format",
            "provider_status": None,
            "error": "truncated output",
        }
    ]

    def _always_invalid(_client, _genai_types, _payload):
        raise module.AuditBatchError(
            message="malformed response",
            reason_code="invalid_response_format",
            provider_status=None,
            attempts=attempts,
        )

    monkeypatch.setattr(module, "_audit_batch", _always_invalid)

    exit_code = module.main()
    assert exit_code == 1

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["reason_code"] == "batch_failures_detected"
    assert report["batch_count"] == 1
    assert report["successful_batches"] == 0
    assert report["failed_batch_count"] == 1
    assert report["issue_count"] == 1
    assert report["blocking_count"] == 1
    assert report["issues"][0]["severity"] == "error"
    assert report["issues"][0]["category"] == "content"
    assert report["issues"][0]["file"] == "apps/web/app/page.tsx"


def test_main_continues_after_invalid_batch_and_records_partial_success(
    monkeypatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    first_file = tmp_path / "apps/web/app/a.tsx"
    second_file = tmp_path / "apps/web/app/b.tsx"
    first_file.parent.mkdir(parents=True, exist_ok=True)
    first_file.write_text("export const first = 1;", encoding="utf-8")
    second_file.write_text("export const second = 2;", encoding="utf-8")
    report_path = tmp_path / "ui-audit-report.json"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_UI_UX_AUDIT_REPORT_PATH", str(report_path))
    monkeypatch.setattr(module.sys, "argv", ["gemini_ui_ux_audit.py"])

    fake_google = pytypes.ModuleType("google")
    fake_genai = pytypes.ModuleType("google.genai")

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

    class FakeGenerateContentConfig:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    fake_types = pytypes.ModuleType("google.genai.types")
    fake_types.GenerateContentConfig = FakeGenerateContentConfig
    fake_genai.Client = FakeClient
    fake_genai.types = fake_types
    fake_google.genai = fake_genai

    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)

    calls = {"count": 0}

    def _first_fails_then_succeeds(_client, _genai_types, _payload):
        calls["count"] += 1
        if calls["count"] == 1:
            raise module.AuditBatchError(
                message="malformed response",
                reason_code="invalid_response_format",
                provider_status=None,
                attempts=[
                    {
                        "model": "gemini-3.1-pro-preview",
                        "status": "failed",
                        "reason_code": "invalid_response_format",
                        "provider_status": None,
                        "error": "truncated output",
                    }
                ],
            )
        return {
            "parsed": {
                "summary": "One actionable issue found.",
                "issues": [
                    {
                        "severity": "warning",
                        "file": "apps/web/app/b.tsx",
                        "line": 1,
                        "category": "ux",
                        "message": "CTA label is vague.",
                        "suggestion": "Use a clearer button label.",
                    }
                ],
                "explicit_none": False,
            },
            "model": "gemini-3.1-pro-preview",
            "attempts": [{"model": "gemini-3.1-pro-preview", "status": "ok", "reason_code": "ok"}],
        }

    monkeypatch.setattr(module, "_audit_batch", _first_fails_then_succeeds)

    exit_code = module.main()
    assert exit_code == 1

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["batch_count"] == 2
    assert report["successful_batches"] == 1
    assert report["failed_batch_count"] == 1
    assert report["reason_code"] == "batch_failures_detected"
    assert report["issue_count"] == 2
    assert report["blocking_count"] == 1
