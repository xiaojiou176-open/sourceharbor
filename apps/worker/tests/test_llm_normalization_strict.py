from __future__ import annotations

from worker.pipeline.steps.llm import normalize_digest_payload, normalize_outline_payload


def test_normalize_outline_payload_does_not_build_local_semantics() -> None:
    state = {
        "title": "State title",
        "metadata": {
            "title": "Metadata title",
            "webpage_url": "https://www.youtube.com/watch?v=demo",
        },
        "transcript": "line 1. line 2.",
        "comments": {"top_comments": [{"content": "should not be used"}]},
        "frames": [{"path": "/tmp/f1.jpg", "timestamp_s": 10}],
    }

    normalized = normalize_outline_payload({}, state)

    assert normalized["title"] == "Metadata title"
    assert normalized["tldr"] == []
    assert normalized["highlights"] == []
    assert normalized["recommended_actions"] == []
    assert normalized["risk_or_pitfalls"] == []
    assert normalized["chapters"] == []
    assert normalized["timestamp_references"] == []


def test_normalize_digest_payload_does_not_build_local_semantics() -> None:
    state = {
        "title": "State title",
        "metadata": {"title": "Metadata title"},
        "transcript": "this transcript should not be auto-summarized",
        "outline": {
            "highlights": ["local highlight"],
            "recommended_actions": ["local action"],
            "timestamp_references": [{"ts_s": 12, "label": "intro", "reason": "local"}],
        },
    }

    normalized = normalize_digest_payload({}, state)

    assert normalized["title"] == "Metadata title"
    assert normalized["summary"] == ""
    assert normalized["tldr"] == []
    assert normalized["highlights"] == []
    assert normalized["action_items"] == []
    assert normalized["code_blocks"] == []
    assert normalized["timestamp_references"] == []
    assert normalized["fallback_notes"] == []
