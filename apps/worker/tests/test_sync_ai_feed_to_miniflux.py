from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3] / "scripts" / "runtime" / "sync_ai_feed_to_miniflux.py"
    )
    spec = importlib.util.spec_from_file_location("sync_ai_feed_to_miniflux", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_import_entries_treats_duplicate_entry_as_idempotent(monkeypatch) -> None:
    module = _load_module()
    calls: list[dict[str, object]] = []

    def fake_http_json(method: str, url: str, headers: dict[str, str], payload=None):
        calls.append({"method": method, "url": url, "payload": payload})
        if payload and payload.get("external_id") == "sourceharbor:job-1":
            raise RuntimeError(
                "HTTP 500 POST http://127.0.0.1:8080/v1/feeds/1/entries/import: "
                '{"error_message":"store: unable to create entry \\"https://example.com/1\\" '
                "(feed #1): pq: duplicate key value violates unique constraint "
                '\\"entries_feed_id_hash_key\\" (23505)"}'
            )
        return {"ok": True}

    monkeypatch.setattr(module, "http_json", fake_http_json)

    imported = module.import_entries(
        "http://127.0.0.1:8080",
        {"X-Auth-Token": "token"},
        1,
        [
            {
                "job_id": "job-1",
                "title": "First",
                "summary_md": "hello",
                "video_url": "https://example.com/1",
                "published_at": "2026-03-09T00:00:00Z",
            },
            {
                "job_id": "job-2",
                "title": "Second",
                "summary_md": "world",
                "video_url": "https://example.com/2",
                "published_at": "2026-03-09T00:01:00Z",
            },
        ],
    )

    assert imported == 1
    assert len(calls) == 2


def test_sync_ai_feed_to_miniflux_inserts_repo_root_into_sys_path() -> None:
    module_path = (
        Path(__file__).resolve().parents[3] / "scripts" / "runtime" / "sync_ai_feed_to_miniflux.py"
    )
    script = module_path.read_text(encoding="utf-8")

    assert "ROOT = Path(__file__).resolve().parents[2]" in script
    assert "sys.path.insert(0, str(ROOT))" in script


def test_is_duplicate_entry_error_matches_known_miniflux_signatures() -> None:
    module = _load_module()

    assert module.is_duplicate_entry_error(
        RuntimeError('duplicate key value violates unique constraint "entries_feed_id_hash_key"')
    )
    assert module.is_duplicate_entry_error(RuntimeError("Entry already exists"))
    assert not module.is_duplicate_entry_error(RuntimeError("HTTP 500 unrelated"))
