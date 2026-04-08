from __future__ import annotations

import base64
import concurrent.futures
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import tempfile
import threading
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from apps.runtime_paths import get_runtime_cache_root, get_runtime_root
from integrations.providers.gemini import build_gemini_client, load_gemini_sdk

from ..config import Settings

_PLAYWRIGHT_HINTS = {
    "playwright",
    "trace",
    "screenshot",
    "snapshot",
    "axe",
    "a11y",
    "accessibility",
    "lighthouse",
}

_FINDING_SEVERITY_MAP = {
    "critical": "critical",
    "serious": "high",
    "high": "high",
    "moderate": "medium",
    "medium": "medium",
    "minor": "low",
    "low": "low",
    "info": "info",
}

_JSON_SUFFIXES = {".json", ".ndjson"}
_MAX_SCAN_FILES = 400
_MAX_GEMINI_IMAGE_BYTES = 5 * 1024 * 1024
_MAX_GEMINI_TEXT_CHARS = 2_000
_MAX_GEMINI_IMAGES = 4
_MAX_GEMINI_TEXT_SNIPPETS = 4
_TEXT_SUFFIXES = {".md", ".txt", ".json", ".ndjson", ".log"}
_DEFAULT_ARTIFACT_BASE_ROOT = tempfile.gettempdir()
_DEFAULT_UI_AUDIT_RUN_STORE = ".runtime-cache/evidence/tests/ui-audit-runs"
_DEFAULT_MODEL_TIMEOUT_SECONDS = 15.0
_DEFAULT_MODEL_MAX_RETRIES = 1
_REPO_ROOT = get_runtime_root()
_RUNTIME_CACHE_ROOT = get_runtime_cache_root()
_EVIDENCE_INDEX_ROOT = _RUNTIME_CACHE_ROOT / "reports" / "evidence-index"

_GEMINI_UI_AUDIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["overall_assessment", "findings", "suggested_actions"],
    "properties": {
        "overall_assessment": {"type": "string", "minLength": 1},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["severity", "title", "message"],
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "high", "medium", "low", "info"],
                    },
                    "title": {"type": "string", "minLength": 1},
                    "message": {"type": "string", "minLength": 1},
                    "artifact_key": {"type": ["string", "null"]},
                    "rule": {"type": ["string", "null"]},
                },
            },
        },
        "suggested_actions": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
    },
}


def _runtime_metadata_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.meta.json")


def _repo_relative_path(path: Path) -> str:
    try:
        return path.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _current_git_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip()
    return commit or None


def _write_runtime_metadata_sidecar(
    path: Path,
    *,
    source_entrypoint: str,
    verification_scope: str,
    source_run_id: str,
    freshness_window_hours: int | None,
    created_at: str | None,
    extra: dict[str, Any] | None = None,
) -> None:
    metadata_path = _runtime_metadata_path(path)
    payload: dict[str, Any] = {
        "version": 1,
        "artifact_path": _repo_relative_path(path),
        "created_at": created_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source_entrypoint": source_entrypoint,
        "source_run_id": source_run_id,
        "verification_scope": verification_scope,
        "freshness_window_hours": freshness_window_hours,
    }
    if (source_commit := _current_git_commit()) is not None:
        payload["source_commit"] = source_commit
    if extra:
        payload.update(extra)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _write_evidence_index(path: Path, *, run_id: str) -> None:
    artifact_rel_path = _repo_relative_path(path)
    payload = {
        "version": 1,
        "run_id": run_id,
        "logs": [],
        "reports": [],
        "evidence": [artifact_rel_path],
    }
    index_path = _EVIDENCE_INDEX_ROOT / f"{run_id}.json"
    if index_path.is_file():
        with suppress(OSError, json.JSONDecodeError):
            existing = json.loads(index_path.read_text(encoding="utf-8"))
            payload = {
                "version": 1,
                "run_id": run_id,
                "logs": sorted({*existing.get("logs", []), *payload["logs"]}),
                "reports": sorted({*existing.get("reports", []), *payload["reports"]}),
                "evidence": sorted({*existing.get("evidence", []), artifact_rel_path}),
            }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_runtime_metadata_sidecar(
        index_path,
        source_entrypoint="apps.api.app.services.ui_audit.UiAuditService",
        verification_scope="evidence-index",
        source_run_id=run_id,
        freshness_window_hours=24,
        created_at=None,
        extra={"report_kind": "evidence-index"},
    )


