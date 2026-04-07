from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_module():
    script_path = _repo_root() / "scripts" / "governance" / "audit_public_images_with_gemini.py"
    spec = importlib.util.spec_from_file_location("audit_public_images_with_gemini", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_report_path_accepts_repo_relative_location() -> None:
    module = _load_module()

    resolved = module.resolve_report_path(".runtime-cache/reports/governance/custom.json")

    assert (
        resolved
        == (_repo_root() / ".runtime-cache" / "reports" / "governance" / "custom.json").resolve()
    )


@pytest.mark.parametrize("candidate", ["/tmp/public-image-audit.json", "../outside.json"])
def test_resolve_report_path_rejects_escape(candidate: str) -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="repo root"):
        module.resolve_report_path(candidate)


def test_summarize_audit_result_discards_freeform_content_and_keeps_safe_summary() -> None:
    module = _load_module()

    summary = module.summarize_audit_result(
        {
            "verdict": "Warning",
            "issues": [
                {
                    "severity": "ERROR",
                    "category": "text clipping",
                    "note": "password=super-secret-123",
                },
                {
                    "severity": "note",
                    "category": "unknown category",
                    "note": "token=abc",
                },
            ],
            "strengths": ["looks polished", "key=secret"],
            "raw": "password=should-never-hit-disk",
        }
    )

    assert summary == {
        "verdict": "warn",
        "issue_count": 2,
        "blocking_issue_count": 1,
        "strength_count": 2,
        "issues": [
            {"severity": "error", "category": "text-clipping"},
            {"severity": "info", "category": "other"},
        ],
        "raw_output_discarded": True,
    }
    assert "super-secret-123" not in json.dumps(summary, sort_keys=True)
    assert "password" not in json.dumps(summary, sort_keys=True)
    assert "token=abc" not in json.dumps(summary, sort_keys=True)


def test_public_image_audit_report_contract_does_not_persist_key_source_metadata() -> None:
    source = (
        _repo_root() / "scripts" / "governance" / "audit_public_images_with_gemini.py"
    ).read_text(encoding="utf-8")

    assert '"key_source"' not in source
