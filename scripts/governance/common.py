#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

_SENSITIVE_TEXT_PATTERNS = (
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE), "Bearer ***REDACTED***"),
    (re.compile(r"Basic\s+[A-Za-z0-9+/=._\-]+", re.IGNORECASE), "Basic ***REDACTED***"),
    (
        re.compile(r"([a-z][a-z0-9+.\-]*://)([^:@/\s]+):([^@/\s]+)@", re.IGNORECASE),
        r"\1***:***@",
    ),
    (re.compile(r"(sk-[A-Za-z0-9]{20,})"), "sk-***REDACTED***"),
    (re.compile(r"(ghp_[A-Za-z0-9]{20,})"), "ghp_***REDACTED***"),
    (re.compile(r"(github_pat_[A-Za-z0-9_]+)"), "github_pat_***REDACTED***"),
    (re.compile(r"(AKIA[0-9A-Z]{16})"), "AKIA***REDACTED***"),
    (re.compile(r"(ASIA[0-9A-Z]{16})"), "ASIA***REDACTED***"),
    (
        re.compile(
            r"([?&](?:api[_-]?key|apikey|key|token|access[_-]?token|refresh[_-]?token|id[_-]?token|oauth[_-]?token|jwt|secret|client[_-]?secret|password|passwd|session(?:id)?|auth(?:orization)?|signature)=)[^&\s]+",
            re.IGNORECASE,
        ),
        r"\1***REDACTED***",
    ),
    (
        re.compile(
            r"((?:^|[{,\s])(?:\"|')?(?:password|passwd|token|access[_-]?token|refresh[_-]?token|id[_-]?token|oauth[_-]?token|api[_-]?key|apikey|secret|client[_-]?secret|session(?:id)?|signature)(?:\"|')?\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^,\s}\]&]+)",
            re.IGNORECASE,
        ),
        r"\1***REDACTED***",
    ),
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        "-----BEGIN ***REDACTED*** PRIVATE KEY-----",
    ),
)

