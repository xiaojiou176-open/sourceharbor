#!/usr/bin/env python3
"""Gemini-powered semantic UI/UX audit for frontend files.

This hook is designed for pre-push usage so we can keep pre-commit fast.
It reads GEMINI_API_KEY from environment first, then falls back to root .env.
"""

from __future__ import annotations

import json
import os
import re
import sys
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts" / "governance") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "governance"))

from common import write_json_artifact

MODEL_ENV_VAR = "GEMINI_UI_UX_AUDIT_MODEL"
FALLBACK_MODELS_ENV_VAR = "GEMINI_UI_UX_AUDIT_FALLBACK_MODELS"
THINKING_LEVEL_ENV_VAR = "GEMINI_UI_UX_AUDIT_THINKING_LEVEL"
DEFAULT_MODEL = "gemini-3.1-pro-preview"
DEFAULT_FALLBACK_MODELS = ("gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.0-flash")
DEFAULT_THINKING_LEVEL = "high"
VALID_THINKING_LEVELS = {"minimal", "low", "medium", "high"}
MAX_FILE_CHARS = 20_000
MAX_FILES_PER_REQUEST = 1
MAX_ISSUES_PER_BATCH = 3
VALID_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".css", ".scss", ".sass", ".html"}
VALID_ISSUE_CATEGORIES = {"a11y", "ux", "tokens", "responsive", "interaction", "motion", "content"}
DEFAULT_REPORT_PATH = ".runtime-cache/reports/ui-audit/gemini-ui-ux-audit-report.json"
REPORT_ENV_VAR = "GEMINI_UI_UX_AUDIT_REPORT_PATH"
DEFAULT_SCAN_ROOTS = (
    Path("apps/web/app"),
    Path("apps/web/components"),
    Path("apps/web/lib"),
)
REPORT_SCHEMA_VERSION = 5
_AUDIT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["error", "warning"]},
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "category": {
                        "type": "string",
                        "enum": sorted(VALID_ISSUE_CATEGORIES),
                    },
                    "message": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["severity", "file", "line", "category", "message", "suggestion"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "issues"],
    "additionalProperties": False,
}


