from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

PRESERVED_ARTIFACT_FILES = {"digest.md", "meta.json", "comments.json", "outline.json"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".flv", ".avi", ".m4v", ".m4a", ".mp3"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def is_cleanup_candidate(path: Path) -> bool:
    name = path.name.lower()
    if name in PRESERVED_ARTIFACT_FILES:
        return False
    suffix = path.suffix.lower()
    if "frames" in path.parts and suffix in IMAGE_EXTENSIONS:
        return True
    if "downloads" in path.parts and suffix in VIDEO_EXTENSIONS.union(IMAGE_EXTENSIONS):
        return True
    if name.startswith("frame_") and suffix in IMAGE_EXTENSIONS:
        return True
    return name.startswith("media.") and suffix in VIDEO_EXTENSIONS


def iter_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*") if path.is_file()]


def prune_empty_dirs(root: Path) -> int:
    deleted_dirs = 0
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if not path.is_dir():
            continue
        try:
            next(path.iterdir())
            continue
        except StopIteration:
            pass
        except OSError:
            continue
        try:
            path.rmdir()
        except OSError:
            continue
        deleted_dirs += 1
    return deleted_dirs


def cleanup_workspace_media_files(
    *,
    workspace_dir: str,
    older_than_hours: int = 24,
    cache_dir: str | None = None,
    cache_older_than_hours: int | None = None,
    cache_max_size_mb: int | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_dir).expanduser()
    resolved_cache_dir = (
        Path(cache_dir).expanduser()
        if isinstance(cache_dir, str) and cache_dir.strip()
        else workspace.parent / "cache"
    )
    effective_cache_older_than_hours = max(
        1, cache_older_than_hours if cache_older_than_hours is not None else older_than_hours
    )
    effective_cache_max_size_mb = max(
        1, cache_max_size_mb if cache_max_size_mb is not None else 1024
    )
    cache_max_size_bytes = effective_cache_max_size_mb * 1024 * 1024

    if not workspace.exists():
        return {
            "ok": True,
            "workspace_dir": str(workspace),
            "cache_dir": str(resolved_cache_dir),
            "deleted_files": 0,
            "deleted_dirs": 0,
            "deleted_paths_sample": [],
            "skipped": True,
            "reason": "workspace_not_found",
        }

    reference = now_utc or datetime.now(UTC)
    cutoff = reference - timedelta(hours=max(1, older_than_hours))
    deleted_files = 0
    deleted_dirs = 0
    deleted_paths_sample: list[str] = []
    cache_deleted_by_age = 0
    cache_deleted_by_size = 0
    cache_deleted_paths_sample: list[str] = []

    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        if not is_cleanup_candidate(path):
            continue
        try:
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        except OSError:
            continue
        if modified_at >= cutoff:
            continue
        try:
            path.unlink()
        except OSError:
            continue
        deleted_files += 1
        if len(deleted_paths_sample) < 20:
            deleted_paths_sample.append(str(path))

    if resolved_cache_dir.exists():
        cache_cutoff = reference - timedelta(hours=effective_cache_older_than_hours)
        cache_file_stats: list[tuple[Path, datetime, int]] = []
        for path in iter_files(resolved_cache_dir):
            try:
                stat = path.stat()
            except OSError:
                continue
            modified_at = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
            size_bytes = int(stat.st_size)
            if modified_at < cache_cutoff:
                try:
                    path.unlink()
                except OSError:
                    continue
                cache_deleted_by_age += 1
                if len(cache_deleted_paths_sample) < 20:
                    cache_deleted_paths_sample.append(str(path))
                continue
            cache_file_stats.append((path, modified_at, size_bytes))

        remaining_cache_size = sum(size for _, _, size in cache_file_stats)
        if remaining_cache_size > cache_max_size_bytes:
            for path, _modified_at, size in sorted(cache_file_stats, key=lambda item: item[1]):
                if remaining_cache_size <= cache_max_size_bytes:
                    break
                try:
                    path.unlink()
                except OSError:
                    continue
                cache_deleted_by_size += 1
                remaining_cache_size = max(0, remaining_cache_size - size)
                if len(cache_deleted_paths_sample) < 20:
                    cache_deleted_paths_sample.append(str(path))
        deleted_dirs += prune_empty_dirs(resolved_cache_dir)

    deleted_dirs += prune_empty_dirs(workspace)

    return {
        "ok": True,
        "workspace_dir": str(workspace),
        "cache_dir": str(resolved_cache_dir),
        "deleted_files": deleted_files,
        "deleted_dirs": deleted_dirs,
        "deleted_paths_sample": deleted_paths_sample,
        "older_than_hours": max(1, older_than_hours),
        "cache_older_than_hours": effective_cache_older_than_hours,
        "cache_max_size_mb": effective_cache_max_size_mb,
        "cache_deleted_files_by_age": cache_deleted_by_age,
        "cache_deleted_files_by_size": cache_deleted_by_size,
        "cache_deleted_paths_sample": cache_deleted_paths_sample,
        "cutoff_utc": cutoff.replace(microsecond=0).isoformat(),
    }
