from __future__ import annotations

import re
from typing import Any

BILIBILI_FAILURE_TAXONOMY = (
    "download_failure",
    "subtitle_missing",
    "asr_quality_insufficient",
    "comments_api_failed",
    "rsshub_route_drift",
    "login_state_missing",
    "risk_control_or_geo_restricted",
)

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_WHITESPACE_RE = re.compile(r"\s+")
_RISK_CONTROL_TOKENS = (
    "-352",
    "412 precondition",
    "风控",
    "risk control",
    "geo",
    "region",
    "country",
    "not available in your region",
)
_LOGIN_TOKENS = (
    "redirected to login",
    "login page",
    "not logged in",
    "cookie required",
    "cookie expired",
    "sessdata",
    "account center",
)
_RSSHUB_DRIFT_TOKENS = (
    "rsshub",
    "/bilibili/user/video/",
    "route probe",
    "route drift",
    "feed returned 404",
    "route returned 404",
)
_COMMENTS_TOKENS = (
    "comments_collection_failed_degraded",
    "comments collection failed",
    "comment api",
    "reply/main",
    "reply/reply",
    "bilibili aid not resolved",
    "bilibili_comment_collect",
)
_DOWNLOAD_TOKENS = (
    "download_provider_chain_failed",
    "media_not_found_after_download",
    "download failed",
    "bbdown",
    "yt-dlp",
    "download_media",
)
_SUBTITLE_TOKENS = (
    "subtitle_file_not_found",
    "subtitle_text_empty_after_parse",
    "subtitle missing",
    "subtitle unavailable",
)
_ASR_QUALITY_TOKENS = (
    "asr_quality_insufficient",
    "quality_insufficient",
    "asr_language_mismatch",
    "asr_quality_repetition_high",
)


def contains_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(str(text or "")))


def _clean_text(value: Any) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "")).strip()


def _parse_duration_seconds(value: Any) -> int:
    if isinstance(value, (int, float)):
        return max(0, int(value))
    text = _clean_text(value)
    if not text:
        return 0
    if text.isdigit():
        return max(0, int(text))
    parts = text.split(":")
    if len(parts) not in {2, 3}:
        return 0
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return 0
    if len(numbers) == 2:
        mm, ss = numbers
        return max(0, mm * 60 + ss)
    hh, mm, ss = numbers
    return max(0, hh * 3600 + mm * 60 + ss)


def _duration_seconds(metadata: dict[str, Any] | None) -> int:
    payload = dict(metadata or {})
    for key in ("duration_s", "duration", "duration_seconds"):
        parsed = _parse_duration_seconds(payload.get(key))
        if parsed > 0:
            return parsed
    return 0


def _infer_language_hint(metadata: dict[str, Any] | None) -> str:
    payload = dict(metadata or {})
    explicit = _clean_text(payload.get("language") or payload.get("lang")).lower()
    if explicit:
        if any(token in explicit for token in ("zh", "cmn", "ja", "jp", "ko", "cjk")):
            return "cjk"
        return "non_cjk"
    combined = " ".join(
        item
        for item in (
            _clean_text(payload.get("title")),
            _clean_text(payload.get("description")),
            _clean_text(payload.get("uploader")),
        )
        if item
    )
    return "cjk" if contains_cjk(combined) else "unknown"