class AuditBatchError(RuntimeError):
    def __init__(
        self,
        message: str,
        reason_code: str,
        provider_status: int | None,
        attempts: list[dict[str, Any]],
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.provider_status = provider_status
        self.attempts = attempts


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            values[key] = value
    return values


def _resolve_api_key(repo_root: Path) -> str | None:
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    dotenv_values = _load_env_file(repo_root / ".env")
    return dotenv_values.get("GEMINI_API_KEY", "").strip() or None


def _iter_scan_candidates(args: list[str], repo_root: Path) -> list[Path]:
    if not args:
        return [repo_root / path for path in DEFAULT_SCAN_ROOTS]
    return [(repo_root / name).resolve() for name in args]


def _filter_files(args: list[str], repo_root: Path) -> list[Path]:
    selected: list[Path] = []
    seen: set[Path] = set()
    for candidate in _iter_scan_candidates(args, repo_root):
        try:
            rel = candidate.relative_to(repo_root)
        except ValueError:
            continue
        rel_str = str(rel).replace("\\", "/")
        if not rel_str.startswith(("apps/web/app", "apps/web/components", "apps/web/lib")):
            continue
        if candidate.is_dir():
            for path in sorted(candidate.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in VALID_SUFFIXES:
                    continue
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                selected.append(resolved)
            continue
        if candidate.is_file() and candidate.suffix.lower() in VALID_SUFFIXES:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            selected.append(resolved)
    return sorted(selected, key=str)


def _file_payload(path: Path, repo_root: Path) -> str:
    rel = path.relative_to(repo_root)
    content = path.read_text(encoding="utf-8", errors="ignore")
    snippet = _render_line_numbered_snippet(content, max_chars=MAX_FILE_CHARS)
    return f"### FILE: {rel}\n```text\n{snippet}\n```\n"


def _render_line_numbered_snippet(content: str, *, max_chars: int) -> str:
    truncated = len(content) > max_chars
    snippet = content[:max_chars]
    lines = snippet.splitlines()
    numbered_lines = [f"{index + 1:04d}: {line}" for index, line in enumerate(lines)]
    rendered = "\n".join(numbered_lines)
    if truncated:
        rendered = f"{rendered}\n...TRUNCATED..."
    return rendered


def _build_prompt(batch_payload: str) -> str:
    return (
        "You are a strict principal Web UI/UX reviewer.\n"
        "Audit these files for concrete user-facing UI/UX defects, not style preferences.\n"
        "Treat this as a release gate for interaction quality.\n"
        "Focus dimensions:\n"
        "1) Accessibility (a11y): WCAG 2.2 AA essentials, keyboard flow, ARIA semantics.\n"
        "2) Interaction (interaction): loading/error/empty/success states, disabled/busy behavior, action feedback.\n"
        "3) UX clarity (ux): affordance, hierarchy, label clarity, destructive action safety.\n"
        "4) Responsive robustness (responsive): mobile overflow, tap targets, breakpoint regressions.\n"
        "5) Motion and focus (motion): reduced-motion support, focus visibility, transition side-effects.\n"
        "6) Design tokens (tokens): hardcoded spacing/colors where design tokens should be used.\n"
        "7) Content semantics (content): heading order, link/button semantics, form hints and errors.\n"
        "Severity rubric:\n"
        "- error: likely user-visible defect, accessibility failure, or broken interaction contract.\n"
        "- warning: real risk that is not clearly breaking yet.\n"
        "Return at most 3 highest-signal issues per batch. Prefer the most severe and most actionable findings.\n"
        "Only report concrete, actionable issues with file + line number.\n"
        "Keep each message and suggestion short: one sentence, ideally under 18 words.\n"
        "Line numbers in code are prefixed like '0042: ...'; use those numbers in the JSON line field.\n"
        "Return ONLY valid JSON matching this shape:\n"
        "{\n"
        '  "summary": "<one sentence>",\n'
        '  "issues": [\n'
        '    {"severity":"error|warning","file":"path","line":42,"category":"a11y|ux|tokens|responsive|interaction|motion|content","message":"...","suggestion":"..."}\n'
        "  ]\n"
        "}\n"
        'If there are no issues, return {"summary":"No actionable UI/UX issues found.","issues":[]}.\n\n'
        f"{batch_payload}"
    )


def _extract_line_report(raw: str) -> dict[str, Any]:
    summary = ""
    issues: list[dict[str, Any]] = []
    explicit_none = False
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    for line in text.splitlines():
        row = line.strip()
        if not row:
            continue
        if row.startswith("SUMMARY|"):
            summary = row.split("|", 1)[1].strip()
            continue
        if row == "ISSUE|none":
            explicit_none = True
            continue
        if not row.startswith("ISSUE|"):
            continue
        parts = row.split("|", 6)
        if len(parts) != 7:
            continue
        _, severity, file_name, line_no, category, message, suggestion = parts
        if severity not in {"error", "warning"}:
            continue
        try:
            parsed_line = int(line_no)
        except ValueError:
            parsed_line = 1
        normalized_category = category.strip().lower() or "ux"
        if normalized_category not in VALID_ISSUE_CATEGORIES:
            normalized_category = "ux"
        issues.append(
            {
                "severity": severity,
                "file": file_name.strip() or "unknown",
                "line": parsed_line,
                "category": normalized_category,
                "message": message.strip() or "issue",
                "suggestion": suggestion.strip(),
            }
        )
    return _normalize_parsed_report(summary=summary, issues=issues, explicit_none=explicit_none)


def _normalize_issue(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    severity = str(item.get("severity", "")).strip().lower()
    if severity not in {"error", "warning"}:
        return None
    category = str(item.get("category", "")).strip().lower() or "ux"
    if category not in VALID_ISSUE_CATEGORIES:
        category = "ux"
    try:
        line = int(item.get("line", 1))
    except (TypeError, ValueError):
        line = 1
    return {
        "severity": severity,
        "file": str(item.get("file", "unknown")).strip() or "unknown",
        "line": max(1, line),
        "category": category,
        "message": str(item.get("message", "issue")).strip() or "issue",
        "suggestion": str(item.get("suggestion", "")).strip(),
    }


def _normalize_parsed_report(
    *, summary: str, issues: list[dict[str, Any]], explicit_none: bool
) -> dict[str, Any]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for issue in issues:
        normalized = _normalize_issue(issue)
        if normalized is None:
            continue
        marker = (
            normalized["severity"],
            normalized["file"],
            normalized["line"],
            normalized["category"],
            normalized["message"],
            normalized["suggestion"],
        )
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(normalized)

    ranked = sorted(
        enumerate(deduped),
        key=lambda pair: (0 if pair[1]["severity"] == "error" else 1, pair[0]),
    )
    capped = [issue for _, issue in ranked[:MAX_ISSUES_PER_BATCH]]
    return {
        "summary": summary.strip(),
        "issues": capped,
        "explicit_none": explicit_none and not capped,
    }


def _extract_json_payload(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if not text:
        return None
    candidates: list[str] = [text]
    fenced_blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(block.strip() for block in fenced_blocks if block.strip())
    decoder = json.JSONDecoder()
    for candidate in candidates:
        with suppress(json.JSONDecodeError):
            payload = json.loads(candidate)
            if isinstance(payload, dict):
                return payload
        for index, char in enumerate(candidate):
            if char != "{":
                continue
            with suppress(json.JSONDecodeError):
                payload, _ = decoder.raw_decode(candidate[index:])
                if isinstance(payload, dict):
                    return payload
    return None


def _extract_json_report(raw: str) -> dict[str, Any] | None:
    payload = _extract_json_payload(raw)
    if payload is None:
        return None
    summary = str(payload.get("summary", "")).strip()
    raw_issues = payload.get("issues", [])
    if not isinstance(raw_issues, list):
        return None
    return _normalize_parsed_report(
        summary=summary,
        issues=raw_issues,
        explicit_none=len(raw_issues) == 0,
    )


def _extract_audit_report(raw: str) -> dict[str, Any]:
    parsed_json = _extract_json_report(raw)
    if parsed_json is not None:
        return parsed_json
    return _extract_line_report(raw)


def _candidate_models() -> list[str]:
    primary_model = os.getenv(MODEL_ENV_VAR, DEFAULT_MODEL).strip() or DEFAULT_MODEL
    fallback_raw = os.getenv(FALLBACK_MODELS_ENV_VAR, "")
    fallback_models = _parse_csv(fallback_raw) if fallback_raw else list(DEFAULT_FALLBACK_MODELS)
    deduped: list[str] = []
    for model in (primary_model, *fallback_models):
        if model and model not in deduped:
            deduped.append(model)
    return deduped


def _parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _normalize_thinking_level(raw: str) -> tuple[str, str | None]:
    normalized = raw.strip().lower()
    if not normalized:
        return DEFAULT_THINKING_LEVEL, "missing_thinking_level"
    if normalized in VALID_THINKING_LEVELS:
        return normalized, None
    return DEFAULT_THINKING_LEVEL, "invalid_thinking_level"


def _build_generate_config(genai_types: Any) -> tuple[Any, dict[str, Any]]:
    requested_level = os.getenv(THINKING_LEVEL_ENV_VAR, DEFAULT_THINKING_LEVEL)
    normalized_level, normalization_reason = _normalize_thinking_level(requested_level)
    config_kwargs: dict[str, Any] = {
        "temperature": 0.0,
        "max_output_tokens": 6_000,
        "response_mime_type": "application/json",
        "response_json_schema": _AUDIT_RESPONSE_SCHEMA,
    }
    applied_level: str | None = None
    fallback_reason = normalization_reason
    thinking_config_cls = getattr(genai_types, "ThinkingConfig", None)
    if callable(thinking_config_cls):
        try:
            config_kwargs["thinking_config"] = thinking_config_cls(
                thinking_level=normalized_level.upper()
            )
            applied_level = normalized_level
        except Exception as exc:  # pragma: no cover - defensive for sdk incompatibilities
            fallback_reason = f"thinking_config_rejected:{type(exc).__name__}"
    else:
        fallback_reason = fallback_reason or "thinking_config_unsupported"
    return genai_types.GenerateContentConfig(**config_kwargs), {
        "thinking_level_requested": requested_level.strip().lower() or DEFAULT_THINKING_LEVEL,
        "thinking_level_normalized": normalized_level,
        "thinking_level_applied": applied_level,
        "thinking_level_fallback_reason": fallback_reason,
    }


def _extract_response_text(response: Any) -> str:
    text = str(getattr(response, "text", "") or "").strip()
    if text:
        return text
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, dict):
        return json.dumps(parsed, ensure_ascii=False)
    return ""


def _build_invalid_response_issue(
    batch: list[Path], repo_root: Path, *, reason_code: str
) -> dict[str, Any]:
    file_name = "unknown"
    if batch:
        with suppress(ValueError):
            file_name = str(batch[0].relative_to(repo_root))
    return {
        "severity": "error",
        "file": file_name,
        "line": 1,
        "category": "content",
        "message": f"Gemini output format invalid for batch ({reason_code}).",
        "suggestion": "Retry this file batch and inspect model_attempts for raw provider output.",
    }


def _extract_provider_status(exc: Exception) -> int | None:
    visited: set[int] = set()
    pending: list[BaseException] = [exc]

    while pending:
        current = pending.pop()
        marker = id(current)
        if marker in visited:
            continue
        visited.add(marker)

        for attr in ("status_code", "http_status", "status", "code"):
            value = getattr(current, attr, None)
            if isinstance(value, int) and 100 <= value <= 599:
                return value
            if isinstance(value, str) and value.isdigit():
                parsed = int(value)
                if 100 <= parsed <= 599:
                    return parsed

        response = getattr(current, "response", None)
        if response is not None:
            status_code = getattr(response, "status_code", None)
            if isinstance(status_code, int) and 100 <= status_code <= 599:
                return status_code

        for nested in (getattr(current, "__cause__", None), getattr(current, "__context__", None)):
            if isinstance(nested, BaseException):
                pending.append(nested)

    message = str(exc)
    for pattern in (
        r"\bHTTP\s+(\d{3})\b",
        r"\bstatus(?:\s*code)?\s*[:=]?\s*(\d{3})\b",
    ):
        matched = re.search(pattern, message, flags=re.IGNORECASE)
        if not matched:
            continue
        parsed = int(matched.group(1))
        if 100 <= parsed <= 599:
            return parsed
    return None


def _classify_error(exc: Exception) -> tuple[str, int | None]:
    message = str(exc)
    upper_message = message.upper()
    provider_status = _extract_provider_status(exc)

    if "invalid_response_format" in message:
        return "invalid_response_format", provider_status
    if (
        provider_status == 403
        or "API_KEY_SERVICE_BLOCKED" in upper_message
        or "PERMISSION_DENIED" in upper_message
    ):
        return "provider_blocked", provider_status or 403
    if provider_status == 401 or "UNAUTHENTICATED" in upper_message:
        return "provider_auth_error", provider_status or 401
    if provider_status == 429 or "RESOURCE_EXHAUSTED" in upper_message:
        return "provider_rate_limited", provider_status or 429
    return "request_failed", provider_status


def _audit_batch(client: Any, genai_types: Any, payload: str) -> dict[str, Any]:
    last_error: Exception | None = None
    attempts: list[dict[str, Any]] = []
    config, thinking_meta = _build_generate_config(genai_types)
    candidate_models = _candidate_models()
    primary_model = candidate_models[0] if candidate_models else DEFAULT_MODEL
    for model_name in candidate_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=_build_prompt(payload),
                config=config,
            )
            text = _extract_response_text(response)
            if not text:
                raise RuntimeError(f"empty response from Gemini model={model_name}")
            parsed = _extract_audit_report(text)
            if not parsed["issues"] and not parsed["explicit_none"]:
                raise RuntimeError(
                    f"invalid_response_format: model={model_name} did not emit structured issues"
                )
            attempts.append(
                {
                    "model": model_name,
                    "status": "ok",
                    "reason_code": "ok",
                    "provider_status": None,
                }
            )
            if model_name != primary_model:
                print(
                    f"gemini-ui-ux-audit: fallback model in use ({model_name})",
                    file=sys.stderr,
                )
            return {
                "parsed": parsed,
                "model": model_name,
                "attempts": attempts,
                "thinking_meta": thinking_meta,
            }
        except Exception as exc:  # pragma: no cover - network/sdk defensive path
            last_error = exc
            reason_code, provider_status = _classify_error(exc)
            attempts.append(
                {
                    "model": model_name,
                    "status": "failed",
                    "reason_code": reason_code,
                    "provider_status": provider_status,
                    "error": str(exc),
                }
            )
            continue
    failure_reason = "request_failed"
    provider_status = None
    if last_error is not None:
        failure_reason, provider_status = _classify_error(last_error)
    raise AuditBatchError(
        message=f"all Gemini model candidates failed: {last_error}",
        reason_code=failure_reason,
        provider_status=provider_status,
        attempts=attempts,
    )


def _resolve_report_path(repo_root: Path) -> Path:
    configured = os.getenv(REPORT_ENV_VAR, DEFAULT_REPORT_PATH).strip()
    target = Path(configured).expanduser()
    if not target.is_absolute():
        target = repo_root / target
    return target


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    write_json_artifact(
        path,
        payload,
        source_entrypoint="scripts/ci/gemini_ui_ux_audit.py",
        verification_scope="ui-audit-report",
        source_run_id="ci-gemini-ui-ux-audit",
        freshness_window_hours=24,
        extra={"report_kind": "ui-audit-report"},
    )


def _summarize_issues(issues: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, int]]:
    severity_counts: dict[str, int] = {"error": 0, "warning": 0}
    category_counts: dict[str, int] = {}
    for issue in issues:
        severity = str(issue.get("severity") or "").lower()
        if severity in severity_counts:
            severity_counts[severity] += 1
        category = str(issue.get("category") or "").lower() or "ux"
        category_counts[category] = category_counts.get(category, 0) + 1
    return severity_counts, category_counts


def main() -> int:
    repo_root = Path.cwd()
    report_path = _resolve_report_path(repo_root)
    requested_thinking_level = os.getenv(THINKING_LEVEL_ENV_VAR, DEFAULT_THINKING_LEVEL)
    normalized_thinking_level, normalization_reason = _normalize_thinking_level(
        requested_thinking_level
    )
    thinking_meta: dict[str, Any] = {
        "thinking_level_requested": requested_thinking_level.strip().lower()
        or DEFAULT_THINKING_LEVEL,
        "thinking_level_normalized": normalized_thinking_level,
        "thinking_level_applied": None,
        "thinking_level_fallback_reason": normalization_reason,
    }
    files = _filter_files(sys.argv[1:], repo_root)
    batch_count = (len(files) + MAX_FILES_PER_REQUEST - 1) // MAX_FILES_PER_REQUEST if files else 0
    if not files:
        print("gemini-ui-ux-audit: no frontend files to audit")
        _write_report(
            report_path,
            {
                "status": "skipped",
                "reason": "no_frontend_files",
                "reason_code": "no_frontend_files",
                "provider_status": None,
                "report_schema_version": REPORT_SCHEMA_VERSION,
                "generated_at": datetime.now(UTC).isoformat(),
                "files": [],
                "batch_count": 0,
                "successful_batches": 0,
                "issue_count": 0,
                "blocking_count": 0,
                "warning_count": 0,
                "severity_counts": {"error": 0, "warning": 0},
                "category_counts": {},
                "summaries": [],
                "model_attempts": [],
                "thinking_meta": {
                    **thinking_meta,
                    "thinking_level_fallback_reason": "not_evaluated_no_files",
                },
                "failed_batch_count": 0,
                "failed_batches": [],
            },
        )
        return 0

    api_key = _resolve_api_key(repo_root)
    if not api_key:
        print(
            "gemini-ui-ux-audit: GEMINI_API_KEY not found in environment or .env",
            file=sys.stderr,
        )
        _write_report(
            report_path,
            {
                "status": "failed",
                "reason": "missing_gemini_api_key",
                "reason_code": "missing_gemini_api_key",
                "provider_status": None,
                "report_schema_version": REPORT_SCHEMA_VERSION,
                "generated_at": datetime.now(UTC).isoformat(),
                "files": [str(path.relative_to(repo_root)) for path in files],
                "batch_count": batch_count,
                "successful_batches": 0,
                "issue_count": 0,
                "blocking_count": 0,
                "warning_count": 0,
                "severity_counts": {"error": 0, "warning": 0},
                "category_counts": {},
                "summaries": [],
                "model_attempts": [],
                "thinking_meta": {
                    **thinking_meta,
                    "thinking_level_fallback_reason": "not_evaluated_missing_api_key",
                },
                "failed_batch_count": 0,
                "failed_batches": [],
            },
        )
        return 1

    try:
        from google import genai
        from google.genai import types as genai_types
    except Exception as exc:  # pragma: no cover - defensive path
        print(f"gemini-ui-ux-audit: google-genai unavailable: {exc}", file=sys.stderr)
        _write_report(
            report_path,
            {
                "status": "failed",
                "reason": f"sdk_unavailable: {exc}",
                "reason_code": "sdk_unavailable",
                "provider_status": None,
                "report_schema_version": REPORT_SCHEMA_VERSION,
                "generated_at": datetime.now(UTC).isoformat(),
                "files": [str(path.relative_to(repo_root)) for path in files],
                "batch_count": batch_count,
                "successful_batches": 0,
                "issue_count": 0,
                "blocking_count": 0,
                "warning_count": 0,
                "severity_counts": {"error": 0, "warning": 0},
                "category_counts": {},
                "summaries": [],
                "model_attempts": [],
                "thinking_meta": {
                    **thinking_meta,
                    "thinking_level_fallback_reason": "sdk_unavailable",
                },
                "failed_batch_count": 0,
                "failed_batches": [],
            },
        )
        return 1

    client = genai.Client(api_key=api_key)
    all_issues: list[dict[str, Any]] = []
    summaries: list[str] = []
    model_attempts: list[dict[str, Any]] = []
    provider_status: int | None = None
    used_models: list[str] = []
    successful_batches = 0
    failed_batches: list[dict[str, Any]] = []
    for i in range(0, len(files), MAX_FILES_PER_REQUEST):
        batch = files[i : i + MAX_FILES_PER_REQUEST]
        payload = "\n".join(_file_payload(path, repo_root) for path in batch)
        try:
            batch_result = _audit_batch(client, genai_types, payload)
        except Exception as exc:  # pragma: no cover - defensive for hook runtime
            if isinstance(exc, AuditBatchError):
                reason_code = exc.reason_code
                provider_status = exc.provider_status
                model_attempts.extend(exc.attempts)
                if reason_code == "invalid_response_format":
                    failed_batches.append(
                        {
                            "files": [str(path.relative_to(repo_root)) for path in batch],
                            "reason_code": reason_code,
                            "provider_status": provider_status,
                            "attempts": exc.attempts,
                        }
                    )
                    all_issues.append(
                        _build_invalid_response_issue(
                            batch,
                            repo_root,
                            reason_code=reason_code,
                        )
                    )
                    summaries.append(
                        "Gemini output was malformed for one batch; marked as blocking issue."
                    )
                    continue
            else:
                reason_code, provider_status = _classify_error(exc)
            print(
                "gemini-ui-ux-audit: request failed: "
                f"reason_code={reason_code} provider_status={provider_status} error={exc}",
                file=sys.stderr,
            )
            _write_report(
                report_path,
                {
                    "status": "failed",
                    "reason": f"{reason_code}: {exc}",
                    "reason_code": reason_code,
                    "provider_status": provider_status,
                    "report_schema_version": REPORT_SCHEMA_VERSION,
                    "generated_at": datetime.now(UTC).isoformat(),
                    "files": [str(path.relative_to(repo_root)) for path in files],
                    "batch_count": batch_count,
                    "successful_batches": successful_batches,
                    "issue_count": len(all_issues),
                    "blocking_count": len(
                        [
                            item
                            for item in all_issues
                            if str(item.get("severity", "")).lower() == "error"
                        ]
                    ),
                    "warning_count": len(
                        [
                            item
                            for item in all_issues
                            if str(item.get("severity", "")).lower() == "warning"
                        ]
                    ),
                    "severity_counts": _summarize_issues(all_issues)[0],
                    "category_counts": _summarize_issues(all_issues)[1],
                    "summaries": summaries,
                    "model_attempts": model_attempts,
                    "thinking_meta": thinking_meta,
                    "failed_batch_count": len(failed_batches),
                    "failed_batches": failed_batches,
                },
            )
            return 1
        model_attempts.extend(batch_result.get("attempts", []))
        batch_thinking_meta = batch_result.get("thinking_meta")
        if isinstance(batch_thinking_meta, dict):
            thinking_meta = batch_thinking_meta
        model_name = str(batch_result.get("model", "")).strip()
        if model_name:
            used_models.append(model_name)
        parsed = batch_result["parsed"]
        successful_batches += 1
        summary = str(parsed.get("summary", "")).strip()
        if summary:
            summaries.append(summary)
        for issue in parsed.get("issues", []):
            if isinstance(issue, dict):
                all_issues.append(issue)

    blocking = [i for i in all_issues if str(i.get("severity", "")).lower() == "error"]

    if all_issues:
        print("gemini-ui-ux-audit: findings")
        for issue in all_issues:
            file_name = issue.get("file", "unknown")
            line = issue.get("line", "?")
            severity = str(issue.get("severity", "warning")).upper()
            message = issue.get("message", "issue")
            suggestion = issue.get("suggestion", "")
            print(f"- [{severity}] {file_name}:{line} {message}")
            if suggestion:
                print(f"  -> {suggestion}")
    else:
        print("gemini-ui-ux-audit: no issues found")

    if summaries:
        print("gemini-ui-ux-audit: summaries")
        for line in summaries:
            print(f"- {line}")

    if blocking:
        print(
            f"gemini-ui-ux-audit: failed with {len(blocking)} error-level issue(s)",
            file=sys.stderr,
        )

    reason_code = "ok"
    if blocking:
        reason_code = "batch_failures_detected" if failed_batches else "blocking_issues_detected"
    warning_count = len(
        [item for item in all_issues if str(item.get("severity", "")).lower() == "warning"]
    )
    severity_counts, category_counts = _summarize_issues(all_issues)
    if reason_code == "ok":
        provider_status = None
    elif provider_status is None:
        for attempt in model_attempts:
            candidate_status = attempt.get("provider_status")
            if isinstance(candidate_status, int) and 100 <= candidate_status <= 599:
                provider_status = candidate_status
                break
    _write_report(
        report_path,
        {
            "status": "failed" if blocking else "passed",
            "reason": reason_code,
            "reason_code": reason_code,
            "provider_status": provider_status,
            "report_schema_version": REPORT_SCHEMA_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "files": [str(path.relative_to(repo_root)) for path in files],
            "batch_count": batch_count,
            "successful_batches": successful_batches,
            "issue_count": len(all_issues),
            "blocking_count": len(blocking),
            "warning_count": warning_count,
            "severity_counts": severity_counts,
            "category_counts": category_counts,
            "summaries": summaries,
            "issues": all_issues,
            "model_attempts": model_attempts,
            "used_models": used_models,
            "thinking_meta": thinking_meta,
            "failed_batch_count": len(failed_batches),
            "failed_batches": failed_batches,
        },
    )
    print(f"gemini-ui-ux-audit: report -> {report_path}")
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
