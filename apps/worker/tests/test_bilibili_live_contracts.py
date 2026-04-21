from __future__ import annotations

import json
from pathlib import Path

from integrations.providers.bilibili_support import (
    assess_bilibili_asr_quality,
    build_bilibili_asr_plan,
    collect_bilibili_failure_taxonomy,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_bilibili_live_canary_matrix_declares_core_extended_and_reader_boundary_samples() -> None:
    matrix_path = _repo_root() / "config" / "runtime" / "bilibili-live-canary-matrix.json"
    payload = json.loads(matrix_path.read_text(encoding="utf-8"))

    samples = payload["samples"]
    slugs = [str(item["slug"]) for item in samples]
    reader_samples = [item for item in samples if bool(item.get("reader_boundary_candidate"))]

    assert payload["matrix_kind"] == "sourceharbor_bilibili_live_canary_matrix_v1"
    assert 5 <= len(samples) <= 10
    assert len(slugs) == len(set(slugs))
    assert any(str(item.get("tier")) == "core" for item in samples)
    assert any(str(item.get("tier")) == "extended" for item in samples)
    assert len(reader_samples) >= 1
    assert all(
        str(item.get("url") or "").startswith("https://www.bilibili.com/video/") for item in samples
    )


def test_build_bilibili_asr_plan_adapts_by_duration_and_language() -> None:
    short_plan = build_bilibili_asr_plan(metadata={})
    long_cjk_plan = build_bilibili_asr_plan(
        metadata={
            "duration": 5400,
            "title": "中文长视频课程",
            "description": "这是一个详细的中文讲解视频。",
            "language": "zh",
        }
    )

    assert short_plan["duration_seconds"] == 0
    assert short_plan["language_hint"] == "unknown"
    assert short_plan["model_candidates"][0] == "tiny"
    assert short_plan["subprocess_timeout_seconds"] == 420

    assert long_cjk_plan["duration_seconds"] == 5400
    assert long_cjk_plan["language_hint"] == "cjk"
    assert long_cjk_plan["model_candidates"][0] in {"base", "small"}
    assert "small" in long_cjk_plan["model_candidates"]
    assert long_cjk_plan["subprocess_timeout_seconds"] >= 900


def test_assess_bilibili_asr_quality_flags_low_confidence_longform_output() -> None:
    verdict = assess_bilibili_asr_quality(
        transcript="你好",
        metadata={"duration": 3600, "title": "中文长视频"},
    )

    assert verdict["status"] == "review"
    assert verdict["score_label"] == "low"
    assert "asr_quality_insufficient" in verdict["reasons"]


def test_collect_bilibili_failure_taxonomy_distinguishes_route_login_and_risk_control() -> None:
    taxonomy = collect_bilibili_failure_taxonomy(
        error_texts=[
            "comments_collection_failed_degraded: bilibili aid not resolved",
            "Error: Got error code -352 while fetching: 风控校验失败",
            "Bilibili account center redirected to login page",
            "rsshub route probe returned 404 for /bilibili/user/video/123456",
        ]
    )

    assert "comments_api_failed" in taxonomy
    assert "risk_control_or_geo_restricted" in taxonomy
    assert "login_state_missing" in taxonomy
    assert "rsshub_route_drift" in taxonomy