def _quality_min_chars(duration_seconds: int) -> int:
    if duration_seconds <= 0:
        return 120
    return max(120, min(2400, duration_seconds // 4))


def build_bilibili_asr_plan(metadata: dict[str, Any] | None) -> dict[str, Any]:
    duration_seconds = _duration_seconds(metadata)
    language_hint = _infer_language_hint(metadata)

    if duration_seconds >= 7200 and language_hint == "cjk":
        model_candidates = ["small", "medium"]
        timeout_seconds = 1200
    elif duration_seconds >= 2700 and language_hint == "cjk" or duration_seconds >= 5400:
        model_candidates = ["base", "small"]
        timeout_seconds = 900
    else:
        model_candidates = ["tiny", "base"]
        timeout_seconds = 420

    return {
        "enabled": True,
        "duration_seconds": duration_seconds,
        "language_hint": language_hint,
        "model_candidates": model_candidates,
        "subprocess_timeout_seconds": timeout_seconds,
        "quality_min_chars": _quality_min_chars(duration_seconds),
    }


def build_bilibili_download_plan(metadata: dict[str, Any] | None) -> dict[str, Any]:
    duration_seconds = _duration_seconds(metadata)
    language_hint = _infer_language_hint(metadata)
    if duration_seconds >= 5400 and language_hint == "cjk":
        timeout_seconds = 900
    elif duration_seconds >= 1800:
        timeout_seconds = 600
    else:
        timeout_seconds = 420
    return {
        "duration_seconds": duration_seconds,
        "language_hint": language_hint,
        "subprocess_timeout_seconds": timeout_seconds,
    }


def assess_bilibili_asr_quality(
    transcript: str,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(metadata or {})
    plan = build_bilibili_asr_plan(payload)
    normalized = str(transcript or "").strip()
    normalized_no_ws = _WHITESPACE_RE.sub("", normalized)
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    unique_line_ratio = (len(set(lines)) / len(lines)) if lines else 1.0
    char_count = len(normalized_no_ws)
    cjk_count = len(_CJK_RE.findall(normalized_no_ws))
    cjk_ratio = (cjk_count / char_count) if char_count else 0.0
    reasons: list[str] = []
    quality_min_chars = int(plan["quality_min_chars"])
    duration_seconds = int(plan["duration_seconds"])
    language_hint = str(plan["language_hint"])

    if char_count == 0 or duration_seconds >= 1800 and char_count < quality_min_chars or duration_seconds >= 600 and char_count < max(80, quality_min_chars // 2):
        reasons.append("asr_quality_insufficient")
    if len(lines) >= 4 and unique_line_ratio < 0.35:
        reasons.append("asr_quality_repetition_high")
    if (
        language_hint == "cjk"
        and duration_seconds >= 1800
        and char_count >= 40
        and cjk_ratio < 0.05
        and "asr_quality_insufficient" in reasons
    ):
        reasons.append("asr_language_mismatch")

    ordered_reasons = []
    for item in reasons:
        if item not in ordered_reasons:
            ordered_reasons.append(item)

    status = "passed" if not ordered_reasons else "review"
    score_label = "high" if status == "passed" else "low"
    return {
        "status": status,
        "score_label": score_label,
        "reasons": ordered_reasons,
        "duration_seconds": duration_seconds,
        "quality_min_chars": quality_min_chars,
        "char_count": char_count,
        "line_count": len(lines),
        "cjk_ratio": round(cjk_ratio, 4),
        "language_hint": language_hint,
        "unique_line_ratio": round(unique_line_ratio, 4),
    }


def collect_bilibili_failure_taxonomy(*, error_texts: list[str] | tuple[str, ...]) -> list[str]:
    taxonomy: list[str] = []
    normalized_items = [_clean_text(item).lower() for item in error_texts if _clean_text(item)]
    if not normalized_items:
        return taxonomy

    for combined in normalized_items:
        if any(token in combined for token in _DOWNLOAD_TOKENS):
            taxonomy.append("download_failure")
        if any(token in combined for token in _SUBTITLE_TOKENS):
            taxonomy.append("subtitle_missing")
        if any(token in combined for token in _ASR_QUALITY_TOKENS):
            taxonomy.append("asr_quality_insufficient")
        if any(token in combined for token in _COMMENTS_TOKENS):
            taxonomy.append("comments_api_failed")
        if (
            any(token in combined for token in _RSSHUB_DRIFT_TOKENS)
            and not any(token in combined for token in _RISK_CONTROL_TOKENS)
        ):
            taxonomy.append("rsshub_route_drift")
        if any(token in combined for token in _LOGIN_TOKENS):
            taxonomy.append("login_state_missing")
        if any(token in combined for token in _RISK_CONTROL_TOKENS):
            taxonomy.append("risk_control_or_geo_restricted")

    ordered: list[str] = []
    for label in BILIBILI_FAILURE_TAXONOMY:
        if label in taxonomy and label not in ordered:
            ordered.append(label)
    return ordered
