from __future__ import annotations

import difflib
import json
import os
import sqlite3
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..config import settings
from ..repositories import JobsRepository

_ARTIFACT_ALIAS_TO_FILE = {
    "meta": "meta.json",
    "comments": "comments.json",
    "danmaku": "danmaku.json",
    "outline": "outline.json",
    "transcript": "transcript.txt",
    "digest": "digest.md",
    "knowledge_cards": "knowledge_cards.json",
}
_ARTIFACT_ALLOWED_FILENAMES = set(_ARTIFACT_ALIAS_TO_FILE.values())
_ARTIFACT_ALLOWED_FRAME_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class JobsService:
    def __init__(self, db: Session) -> None:
        self.repo = JobsRepository(db)

    def get_job(self, job_id: uuid.UUID):
        return self.repo.get(job_id)

    def compare_with_previous(self, *, job_id: uuid.UUID) -> dict[str, Any] | None:
        current = self.get_job(job_id)
        if current is None:
            return None

        previous = self.repo.get_previous_successful_job(job_id=job_id)
        current_digest = self._read_digest_text(getattr(current, "artifact_digest_md", None))
        previous_digest = (
            self._read_digest_text(getattr(previous, "artifact_digest_md", None))
            if previous is not None
            else None
        )

        if previous_digest is None:
            return {
                "job_id": str(current.id),
                "previous_job_id": None,
                "has_previous": False,
                "current_digest": current_digest,
                "previous_digest": None,
                "diff_markdown": "",
                "stats": {
                    "added_lines": 0,
                    "removed_lines": 0,
                    "changed": False,
                },
            }

        current_lines = (current_digest or "").splitlines()
        previous_lines = previous_digest.splitlines()
        diff_lines = list(
            difflib.unified_diff(
                previous_lines,
                current_lines,
                fromfile=f"job:{previous.id}",
                tofile=f"job:{current.id}",
                lineterm="",
            )
        )
        added_lines = sum(
            1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
        )
        removed_lines = sum(
            1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
        )
        return {
            "job_id": str(current.id),
            "previous_job_id": str(previous.id),
            "has_previous": True,
            "current_digest": current_digest,
            "previous_digest": previous_digest,
            "diff_markdown": "\n".join(diff_lines),
            "stats": {
                "added_lines": added_lines,
                "removed_lines": removed_lines,
                "changed": bool(diff_lines),
            },
        }

    def resolve_llm_gate_fields(
        self,
        *,
        llm_required: bool | None,
        llm_gate_passed: bool | None,
        hard_fail_reason: str | None,
        steps: list[dict[str, object]],
    ) -> tuple[bool, bool | None, str | None]:
        required = True if llm_required is None else llm_required
        if llm_gate_passed is not None:
            reason = hard_fail_reason if llm_gate_passed is False else None
            return required, llm_gate_passed, reason

        llm_steps = [item for item in steps if item.get("name") in {"llm_outline", "llm_digest"}]
        if not llm_steps:
            return required, None, hard_fail_reason

        failed = next((item for item in llm_steps if item.get("status") == "failed"), None)
        if failed is not None:
            error = failed.get("error")
            reason = None
            if isinstance(error, dict):
                raw = error.get("reason") or error.get("error")
                if isinstance(raw, str) and raw.strip():
                    reason = raw.strip()
            return required, False, reason or hard_fail_reason or "llm_step_failed"

        all_ok = all(item.get("status") in {"succeeded", "skipped"} for item in llm_steps)
        return required, (True if all_ok else None), (None if all_ok else hard_fail_reason)

    def get_pipeline_final_status(self, job_id: uuid.UUID, *, fallback_status: str) -> str | None:
        status = self.repo.get_pipeline_final_status(job_id=job_id)
        if status in {"succeeded", "degraded", "failed"}:
            return status
        if fallback_status in {"succeeded", "degraded", "failed"}:
            return fallback_status
        return None

    def get_steps(self, job_id: uuid.UUID) -> list[dict[str, object]]:
        try:
            conn = sqlite3.connect(settings.sqlite_state_path)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error:
            return []

        try:
            rows = conn.execute(
                """
                SELECT
                    step_name,
                    status,
                    attempt,
                    started_at,
                    finished_at,
                    error_json,
                    error_kind,
                    retry_meta_json,
                    result_json,
                    cache_key
                FROM step_runs
                WHERE job_id = ?
                ORDER BY attempt ASC, started_at ASC, step_name ASC
                """,
                (str(job_id),),
            ).fetchall()
        except sqlite3.Error:
            return []
        finally:
            conn.close()

        result: list[dict[str, object]] = []
        for row in rows:
            error_value = self._json_loads(row["error_json"])
            retry_meta = self._json_loads(row["retry_meta_json"])
            result_payload = self._json_loads(row["result_json"])
            thought_metadata = self._extract_thought_metadata(result_payload)

            result.append(
                {
                    "name": row["step_name"],
                    "status": row["status"],
                    "attempt": row["attempt"],
                    "started_at": row["started_at"],
                    "finished_at": row["finished_at"],
                    "error": error_value,
                    "error_kind": row["error_kind"],
                    "retry_meta": retry_meta if isinstance(retry_meta, dict) else None,
                    "result": result_payload if isinstance(result_payload, dict) else None,
                    "thought_metadata": thought_metadata,
                    "cache_key": row["cache_key"],
                }
            )

        return result

    def _extract_thought_metadata(self, result_payload: Any) -> dict[str, Any]:
        empty = self._empty_thought_metadata()
        if not isinstance(result_payload, dict):
            return empty

        legacy_payload: dict[str, Any] = {}
        for key in ("thought_metadata", "thinking_metadata", "thoughts_metadata", "thoughts"):
            value = result_payload.get(key)
            if isinstance(value, dict):
                legacy_payload = dict(value)
                break

        llm_meta = result_payload.get("llm_meta")
        llm_meta_dict = llm_meta if isinstance(llm_meta, dict) else {}
        llm_thinking = llm_meta_dict.get("thinking")
        llm_thinking_dict = llm_thinking if isinstance(llm_thinking, dict) else {}

        merged = dict(legacy_payload)
        normalized_thinking = self._normalize_thinking_payload(legacy_payload, llm_thinking_dict)
        merged["thinking"] = normalized_thinking
        merged["thought_count"] = normalized_thinking["thought_count"]
        merged["thought_signatures"] = list(normalized_thinking["thought_signatures"])
        merged["thought_signature_digest"] = normalized_thinking["thought_signature_digest"]

        provider = merged.get("provider")
        if not isinstance(provider, str) or not provider.strip():
            thinking_provider = llm_thinking_dict.get("provider")
            if isinstance(thinking_provider, str) and thinking_provider.strip():
                merged["provider"] = thinking_provider.strip()
            else:
                llm_provider = llm_meta_dict.get("provider")
                if isinstance(llm_provider, str) and llm_provider.strip():
                    merged["provider"] = llm_provider.strip()

        return merged or empty

    def _normalize_thinking_payload(
        self,
        legacy_payload: dict[str, Any],
        llm_thinking_payload: dict[str, Any],
    ) -> dict[str, Any]:
        empty = self._empty_thinking_payload()

        source = llm_thinking_payload or legacy_payload
        if not isinstance(source, dict):
            return empty

        normalized = self._empty_thinking_payload()
        for key in ("enabled", "include_thoughts"):
            value = source.get(key)
            if isinstance(value, bool):
                normalized[key] = value

        level = source.get("level")
        if isinstance(level, str) and level.strip():
            normalized["level"] = level.strip().lower()

        thought_count = source.get("thought_count")
        if isinstance(thought_count, int):
            normalized["thought_count"] = max(0, thought_count)

        thought_signatures = source.get("thought_signatures")
        if isinstance(thought_signatures, list):
            normalized["thought_signatures"] = [
                item.strip()
                for item in thought_signatures
                if isinstance(item, str) and item.strip()
            ]

        signature_digest = source.get("thought_signature_digest")
        if isinstance(signature_digest, str) and signature_digest.strip():
            normalized["thought_signature_digest"] = signature_digest.strip()

        usage = source.get("usage")
        if isinstance(usage, dict):
            normalized["usage"] = dict(usage)
        elif isinstance(source.get("thought_tokens"), int):
            normalized["usage"] = {"thoughts_token_count": int(source["thought_tokens"])}

        if normalized["thought_count"] == 0 and normalized["thought_signatures"]:
            normalized["thought_count"] = len(normalized["thought_signatures"])

        return normalized

    def _empty_thought_metadata(self) -> dict[str, Any]:
        return {
            "thinking": self._empty_thinking_payload(),
            "thought_count": 0,
            "thought_signatures": [],
            "thought_signature_digest": None,
        }

    def _empty_thinking_payload(self) -> dict[str, Any]:
        return {
            "enabled": None,
            "level": None,
            "include_thoughts": None,
            "thought_count": 0,
            "thought_signatures": [],
            "thought_signature_digest": None,
            "usage": {},
        }

    def get_step_summary(self, job_id: uuid.UUID) -> list[dict[str, object]]:
        return [
            {
                "name": item["name"],
                "status": item["status"],
                "attempt": item["attempt"],
                "started_at": item["started_at"],
                "finished_at": item["finished_at"],
                "error": item["error"],
            }
            for item in self.get_steps(job_id)
        ]

    def get_notification_retry(self, job_id: uuid.UUID) -> dict[str, object] | None:
        query = text(
            """
            SELECT
                id::text AS delivery_id,
                status,
                attempt_count,
                next_retry_at,
                last_error_kind
            FROM notification_deliveries
            WHERE kind = 'video_digest'
              AND job_id = CAST(:job_id AS UUID)
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        try:
            row = self.repo.db.execute(query, {"job_id": str(job_id)}).mappings().first()
        except DBAPIError:
            self.repo.db.rollback()
            return None
        if row is None:
            return None
        return {
            "delivery_id": row.get("delivery_id"),
            "status": row.get("status"),
            "attempt_count": int(row.get("attempt_count") or 0),
            "next_retry_at": row.get("next_retry_at"),
            "last_error_kind": row.get("last_error_kind"),
        }

    def get_degradations(
        self,
        *,
        artifact_root: str | None,
        artifact_digest_md: str | None,
        steps: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        meta = self._read_artifact_meta(artifact_root=artifact_root, digest_path=artifact_digest_md)
        degradations = meta.get("degradations")
        if isinstance(degradations, list):
            return [item for item in degradations if isinstance(item, dict)]

        fallback: list[dict[str, object]] = []
        for step in steps:
            step_name = step.get("name")
            step_status = step.get("status")
            step_error = step.get("error")
            step_result = step.get("result")
            should_collect = step_status in {"failed", "skipped"} or (
                isinstance(step_result, dict) and bool(step_result.get("degraded"))
            )
            if not should_collect:
                continue

            record: dict[str, object] = {
                "step": str(step_name) if step_name else None,
                "status": str(step_status) if step_status else None,
            }
            if isinstance(step_error, dict):
                if "reason" in step_error:
                    record["reason"] = step_error.get("reason")
                if "error" in step_error:
                    record["error"] = step_error.get("error")
                if "error_kind" in step_error:
                    record["error_kind"] = step_error.get("error_kind")
                if "retry_meta" in step_error:
                    record["retry_meta"] = step_error.get("retry_meta")
            elif step_error is not None:
                record["error"] = step_error

            if isinstance(step_result, dict):
                if "reason" in step_result and "reason" not in record:
                    record["reason"] = step_result.get("reason")
                if "error" in step_result and "error" not in record:
                    record["error"] = step_result.get("error")
                if "error_kind" in step_result and "error_kind" not in record:
                    record["error_kind"] = step_result.get("error_kind")
                if "retry_meta" in step_result and "retry_meta" not in record:
                    record["retry_meta"] = step_result.get("retry_meta")
                if "cache_meta" in step_result:
                    record["cache_meta"] = step_result.get("cache_meta")
            fallback.append(record)

        return fallback

    def get_artifacts_index(
        self,
        *,
        artifact_root: str | None,
        artifact_digest_md: str | None,
        steps: list[dict[str, object]],
    ) -> dict[str, str]:
        from_steps = self._artifacts_from_steps(steps)
        if from_steps:
            return from_steps

        index: dict[str, str] = {}
        if artifact_root:
            root = Path(artifact_root).expanduser()
            known_files = {
                "meta": "meta.json",
                "comments": "comments.json",
                "danmaku": "danmaku.json",
                "transcript": "transcript.txt",
                "outline": "outline.json",
                "digest": "digest.md",
                "knowledge_cards": "knowledge_cards.json",
            }
            for key, name in known_files.items():
                path = root / name
                if path.exists() and path.is_file():
                    index[key] = str(path.resolve())

        if artifact_digest_md:
            digest_path = Path(artifact_digest_md).expanduser()
            if digest_path.exists() and digest_path.is_file():
                index["digest"] = str(digest_path.resolve())

        return index

    def get_artifact_payload(
        self, *, job_id: uuid.UUID | None, video_url: str | None
    ) -> dict[str, Any] | None:
        digest_path: str | None
        if job_id is not None:
            digest_path = self.repo.get_artifact_digest_md(job_id=job_id)
        elif video_url:
            digest_path = self.repo.get_artifact_digest_md_by_video_url(video_url=video_url)
        else:
            return None

        if not digest_path:
            return None

        path = Path(digest_path)
        if not path.exists() or not path.is_file():
            return None
        try:
            markdown = path.read_text(encoding="utf-8")
        except OSError:
            return None
        return {
            "markdown": markdown,
            "meta": self._read_artifact_meta(artifact_root=None, digest_path=str(path)),
        }

    def get_artifact_asset(self, *, job_id: uuid.UUID, path: str) -> Path | None:
        row = self.get_job(job_id)
        if row is None:
            return None

        artifact_root = self._resolve_artifact_root(
            artifact_root=getattr(row, "artifact_root", None),
            digest_path=getattr(row, "artifact_digest_md", None),
        )
        if artifact_root is None:
            return None

        normalized_path = self._normalize_artifact_asset_path(path)
        if not normalized_path:
            return None

        raw_parts = PurePosixPath(normalized_path).parts
        if normalized_path.startswith(("/", "\\")) or any(
            part in {"..", "."} for part in raw_parts
        ):
            return None
        requested = Path(*[part for part in raw_parts if part not in {"", "/"}])
        if not requested.parts:
            return None
        target = artifact_root / requested

        try:
            resolved_root = artifact_root.resolve(strict=True)
            resolved_target = target.resolve(strict=True)
        except OSError:
            return None

        if not resolved_target.is_file():
            return None

        try:
            relative_path = resolved_target.relative_to(resolved_root).as_posix()
        except ValueError:
            return None

        if not self._is_allowed_artifact_asset(relative_path):
            return None
        return resolved_target

    def get_artifact_digest_md(
        self, *, job_id: uuid.UUID | None, video_url: str | None
    ) -> str | None:
        payload = self.get_artifact_payload(job_id=job_id, video_url=video_url)
        if payload is None:
            return None
        markdown = payload.get("markdown")
        return str(markdown) if isinstance(markdown, str) else None

    def get_knowledge_cards(self, *, job_id: uuid.UUID) -> list[dict[str, Any]] | None:
        row = self.get_job(job_id)
        if row is None:
            return None

        artifact_root = self._resolve_artifact_root(
            artifact_root=getattr(row, "artifact_root", None),
            digest_path=getattr(row, "artifact_digest_md", None),
        )
        if artifact_root is None:
            return []

        cards_path = artifact_root / "knowledge_cards.json"
        if not cards_path.exists() or not cards_path.is_file():
            return []
        try:
            payload = json.loads(cards_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    def build_evidence_bundle(self, *, job_id: uuid.UUID) -> dict[str, Any] | None:
        row = self.get_job(job_id)
        if row is None:
            return None

        steps = self.get_steps(job_id)
        step_summary = [
            {
                "name": item["name"],
                "status": item["status"],
                "attempt": item["attempt"],
                "started_at": item["started_at"],
                "finished_at": item["finished_at"],
                "error": item.get("error"),
            }
            for item in steps
        ]
        comparison = self.compare_with_previous(job_id=job_id)
        knowledge_cards = self.get_knowledge_cards(job_id=job_id) or []
        digest_payload = self.get_artifact_payload(job_id=job_id, video_url=None) or {}
        artifact_meta = (
            dict(digest_payload.get("meta") or {})
            if isinstance(digest_payload.get("meta"), dict)
            else {}
        )
        digest_meta = self._flatten_digest_meta(artifact_meta)
        rich_evidence = self._build_rich_evidence(artifact_meta, digest_meta)

        llm_required, llm_gate_passed, hard_fail_reason = self.resolve_llm_gate_fields(
            llm_required=getattr(row, "llm_required", None),
            llm_gate_passed=getattr(row, "llm_gate_passed", None),
            hard_fail_reason=getattr(row, "hard_fail_reason", None),
            steps=steps,
        )
        pipeline_final_status = self.get_pipeline_final_status(job_id, fallback_status=row.status)
        artifacts_index = self.get_artifacts_index(
            artifact_root=row.artifact_root,
            artifact_digest_md=row.artifact_digest_md,
            steps=steps,
        )

        return {
            "bundle_kind": "sourceharbor_job_evidence_bundle_v1",
            "sharing_scope": "internal",
            "sample": False,
            "generated_at": datetime.now(UTC).isoformat(),
            "proof_boundary": (
                "Internal evidence bundle only. Do not treat this as hosted proof, release proof, "
                "or a durable public document."
            ),
            "job": {
                "id": str(row.id),
                "video_id": str(row.video_id),
                "kind": row.kind,
                "status": row.status,
                "pipeline_final_status": pipeline_final_status,
                "mode": row.mode,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
                "error_message": row.error_message,
            },
            "trace_summary": {
                "step_count": len(step_summary),
                "degradations": self.get_degradations(
                    artifact_root=row.artifact_root,
                    artifact_digest_md=row.artifact_digest_md,
                    steps=steps,
                ),
                "notification_retry": self.get_notification_retry(job_id),
                "llm_required": llm_required,
                "llm_gate_passed": llm_gate_passed,
                "hard_fail_reason": hard_fail_reason,
            },
            "digest": digest_payload.get("markdown"),
            "digest_meta": digest_meta or None,
            "rich_evidence": rich_evidence or None,
            "comparison": comparison,
            "knowledge_cards": knowledge_cards,
            "artifact_manifest": artifacts_index,
            "step_summary": step_summary,
        }

    def _flatten_digest_meta(self, artifact_meta: dict[str, Any]) -> dict[str, Any]:
        metadata = artifact_meta.get("metadata")
        flattened = dict(metadata or {}) if isinstance(metadata, dict) else dict(artifact_meta)
        raw_stage_contract = artifact_meta.get("raw_stage_contract")
        if isinstance(raw_stage_contract, dict):
            flattened["raw_stage_contract"] = raw_stage_contract
        for key in ("download_mode", "media_path", "subtitle_files", "frame_files", "generated_at"):
            if key in artifact_meta:
                flattened[key] = artifact_meta.get(key)
        return flattened

    def _build_rich_evidence(
        self, artifact_meta: dict[str, Any], digest_meta: dict[str, Any]
    ) -> dict[str, Any]:
        def _present(value: Any) -> bool:
            if value is None:
                return False
            if isinstance(value, str):
                return bool(value.strip())
            if isinstance(value, (list, dict, tuple, set)):
                return bool(value)
            return True

        payload: dict[str, Any] = {}
        danmaku = artifact_meta.get("danmaku")
        if isinstance(danmaku, dict) and danmaku:
            payload["danmaku"] = danmaku
        site_objects = digest_meta.get("site_objects")
        if isinstance(site_objects, dict) and site_objects:
            payload["site_objects"] = site_objects

        creator_metadata = {
            key: digest_meta.get(key)
            for key in ("uploader", "uploader_mid", "uploader_url", "uploader_avatar")
            if _present(digest_meta.get(key))
        }
        if creator_metadata:
            payload["creator_metadata"] = creator_metadata

        video_metadata = {
            key: digest_meta.get(key)
            for key in (
                "view_count",
                "like_count",
                "comment_count",
                "danmaku_count",
                "coin_count",
                "favorite_count",
                "share_count",
                "category",
                "category_id",
                "bilibili_aid",
                "bilibili_bvid",
                "bilibili_cid",
                "chapters",
            )
            if _present(digest_meta.get(key))
        }
        if video_metadata:
            payload["video_metadata"] = video_metadata
        return payload

    def _read_digest_text(self, digest_path: str | None) -> str | None:
        if not isinstance(digest_path, str) or not digest_path.strip():
            return None
        path = Path(digest_path).expanduser()
        if not path.exists() or not path.is_file():
            return None
        try:
            payload = path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return payload or None

    def _read_artifact_meta(
        self, *, artifact_root: str | None, digest_path: str | None
    ) -> dict[str, Any]:
        candidates: list[Path] = []
        if artifact_root:
            candidates.append(Path(artifact_root).expanduser() / "meta.json")
        if digest_path:
            candidates.append(Path(digest_path).expanduser().parent / "meta.json")

        for candidate in candidates:
            if not candidate.exists():
                continue
            if not candidate.is_file():
                continue
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                return payload
        return {}

    def _artifacts_from_steps(self, steps: list[dict[str, object]]) -> dict[str, str]:
        for step in reversed(steps):
            if step.get("name") != "write_artifacts":
                continue
            result = step.get("result")
            if not isinstance(result, dict):
                continue

            files = None
            output = result.get("output")
            if isinstance(output, dict):
                files = output.get("files")
            if not isinstance(files, dict):
                state_updates = result.get("state_updates")
                if isinstance(state_updates, dict):
                    files = state_updates.get("artifacts")
            if not isinstance(files, dict):
                continue

            index = {
                str(key): str(value)
                for key, value in files.items()
                if isinstance(key, str) and isinstance(value, str) and value
            }
            if index:
                return index
        return {}

    def _normalize_artifact_asset_path(self, path: str) -> str:
        normalized = path.strip()
        if not normalized:
            return ""
        alias = _ARTIFACT_ALIAS_TO_FILE.get(normalized.lower())
        return alias or normalized

    def _resolve_artifact_root(
        self, *, artifact_root: str | None, digest_path: str | None
    ) -> Path | None:
        artifact_base_root = (
            Path(settings.pipeline_artifact_root).expanduser().resolve(strict=False)
        )
        allow_temp_test_root = bool(os.getenv("PYTEST_CURRENT_TEST"))
        if artifact_root:
            root_path = Path(artifact_root).expanduser()
            try:
                resolved_root = root_path.resolve(strict=True)
            except OSError:
                resolved_root = None
            if (
                resolved_root is not None
                and resolved_root.is_dir()
                and self._is_path_within_root(
                    resolved_root,
                    artifact_base_root,
                    allow_temp_test_root=allow_temp_test_root,
                )
            ):
                return resolved_root

        if digest_path:
            digest_file = Path(digest_path).expanduser()
            try:
                resolved_digest = digest_file.resolve(strict=True)
            except OSError:
                return None
            if (
                resolved_digest.is_file()
                and resolved_digest.parent.is_dir()
                and self._is_path_within_root(
                    resolved_digest.parent,
                    artifact_base_root,
                    allow_temp_test_root=allow_temp_test_root,
                )
            ):
                return resolved_digest.parent

        return None

    def _is_path_within_root(
        self, path: Path, root: Path, *, allow_temp_test_root: bool = False
    ) -> bool:
        try:
            path.relative_to(root)
            return path != root
        except ValueError:
            if allow_temp_test_root:
                temp_root = Path(tempfile.gettempdir()).resolve(strict=False)
                temp_roots = {temp_root}
                if temp_root.is_absolute():
                    private_variant = Path("/private") / temp_root.relative_to(temp_root.anchor)
                    temp_roots.add(private_variant)
                for temp_candidate in temp_roots:
                    try:
                        path.relative_to(temp_candidate)
                        return path != temp_candidate
                    except ValueError:
                        continue
                return False
            return False

    def _is_allowed_artifact_asset(self, relative_path: str) -> bool:
        normalized = relative_path.strip("/")
        if not normalized:
            return False

        rel_file = Path(normalized)
        filename = rel_file.name.lower()
        if "/" not in normalized and filename in _ARTIFACT_ALLOWED_FILENAMES:
            return True

        return (
            filename.startswith("frame_")
            and rel_file.suffix.lower() in _ARTIFACT_ALLOWED_FRAME_EXTENSIONS
        )

    def _json_loads(self, payload: str | None) -> Any:
        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return {"raw": payload}
