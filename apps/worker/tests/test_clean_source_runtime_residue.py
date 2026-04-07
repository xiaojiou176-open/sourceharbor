from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    original = sys.dont_write_bytecode
    script_path = (
        Path(__file__).resolve().parents[3]
        / "scripts"
        / "runtime"
        / "clean_source_runtime_residue.py"
    )
    spec = importlib.util.spec_from_file_location("clean_source_runtime_residue", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = original


def test_remove_path_ignores_file_not_found_race_for_directories(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_module()
    module.ROOT = tmp_path

    residue_dir = tmp_path / "pkg" / "__pycache__"
    residue_dir.mkdir(parents=True)

    def _raise_file_not_found(target: Path, *args, **kwargs) -> None:
        raise FileNotFoundError(target)

    monkeypatch.setattr(module.shutil, "rmtree", _raise_file_not_found)
    module._remove_path("pkg/__pycache__")