_SENSITIVE_FIELD_NAME_PATTERN = re.compile(
    r"^(?:password|passwd|token|access[_-]?token|refresh[_-]?token|id[_-]?token|oauth[_-]?token|api[_-]?key|apikey|secret|client[_-]?secret|session(?:id)?|auth(?:orization)?|signature|cookie)$",
    re.IGNORECASE,
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_governance_json(name: str) -> dict[str, Any]:
    path = repo_root() / "config" / "governance" / name
    return json.loads(path.read_text(encoding="utf-8"))


def rel_path(path: Path) -> str:
    try:
        return path.relative_to(repo_root()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def top_level_entries() -> list[Path]:
    return sorted(repo_root().iterdir(), key=lambda item: item.name)


def git_output(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root(),
        check=check,
        capture_output=True,
        text=True,
    )
    return result.stdout


def git_tracked_paths() -> set[str]:
    return {line.strip() for line in git_output("ls-files").splitlines() if line.strip()}


def git_is_tracked(path: str, *, tracked_paths: set[str] | None = None) -> bool:
    tracked = tracked_paths if tracked_paths is not None else git_tracked_paths()
    normalized = path.strip("/")
    if normalized in tracked:
        return True
    prefix = normalized + "/"
    return any(item == normalized or item.startswith(prefix) for item in tracked)


def current_git_commit() -> str:
    return git_output("rev-parse", "HEAD").strip()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def find_forbidden_runtime_entries(patterns: list[str]) -> list[str]:
    root = repo_root()
    allowed_runtime_root = root / ".runtime-cache"
    ignored_dir_names = {".git"}
    matches: set[str] = set()

    for path in root.rglob("*"):
        if any(part in ignored_dir_names for part in path.parts):
            continue
        if path == allowed_runtime_root or _is_within(path, allowed_runtime_root):
            continue
        if any(fnmatch(path.name, pattern) for pattern in patterns):
            matches.add(rel_path(path))

    return sorted(matches)


def runtime_metadata_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.meta.json")


def is_runtime_metadata_managed_artifact(path: Path) -> bool:
    if not path.is_file() or path.name.endswith(".meta.json"):
        return False
    # Coverage shard databases under reports/python are transient combine inputs,
    # not durable evidence artifacts that should receive sidecars or indexing.
    return not (
        path.name.startswith(".coverage.")
        and path.parent.name == "python"
        and path.parent.parent.name == "reports"
    )


def read_runtime_metadata(path: Path) -> dict[str, Any] | None:
    metadata_path = runtime_metadata_path(path)
    if not metadata_path.is_file():
        return None
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def write_runtime_metadata(
    path: Path,
    *,
    source_entrypoint: str,
    verification_scope: str,
    source_run_id: str = "",
    source_commit: str | None = None,
    freshness_window_hours: int | None = None,
    created_at: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    metadata_path = runtime_metadata_path(path)
    created_at_value = created_at or datetime.now(UTC).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    payload: dict[str, Any] = {
        "version": 1,
        "artifact_path": rel_path(path),
        "created_at": created_at_value,
        "source_entrypoint": source_entrypoint,
        "source_run_id": source_run_id,
        "source_commit": source_commit or current_git_commit(),
        "verification_scope": verification_scope,
        "freshness_window_hours": freshness_window_hours,
    }
    if extra:
        payload.update(extra)
    payload = redact_sensitive_value(payload)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return metadata_path


def maybe_write_runtime_metadata(
    path: Path,
    *,
    source_entrypoint: str,
    verification_scope: str,
    source_run_id: str = "",
    source_commit: str | None = None,
    freshness_window_hours: int | None = None,
    created_at: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Path | None:
    resolved = path.resolve()
    runtime_root = repo_root() / ".runtime-cache"
    if not _is_within(resolved, runtime_root):
        return None
    return write_runtime_metadata(
        resolved,
        source_entrypoint=source_entrypoint,
        verification_scope=verification_scope,
        source_run_id=source_run_id,
        source_commit=source_commit,
        freshness_window_hours=freshness_window_hours,
        created_at=created_at,
        extra=extra,
    )


def write_text_artifact(
    path: Path,
    content: str,
    *,
    source_entrypoint: str,
    verification_scope: str,
    source_run_id: str = "",
    source_commit: str | None = None,
    freshness_window_hours: int | None = None,
    created_at: str | None = None,
    extra: dict[str, Any] | None = None,
    encoding: str = "utf-8",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact_sensitive_text(content), encoding=encoding)
    maybe_write_runtime_metadata(
        path,
        source_entrypoint=source_entrypoint,
        verification_scope=verification_scope,
        source_run_id=source_run_id,
        source_commit=source_commit,
        freshness_window_hours=freshness_window_hours,
        created_at=created_at,
        extra=extra,
    )
    return path


def write_json_artifact(
    path: Path,
    payload: dict[str, Any],
    *,
    source_entrypoint: str,
    verification_scope: str,
    source_run_id: str = "",
    source_commit: str | None = None,
    freshness_window_hours: int | None = None,
    created_at: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    payload = redact_sensitive_value(payload)
    return write_text_artifact(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        source_entrypoint=source_entrypoint,
        verification_scope=verification_scope,
        source_run_id=source_run_id,
        source_commit=source_commit,
        freshness_window_hours=freshness_window_hours,
        created_at=created_at,
        extra=extra,
    )


def ensure_runtime_metadata(
    path: Path,
    *,
    source_entrypoint: str,
    verification_scope: str,
    source_run_id: str = "",
    source_commit: str | None = None,
    freshness_window_hours: int | None = None,
    created_at: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = read_runtime_metadata(path)
    if payload is not None:
        return payload
    write_runtime_metadata(
        path,
        source_entrypoint=source_entrypoint,
        verification_scope=verification_scope,
        source_run_id=source_run_id,
        source_commit=source_commit,
        freshness_window_hours=freshness_window_hours,
        created_at=created_at,
        extra=extra,
    )
    loaded = read_runtime_metadata(path)
    if loaded is None:
        raise RuntimeError(f"failed to create runtime metadata for {path}")
    return loaded


def parse_iso8601(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(UTC)


def artifact_age_hours(path: Path, metadata: dict[str, Any] | None = None) -> float:
    file_created_at = datetime.fromtimestamp(path.stat().st_mtime, UTC)
    if metadata and isinstance(metadata.get("created_at"), str):
        metadata_created_at = parse_iso8601(str(metadata["created_at"]))
        created_at = min(file_created_at, metadata_created_at)
    else:
        created_at = file_created_at
    return max(0.0, (datetime.now(UTC) - created_at).total_seconds() / 3600.0)


def redact_sensitive_text(value: str) -> str:
    sanitized = value
    for pattern, replacement in _SENSITIVE_TEXT_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def redact_sensitive_value(value: Any, *, key_name: str | None = None) -> Any:
    if isinstance(value, dict):
        sanitized: dict[Any, Any] = {}
        for child_key, child_value in value.items():
            child_key_str = str(child_key)
            if _SENSITIVE_FIELD_NAME_PATTERN.fullmatch(child_key_str):
                sanitized[child_key] = "***REDACTED***"
                continue
            sanitized[child_key] = redact_sensitive_value(child_value, key_name=child_key_str)
        return sanitized
    if isinstance(value, (list, tuple, set)):
        return [redact_sensitive_value(item, key_name=key_name) for item in value]
    if isinstance(value, str):
        sanitized = redact_sensitive_text(value)
        if key_name and _SENSITIVE_FIELD_NAME_PATTERN.fullmatch(key_name):
            return "***REDACTED***"
        return sanitized
    return value
