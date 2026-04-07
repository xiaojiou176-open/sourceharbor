from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_prepare_web_runtime_reclaims_stale_lock_without_pid_marker() -> None:
    source = (_repo_root() / "scripts" / "ci" / "prepare_web_runtime.sh").read_text(
        encoding="utf-8"
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_root = Path(tmp_dir)
        script_path = repo_root / "scripts" / "ci" / "prepare_web_runtime.sh"
        web_dir = repo_root / "apps" / "web"
        lock_dir = repo_root / ".runtime-cache" / "run" / "web-runtime" / ".prepare-lock"

        script_path.parent.mkdir(parents=True, exist_ok=True)
        web_dir.mkdir(parents=True, exist_ok=True)
        script_path.write_text(source, encoding="utf-8")
        script_path.chmod(0o755)

        (web_dir / "package.json").write_text(
            '{"name":"test-web","private":true}\n', encoding="utf-8"
        )
        (web_dir / "package-lock.json").write_text(
            '{"name":"test-web","lockfileVersion":3}\n', encoding="utf-8"
        )
        (web_dir / "eslint.config.mjs").write_text("export default [];\n", encoding="utf-8")
        (web_dir / "tsconfig.json").write_text("{}\n", encoding="utf-8")
        (web_dir / "app.txt").write_text("content\n", encoding="utf-8")

        lock_dir.mkdir(parents=True, exist_ok=True)
        stale_mtime = time.time() - 5
        os.utime(lock_dir, (stale_mtime, stale_mtime))

        result = subprocess.run(
            ["bash", str(script_path), "--shell-exports", "--skip-install", "1"],
            cwd=repo_root,
            env={**os.environ, "PREPARE_WEB_RUNTIME_STALE_LOCK_SECONDS": "1"},
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert "export WEB_RUNTIME_WEB_DIR=" in result.stdout
        assert not lock_dir.exists()

        copied_web_dir = (
            repo_root / ".runtime-cache" / "tmp" / "web-runtime" / "workspace" / "apps" / "web"
        )
        assert (copied_web_dir / "eslint.config.mjs").is_file()
        assert (copied_web_dir / "tsconfig.json").is_file()