class UiAuditService:
    _run_store: dict[str, dict[str, Any]] = {}
    _store_lock = threading.Lock()

    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def run(
        self,
        *,
        job_id: uuid.UUID | None = None,
        artifact_root: str | None = None,
    ) -> dict[str, Any]:
        resolved_root = self._resolve_artifact_root(job_id=job_id, artifact_root=artifact_root)
        run_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()

        if resolved_root is None:
            payload = {
                "run_id": run_id,
                "job_id": str(job_id) if job_id is not None else None,
                "artifact_root": None,
                "status": "not_found",
                "created_at": created_at,
                "summary": {
                    "artifact_count": 0,
                    "finding_count": 0,
                    "severity_counts": {},
                },
                "findings": [],
                "artifacts": [],
            }
            self._save_run(payload)
            return payload

        artifacts = self._collect_artifacts(resolved_root)
        findings = self._collect_findings(artifacts)
        gemini_suggested_actions: list[str] = []
        gemini_review_meta = self._build_gemini_review_meta(status="skipped", reason_code="not_run")
        gemini_review = self._run_gemini_review(artifacts)
        gemini_review_meta = gemini_review.get("meta", gemini_review_meta)
        findings.extend(gemini_review.get("findings", []))
        gemini_suggested_actions = gemini_review.get("suggested_actions", [])
        overall = str(gemini_review.get("overall_assessment") or "").strip()
        if overall:
            findings.append(
                {
                    "id": "gemini-overall-assessment",
                    "severity": "info",
                    "title": "Gemini UI/UX Overall Assessment",
                    "message": overall,
                    "rule": "gemini-overall-assessment",
                    "artifact_key": None,
                }
            )
        severity_counts = self._build_severity_counts(findings)
        status = "completed"
        gemini_status = str(gemini_review_meta.get("status") or "").lower()
        if gemini_status == "failed":
            status = "completed_with_gemini_failure"
        elif gemini_status == "skipped":
            status = "completed_with_gemini_skipped"

        payload = {
            "run_id": run_id,
            "job_id": str(job_id) if job_id is not None else None,
            "artifact_root": str(resolved_root),
            "status": status,
            "created_at": created_at,
            "summary": {
                "artifact_count": len(artifacts),
                "finding_count": len(findings),
                "severity_counts": severity_counts,
            },
            "findings": findings,
            "artifacts": artifacts,
            "gemini_review": gemini_review_meta,
            "gemini_suggested_actions": gemini_suggested_actions,
        }
        self._save_run(payload)
        return payload

    def get(self, run_id: str) -> dict[str, Any] | None:
        payload = self._load_run(run_id)
        if payload is None:
            return None
        return {
            "run_id": payload["run_id"],
            "job_id": payload.get("job_id"),
            "artifact_root": payload.get("artifact_root"),
            "status": payload.get("status"),
            "created_at": payload.get("created_at"),
            "summary": payload.get("summary")
            or {
                "artifact_count": 0,
                "finding_count": 0,
                "severity_counts": {},
            },
            "gemini_review": payload.get("gemini_review"),
        }

    def list_findings(
        self, *, run_id: str, severity: str | None = None
    ) -> list[dict[str, Any]] | None:
        payload = self._load_run(run_id)
        if payload is None:
            return None

        findings = payload.get("findings") if isinstance(payload, dict) else None
        finding_items = findings if isinstance(findings, list) else []
        if severity is None:
            return [item for item in finding_items if isinstance(item, dict)]

        target = severity.strip().lower()
        return [
            item
            for item in finding_items
            if isinstance(item, dict) and str(item.get("severity") or "").lower() == target
        ]

    def list_artifacts(self, *, run_id: str) -> list[dict[str, Any]] | None:
        payload = self._load_run(run_id)
        if payload is None:
            return None

        artifacts = payload.get("artifacts") if isinstance(payload, dict) else None
        return (
            [item for item in artifacts if isinstance(item, dict)]
            if isinstance(artifacts, list)
            else []
        )

    def get_artifact(
        self,
        *,
        run_id: str,
        key: str,
        include_base64: bool = False,
    ) -> dict[str, Any] | None:
        artifacts = self.list_artifacts(run_id=run_id)
        if artifacts is None:
            return None

        selected = next((item for item in artifacts if item.get("key") == key), None)
        if selected is None:
            return None

        path_value = selected.get("path")
        if not isinstance(path_value, str):
            return None

        target = Path(path_value).expanduser()
        if not target.exists() or not target.is_file():
            return None

        payload = dict(selected)
        payload["exists"] = True
        payload["base64"] = None
        if include_base64:
            try:
                payload["base64"] = base64.b64encode(target.read_bytes()).decode("ascii")
            except OSError:
                return None
        return payload

    def autofix(
        self,
        *,
        run_id: str,
        mode: str = "dry-run",
        max_files: int = 3,
        max_changed_lines: int = 120,
    ) -> dict[str, Any] | None:
        payload = self._load_run(run_id)
        if payload is None:
            return None

        findings = payload.get("findings") if isinstance(payload, dict) else None
        finding_items = findings if isinstance(findings, list) else []
        high_or_worse = 0
        for item in finding_items:
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity") or "info").lower()
            if severity in {"critical", "high"}:
                high_or_worse += 1

        suggested_actions: list[str] = []
        gemini_suggestions = payload.get("gemini_suggested_actions")
        if isinstance(gemini_suggestions, list):
            suggested_actions.extend(
                str(item).strip() for item in gemini_suggestions if str(item).strip()
            )
        if high_or_worse > 0:
            suggested_actions.append("Fix high-severity UI issues first and rerun focused E2E.")
        if finding_items:
            suggested_actions.append(
                "Apply minimal patches and rerun failed tests before full suite."
            )
        if not finding_items:
            suggested_actions.append("No findings detected; no code changes recommended.")

        effective_mode = "dry-run"
        requested_mode = "apply" if mode == "apply" else "dry-run"
        guardrail_note = "This endpoint currently returns a dry-run plan only."
        if requested_mode == "apply":
            guardrail_note = (
                "Requested apply mode is not supported yet; returning a persisted dry-run plan."
            )

        return {
            "run_id": run_id,
            "mode": effective_mode,
            "autofix_applied": False,
            "summary": {
                "finding_count": len([item for item in finding_items if isinstance(item, dict)]),
                "high_or_worse_count": int(high_or_worse),
            },
            "guardrails": {
                "max_files": int(max_files),
                "max_changed_lines": int(max_changed_lines),
                "requested_mode": requested_mode,
                "effective_mode": effective_mode,
                "note": guardrail_note,
            },
            "suggested_actions": suggested_actions,
        }

    def _run_gemini_review(self, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
        settings = Settings.from_env()
        if not self._is_gemini_ui_audit_enabled(settings):
            return self._gemini_review_result(status="skipped", reason_code="disabled")
        api_key = (settings.gemini_api_key or "").strip()
        if not api_key:
            return self._gemini_review_result(
                status="skipped", reason_code="missing_gemini_api_key"
            )

        try:
            sdk = load_gemini_sdk()
            genai_types = sdk.genai_types
        except Exception as exc:
            return self._gemini_review_result(
                status="failed",
                reason_code="sdk_unavailable",
                findings=[
                    {
                        "id": "gemini-ui-review-sdk-unavailable",
                        "severity": "high",
                        "title": "Gemini UI review unavailable",
                        "message": f"Gemini SDK unavailable: {exc}",
                        "rule": "gemini-ui-review-sdk-unavailable",
                        "artifact_key": None,
                    }
                ],
            )

        image_artifacts = self._select_gemini_image_artifacts(artifacts)
        text_snippets = self._select_gemini_text_snippets(artifacts)
        if not image_artifacts and not text_snippets:
            return self._gemini_review_result(
                status="skipped", reason_code="no_supported_artifacts"
            )

        model = (settings.gemini_model or "gemini-3.1-pro-preview").strip()
        thinking_level = (settings.gemini_thinking_level or "high").strip().upper()
        prompt = self._build_gemini_ui_prompt(
            text_snippets=text_snippets, image_artifacts=image_artifacts
        )
        contents: list[Any] = [prompt]
        for item in image_artifacts:
            path = Path(str(item.get("path") or ""))
            if not path.exists() or not path.is_file():
                continue
            mime_type = str(item.get("mime_type") or "image/png")
            try:
                contents.append(
                    genai_types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type)
                )
            except OSError:
                continue

        timeout_seconds = self._read_float_env(
            "UI_AUDIT_MODEL_TIMEOUT_SECONDS",
            default=_DEFAULT_MODEL_TIMEOUT_SECONDS,
            min_value=1.0,
            max_value=120.0,
        )
        max_retries = self._read_int_env(
            "UI_AUDIT_MODEL_MAX_RETRIES",
            default=_DEFAULT_MODEL_MAX_RETRIES,
            min_value=0,
            max_value=3,
        )

        try:
            client = build_gemini_client(api_key=api_key)
            response = self._generate_with_timeout_and_retry(
                client=client,
                model=model,
                contents=contents,
                config=self._build_gemini_generate_config(
                    genai_types=genai_types,
                    thinking_level=thinking_level,
                ),
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
        except Exception as exc:
            return self._gemini_review_result(
                status="failed",
                reason_code="provider_error",
                provider_status=self._extract_provider_status(exc),
                model=model,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                findings=[
                    {
                        "id": "gemini-ui-review-provider-error",
                        "severity": "high",
                        "title": "Gemini UI review unavailable",
                        "message": f"Gemini UI review failed due to provider error: {exc}",
                        "rule": "gemini-ui-review-provider-error",
                        "artifact_key": None,
                    }
                ],
            )

        raw_text = str(getattr(response, "text", "") or "").strip()
        if not raw_text:
            return self._gemini_review_result(
                status="failed",
                reason_code="empty_response",
                model=model,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                findings=[
                    {
                        "id": "gemini-ui-review-empty-response",
                        "severity": "high",
                        "title": "Gemini UI review empty response",
                        "message": "Gemini returned an empty response; review result ignored.",
                        "rule": "gemini-ui-review-empty-response",
                        "artifact_key": None,
                    }
                ],
            )
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            return self._gemini_review_result(
                status="failed",
                reason_code="invalid_json",
                model=model,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                findings=[
                    {
                        "id": "gemini-ui-review-invalid-json",
                        "severity": "high",
                        "title": "Gemini UI review parse fallback",
                        "message": "Gemini returned non-JSON output; review result ignored.",
                        "rule": "gemini-ui-review-invalid-json",
                        "artifact_key": None,
                    }
                ],
            )
        normalized = self._normalize_gemini_review(parsed)
        normalized["meta"] = self._build_gemini_review_meta(
            status="passed",
            reason_code="ok",
            provider_status=None,
            model=model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        return normalized

    def _generate_with_timeout_and_retry(
        self,
        *,
        client: Any,
        model: str,
        contents: list[Any],
        config: Any,
        timeout_seconds: float,
        max_retries: int,
    ) -> Any:
        attempts = max_retries + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        client.models.generate_content,
                        model=model,
                        contents=contents,
                        config=config,
                    )
                    return future.result(timeout=timeout_seconds)
            except concurrent.futures.TimeoutError:
                last_error = TimeoutError(
                    f"ui audit model timeout after {timeout_seconds:.1f}s (attempt {attempt}/{attempts})"
                )
            except Exception as exc:
                last_error = exc
            if attempt >= attempts:
                break
        raise RuntimeError(
            str(last_error) if last_error is not None else "ui audit model call failed"
        )

    def _resolve_artifact_root(
        self,
        *,
        job_id: uuid.UUID | None,
        artifact_root: str | None,
    ) -> Path | None:
        base_root = self._artifact_base_root()
        if artifact_root and artifact_root.strip():
            raw_path = artifact_root.strip()
            path_parts = PurePosixPath(raw_path).parts
            if raw_path.startswith(("/", "\\")) or any(part in {"..", "."} for part in path_parts):
                return None
            relative_path = Path(*[part for part in path_parts if part not in {"", "/"}])
            if not relative_path.parts:
                return None
            path = base_root / relative_path
            resolved = self._resolve_if_within_base(path=path, base_root=base_root)
            if resolved is not None and resolved.exists() and resolved.is_dir():
                return resolved
            return None

        if job_id is None or self.db is None:
            return None

        statement = text(
            """
            SELECT artifact_root
            FROM jobs
            WHERE CAST(id AS TEXT) = :job_id
            LIMIT 1
            """
        )
        try:
            row = self.db.execute(statement, {"job_id": str(job_id)}).mappings().first()
        except DBAPIError:
            self.db.rollback()
            return None

        root_value = row.get("artifact_root") if row is not None else None
        if not isinstance(root_value, str) or not root_value.strip():
            return None

        path = Path(root_value).expanduser()
        resolved = self._resolve_if_within_base(path=path, base_root=base_root)
        return (
            resolved if resolved is not None and resolved.exists() and resolved.is_dir() else None
        )

    def _artifact_base_root(self) -> Path:
        configured = os.getenv("UI_AUDIT_ARTIFACT_BASE_ROOT", _DEFAULT_ARTIFACT_BASE_ROOT)
        return Path(configured).expanduser().resolve(strict=False)

    def _resolve_if_within_base(self, *, path: Path, base_root: Path) -> Path | None:
        resolved = path.resolve(strict=False)
        try:
            resolved.relative_to(base_root)
        except ValueError:
            return None
        if resolved == base_root:
            return None
        return resolved

    def _collect_artifacts(self, root: Path) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for path in root.rglob("*"):
            if len(payload) >= _MAX_SCAN_FILES:
                break
            try:
                if not path.is_file():
                    continue
            except OSError:
                continue
            relative = path.relative_to(root).as_posix()
            mime_type, _ = mimetypes.guess_type(path.name)
            category = "playwright" if self._is_playwright_artifact(relative) else "artifact"
            try:
                size_bytes = path.stat().st_size
            except OSError:
                size_bytes = 0
            payload.append(
                {
                    "key": relative,
                    "path": str(path),
                    "mime_type": mime_type or "application/octet-stream",
                    "size_bytes": int(size_bytes),
                    "category": category,
                }
            )
        return payload

    def _is_gemini_ui_audit_enabled(self, settings: Settings) -> bool:
        return bool(settings.ui_audit_gemini_enabled)

    def _select_gemini_image_artifacts(
        self, artifacts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        for item in artifacts:
            mime_type = str(item.get("mime_type") or "").lower()
            if not mime_type.startswith("image/"):
                continue
            size_bytes = int(item.get("size_bytes") or 0)
            if size_bytes <= 0 or size_bytes > _MAX_GEMINI_IMAGE_BYTES:
                continue
            selected.append(item)
            if len(selected) >= _MAX_GEMINI_IMAGES:
                break
        return selected

    def _select_gemini_text_snippets(self, artifacts: list[dict[str, Any]]) -> list[dict[str, str]]:
        snippets: list[dict[str, str]] = []
        for item in artifacts:
            key = str(item.get("key") or "")
            path_value = str(item.get("path") or "")
            path = Path(path_value)
            if not key or not path.exists() or not path.is_file():
                continue
            if path.suffix.lower() not in _TEXT_SUFFIXES:
                continue
            normalized = self._read_text_prefix(path, max_chars=_MAX_GEMINI_TEXT_CHARS)
            if not normalized:
                continue
            snippets.append(
                {
                    "key": key,
                    "snippet": normalized,
                }
            )
            if len(snippets) >= _MAX_GEMINI_TEXT_SNIPPETS:
                break
        return snippets

    def _read_text_prefix(self, path: Path, *, max_chars: int) -> str | None:
        chunks: list[str] = []
        total = 0
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                while total < max_chars:
                    chunk = handle.read(min(4096, max_chars - total))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
        except OSError:
            return None
        return "".join(chunks).strip() or None

    def _read_float_env(
        self, name: str, *, default: float, min_value: float, max_value: float
    ) -> float:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = float(raw.strip())
        except (TypeError, ValueError):
            return default
        return min(max(value, min_value), max_value)

    def _read_int_env(self, name: str, *, default: int, min_value: int, max_value: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = int(raw.strip())
        except (TypeError, ValueError):
            return default
        return min(max(value, min_value), max_value)

    def _build_gemini_ui_prompt(
        self,
        *,
        text_snippets: list[dict[str, str]],
        image_artifacts: list[dict[str, Any]],
    ) -> str:
        snippet_lines = []
        for item in text_snippets:
            snippet_lines.append(f"- {item['key']}: {item['snippet']}")
        image_lines = [
            f"- {item.get('key') or ''!s}"
            for item in image_artifacts
            if str(item.get("key") or "").strip()
        ]
        evidence_text = "\n".join(snippet_lines) if snippet_lines else "- none"
        evidence_images = "\n".join(image_lines) if image_lines else "- none"
        return (
            "You are a strict Web UI/UX quality reviewer. Analyze screenshots and Playwright evidence. "
            "Return ONLY JSON that follows the provided schema.\n"
            "Rules:\n"
            "1) Focus on concrete, user-visible defects in interaction quality.\n"
            "2) Evaluate accessibility, interaction states, feedback clarity, responsive behavior, and hierarchy.\n"
            "3) Severity must be one of critical/high/medium/low/info.\n"
            "4) Every finding should reference artifact_key when possible.\n"
            "5) Keep suggested_actions short, actionable, and test-oriented.\n"
            f"Text evidence snippets:\n{evidence_text}\n"
            f"Image evidence keys:\n{evidence_images}\n"
        )

    def _build_gemini_generate_config(self, *, genai_types: Any, thinking_level: str) -> Any:
        config_kwargs: dict[str, Any] = {
            "temperature": 1.0,
            "response_mime_type": "application/json",
            "response_json_schema": _GEMINI_UI_AUDIT_SCHEMA,
        }
        thinking_config_cls = getattr(genai_types, "ThinkingConfig", None)
        if callable(thinking_config_cls):
            with suppress(Exception):
                config_kwargs["thinking_config"] = thinking_config_cls(
                    thinking_level=thinking_level,
                )
        return genai_types.GenerateContentConfig(**config_kwargs)

    def _normalize_gemini_review(self, payload: Any) -> dict[str, Any]:
        source = payload if isinstance(payload, dict) else {}
        overall = str(source.get("overall_assessment") or "").strip()
        suggested = source.get("suggested_actions")
        raw_suggested = suggested if isinstance(suggested, list) else []
        suggested_actions = [str(item).strip() for item in raw_suggested if str(item).strip()]
        findings_source = source.get("findings")
        raw_findings = findings_source if isinstance(findings_source, list) else []
        findings: list[dict[str, Any]] = []
        for index, item in enumerate(raw_findings):
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity") or "medium").strip().lower()
            if severity not in {"critical", "high", "medium", "low", "info"}:
                severity = "medium"
            title = str(item.get("title") or "").strip() or "Gemini UI review finding"
            message = str(item.get("message") or "").strip()
            if not message:
                continue
            rule = str(item.get("rule") or "").strip() or None
            artifact_key = str(item.get("artifact_key") or "").strip() or None
            findings.append(
                {
                    "id": f"gemini-finding-{index + 1}",
                    "severity": severity,
                    "title": title,
                    "message": message,
                    "rule": rule,
                    "artifact_key": artifact_key,
                }
            )
        return {
            "overall_assessment": overall,
            "findings": findings,
            "suggested_actions": suggested_actions,
        }

    def _gemini_review_result(
        self,
        *,
        status: str,
        reason_code: str,
        provider_status: int | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        findings: list[dict[str, Any]] | None = None,
        overall_assessment: str = "",
        suggested_actions: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "meta": self._build_gemini_review_meta(
                status=status,
                reason_code=reason_code,
                provider_status=provider_status,
                model=model,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            ),
            "overall_assessment": overall_assessment,
            "findings": findings or [],
            "suggested_actions": suggested_actions or [],
        }

    def _build_gemini_review_meta(
        self,
        *,
        status: str,
        reason_code: str,
        provider_status: int | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "reason_code": reason_code,
            "provider_status": provider_status,
            "model": model,
            "timeout_seconds": timeout_seconds,
            "max_retries": max_retries,
        }

    def _extract_provider_status(self, exc: Exception) -> int | None:
        for attr in ("status_code", "http_status", "status", "code"):
            value = getattr(exc, attr, None)
            if isinstance(value, int) and 100 <= value <= 599:
                return value
            if isinstance(value, str) and value.isdigit():
                parsed = int(value)
                if 100 <= parsed <= 599:
                    return parsed

        response = getattr(exc, "response", None)
        if response is not None:
            status_code = getattr(response, "status_code", None)
            if isinstance(status_code, int) and 100 <= status_code <= 599:
                return status_code

        matched = re.search(r"\b(?:HTTP|status(?:\s*code)?)\s*[:=]?\s*(\d{3})\b", str(exc), re.I)
        if matched:
            return int(matched.group(1))
        return None

    def _collect_findings(self, artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        for artifact in artifacts:
            path_value = artifact.get("path")
            key = artifact.get("key")
            if not isinstance(path_value, str) or not isinstance(key, str):
                continue

            path = Path(path_value)
            if path.suffix.lower() not in _JSON_SUFFIXES:
                continue

            parsed = self._load_json(path)
            if parsed is None:
                continue

            findings.extend(self._extract_findings_from_json(parsed, artifact_key=key))

        if findings:
            return findings

        if any(item.get("category") == "playwright" for item in artifacts):
            return [
                {
                    "id": "evidence-collected",
                    "severity": "info",
                    "title": "Playwright evidence collected",
                    "message": "No structured findings were parsed, but Playwright artifacts were found.",
                    "rule": None,
                    "artifact_key": None,
                }
            ]

        return []

    def _extract_findings_from_json(
        self, payload: Any, *, artifact_key: str
    ) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []

        findings: list[dict[str, Any]] = []

        violations = payload.get("violations")
        if isinstance(violations, list):
            for index, item in enumerate(violations):
                if not isinstance(item, dict):
                    continue
                impact = str(item.get("impact") or "medium").lower()
                severity = _FINDING_SEVERITY_MAP.get(impact, "medium")
                findings.append(
                    {
                        "id": f"{artifact_key}#violation-{index + 1}",
                        "severity": severity,
                        "title": str(
                            item.get("help") or item.get("id") or "Accessibility violation"
                        ),
                        "message": str(
                            item.get("description") or "A UI accessibility issue was detected."
                        ),
                        "rule": str(item.get("id") or ""),
                        "artifact_key": artifact_key,
                    }
                )

        generic_items = payload.get("findings")
        if isinstance(generic_items, list):
            for index, item in enumerate(generic_items):
                if not isinstance(item, dict):
                    continue
                severity_raw = str(item.get("severity") or "medium").lower()
                findings.append(
                    {
                        "id": str(item.get("id") or f"{artifact_key}#finding-{index + 1}"),
                        "severity": _FINDING_SEVERITY_MAP.get(severity_raw, "medium"),
                        "title": str(item.get("title") or "UI audit finding"),
                        "message": str(item.get("message") or item.get("description") or ""),
                        "rule": str(item.get("rule") or "") or None,
                        "artifact_key": artifact_key,
                    }
                )

        return findings

    def _load_json(self, path: Path) -> dict[str, Any] | None:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return None

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None

        return payload if isinstance(payload, dict) else None

    def _is_playwright_artifact(self, relative: str) -> bool:
        normalized = relative.lower()
        return any(token in normalized for token in _PLAYWRIGHT_HINTS)

    def _build_severity_counts(self, findings: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in findings:
            severity = str(item.get("severity") or "info").lower()
            counts[severity] = counts.get(severity, 0) + 1
        return counts

    def _save_run(self, payload: dict[str, Any]) -> None:
        run_id = str(payload.get("run_id") or "")
        if not run_id:
            return
        with self._store_lock:
            self._run_store[run_id] = payload
        self._persist_run_to_disk(run_id, payload)

    def _load_run(self, run_id: str) -> dict[str, Any] | None:
        with self._store_lock:
            payload = self._run_store.get(run_id)
        if payload is not None:
            return payload
        payload = self._load_run_from_disk(run_id)
        if payload is None:
            return None
        with self._store_lock:
            self._run_store[run_id] = payload
        return payload

    def _run_store_dir(self) -> Path:
        configured = os.getenv("UI_AUDIT_RUN_STORE_DIR", _DEFAULT_UI_AUDIT_RUN_STORE)
        base = Path(configured).expanduser()
        if not base.is_absolute():
            base = _REPO_ROOT / base
        return base.resolve(strict=False)

    def _run_store_path(self, run_id: str) -> Path:
        digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
        return self._run_store_dir() / f"{digest}.json"

    def _persist_run_to_disk(self, run_id: str, payload: dict[str, Any]) -> None:
        path = self._run_store_path(run_id)
        temp_path = path.with_suffix(".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            temp_path.replace(path)
            self._write_run_metadata(path, run_id=run_id, payload=payload)
        except OSError:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
            return

    def _write_run_metadata(self, path: Path, *, run_id: str, payload: dict[str, Any]) -> None:
        created_at = str(payload.get("created_at") or "").strip() or None
        resolved_path = path.resolve(strict=False)
        if (
            resolved_path != _RUNTIME_CACHE_ROOT
            and _RUNTIME_CACHE_ROOT not in resolved_path.parents
        ):
            return
        with suppress(OSError, ValueError, TypeError):
            _write_runtime_metadata_sidecar(
                path,
                source_entrypoint="apps.api.app.services.ui_audit.UiAuditService",
                verification_scope="ui-audit-run-store",
                source_run_id=run_id,
                freshness_window_hours=336,
                created_at=created_at,
                extra={
                    "classification": "debug-evidence",
                    "runtime_subdir": "evidence",
                    "owner": "platform",
                },
            )
            _write_evidence_index(path, run_id=run_id)

    def _load_run_from_disk(self, run_id: str) -> dict[str, Any] | None:
        path = self._run_store_path(run_id)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        if str(payload.get("run_id") or "") != run_id:
            return None
        return payload
