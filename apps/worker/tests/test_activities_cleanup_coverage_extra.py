from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from worker.temporal import activities_cleanup


def _set_mtime(path: Path, dt: datetime) -> None:
    ts = dt.timestamp()
    os.utime(path, (ts, ts))


def test_is_cleanup_candidate_and_iter_files_matrix(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    files = {
        "frames/frame_001.jpg": True,
        "downloads/video.mp4": True,
        "downloads/thumb.png": True,
        "misc/frame_002.webp": True,
        "misc/media.mkv": True,
        "artifacts/digest.md": False,
        "misc/notes.txt": False,
    }

    for rel in files:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")

    iterated = {path.relative_to(root).as_posix() for path in activities_cleanup.iter_files(root)}
    assert iterated == set(files.keys())

    for rel, expected in files.items():
        assert activities_cleanup.is_cleanup_candidate(root / rel) is expected


def test_prune_empty_dirs_covers_oserror_branches() -> None:
    class _FakeDir:
        def __init__(
            self,
            *,
            name: str,
            raise_iterdir: bool = False,
            raise_rmdir: bool = False,
            has_child: bool = False,
        ) -> None:
            self.parts = ("workspace", name)
            self._raise_iterdir = raise_iterdir
            self._raise_rmdir = raise_rmdir
            self._has_child = has_child
            self.removed = False

        def is_dir(self) -> bool:
            return True

        def iterdir(self):
            if self._raise_iterdir:
                raise OSError("iterdir failed")
            if self._has_child:
                return iter([object()])
            return iter(())

        def rmdir(self) -> None:
            if self._raise_rmdir:
                raise OSError("rmdir failed")
            self.removed = True

    class _FakeFile:
        parts = ("workspace", "file.txt")

        def is_dir(self) -> bool:
            return False

    class _FakeRoot:
        def rglob(self, _pattern: str):
            return [
                _FakeDir(name="raise-iter", raise_iterdir=True),
                _FakeDir(name="has-child", has_child=True),
                _FakeDir(name="raise-rmdir", raise_rmdir=True),
                _FakeDir(name="remove-me"),
                _FakeFile(),
            ]

    assert activities_cleanup.prune_empty_dirs(_FakeRoot()) == 1


def test_cleanup_workspace_media_files_handles_missing_workspace(tmp_path: Path) -> None:
    missing_workspace = tmp_path / "not-exists"
    result = activities_cleanup.cleanup_workspace_media_files(workspace_dir=str(missing_workspace))
    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["reason"] == "workspace_not_found"


def test_cleanup_workspace_media_files_applies_cache_age_and_size_limits(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    downloads = workspace / "job-1" / "downloads"
    artifacts = workspace / "job-1" / "artifacts"
    cache = tmp_path / "cache"
    downloads.mkdir(parents=True)
    artifacts.mkdir(parents=True)
    cache.mkdir(parents=True)

    old_media = downloads / "media.mp4"
    recent_media = downloads / "media.webm"
    digest = artifacts / "digest.md"
    old_media.write_bytes(b"old-video")
    recent_media.write_bytes(b"new-video")
    digest.write_text("keep", encoding="utf-8")

    old_cache = cache / "old.cache"
    new_cache_1 = cache / "new-1.cache"
    new_cache_2 = cache / "new-2.cache"
    old_cache.write_bytes(b"1" * 64)
    new_cache_1.write_bytes(b"2" * (700 * 1024))
    new_cache_2.write_bytes(b"3" * (700 * 1024))

    now_utc = datetime(2026, 3, 8, 12, 0, tzinfo=UTC)
    very_old = now_utc - timedelta(days=3)
    recent = now_utc - timedelta(hours=1)
    _set_mtime(old_media, very_old)
    _set_mtime(recent_media, recent)
    _set_mtime(digest, very_old)
    _set_mtime(old_cache, very_old)
    _set_mtime(new_cache_1, recent)
    _set_mtime(new_cache_2, recent)

    result = activities_cleanup.cleanup_workspace_media_files(
        workspace_dir=str(workspace),
        cache_dir=str(cache),
        older_than_hours=24,
        cache_older_than_hours=24,
        cache_max_size_mb=1,
        now_utc=now_utc,
    )

    assert result["deleted_files"] == 1
    assert result["cache_deleted_files_by_age"] == 1
    assert result["cache_deleted_files_by_size"] == 1
    assert old_media.exists() is False
    assert recent_media.exists() is True
    assert digest.exists() is True


def test_cleanup_workspace_media_files_tolerates_workspace_and_cache_oserror(
    monkeypatch,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    cache = tmp_path / "cache"
    cache.mkdir(parents=True)

    now_utc = datetime(2026, 3, 8, 12, 0, tzinfo=UTC)
    very_old = now_utc - timedelta(days=2)

    class _FakeWorkspaceFile:
        def __init__(
            self, *, name: str, fail_stat: bool = False, fail_unlink: bool = False
        ) -> None:
            self.name = name
            self.suffix = ".mp4"
            self.parts = ("workspace", "downloads", name)
            self._fail_stat = fail_stat
            self._fail_unlink = fail_unlink

        def is_file(self) -> bool:
            return True

        def stat(self):
            if self._fail_stat:
                raise OSError("stat failed")
            return SimpleNamespace(st_mtime=very_old.timestamp())

        def unlink(self) -> None:
            if self._fail_unlink:
                raise OSError("unlink failed")

    bad_stat = _FakeWorkspaceFile(name="bad-stat.mp4", fail_stat=True)
    bad_unlink = _FakeWorkspaceFile(name="bad-unlink.mp4", fail_unlink=True)
    workspace_files = [bad_stat, bad_unlink]

    class _FakeCacheFile:
        def __init__(
            self,
            *,
            name: str,
            modified_at: datetime,
            size: int,
            fail_stat: bool = False,
            fail_unlink: bool = False,
        ) -> None:
            self.name = name
            self._modified_at = modified_at
            self._size = size
            self._fail_stat = fail_stat
            self._fail_unlink = fail_unlink

        def stat(self):
            if self._fail_stat:
                raise OSError("stat failed")
            return SimpleNamespace(st_mtime=self._modified_at.timestamp(), st_size=self._size)

        def unlink(self) -> None:
            if self._fail_unlink:
                raise OSError("unlink failed")

        def __str__(self) -> str:
            return self.name

    cache_files = [
        _FakeCacheFile(name="cache-stat-error", modified_at=very_old, size=128, fail_stat=True),
        _FakeCacheFile(
            name="cache-old-unlink-error",
            modified_at=very_old,
            size=128,
            fail_unlink=True,
        ),
        _FakeCacheFile(
            name="cache-size-unlink-error",
            modified_at=now_utc - timedelta(hours=1),
            size=2 * 1024 * 1024,
            fail_unlink=True,
        ),
    ]

    original_rglob = Path.rglob

    def _fake_rglob(self: Path, pattern: str):
        if self == workspace and pattern == "*":
            return workspace_files
        return original_rglob(self, pattern)

    monkeypatch.setattr(Path, "rglob", _fake_rglob, raising=False)
    monkeypatch.setattr(activities_cleanup, "iter_files", lambda _root: cache_files)
    monkeypatch.setattr(activities_cleanup, "prune_empty_dirs", lambda _root: 0)

    result = activities_cleanup.cleanup_workspace_media_files(
        workspace_dir=str(workspace),
        cache_dir=str(cache),
        older_than_hours=24,
        cache_older_than_hours=24,
        cache_max_size_mb=1,
        now_utc=now_utc,
    )

    assert result["ok"] is True
    assert result["deleted_files"] == 0
    assert result["cache_deleted_files_by_age"] == 0
    assert result["cache_deleted_files_by_size"] == 0
