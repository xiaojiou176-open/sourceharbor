from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_dev_api_uses_uvicorn_cli_under_uv_run() -> None:
    script = (_repo_root() / "scripts" / "runtime" / "dev_api.sh").read_text(encoding="utf-8")

    assert 'exec uv run uvicorn "${uvicorn_args[@]}"' in script
    assert 'exec uv run python -m uvicorn "${uvicorn_args[@]}"' not in script
