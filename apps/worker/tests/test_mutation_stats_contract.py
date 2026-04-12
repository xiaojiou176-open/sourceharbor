from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_module():
    module_path = _repo_root() / "scripts" / "governance" / "check_mutation_stats.py"
    spec = importlib.util.spec_from_file_location("check_mutation_stats_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summarize_mutants_preserves_not_checked_and_run_exit(tmp_path: Path) -> None:
    module = _load_module()
    mutants_dir = tmp_path / "mutants"
    meta_path = mutants_dir / "apps" / "api" / "demo.py.meta"
    meta_path.parent.mkdir(parents=True)
    meta_path.write_text(
        json.dumps(
            {
                "exit_code_by_key": {
                    "demo__mutmut_1": None,
                    "demo__mutmut_2": 1,
                    "demo__mutmut_3": 0,
                    "demo__mutmut_4": 37,
                },
                "durations_by_key": {},
                "type_check_error_by_key": {},
                "estimated_durations_by_key": {},
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "mutmut-cicd-stats.json"

    payload = module.summarize_mutants(mutants_dir, output_path, 7)

    assert payload["total"] == 4
    assert payload["not_checked"] == 1
    assert payload["killed"] == 1
    assert payload["survived"] == 1
    assert payload["caught_by_type_check"] == 1
    assert payload["mutmut_run_exit"] == 7
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload


def test_validate_stats_reports_exact_leaf_for_incomplete_mutmut_run() -> None:
    module = _load_module()
    stats = {
        "killed": 0,
        "survived": 0,
        "total": 7443,
        "no_tests": 0,
        "skipped": 0,
        "suspicious": 0,
        "timeout": 0,
        "check_was_interrupted_by_user": 0,
        "segfault": 0,
        "not_checked": 7443,
        "caught_by_type_check": 0,
        "mutmut_run_exit": 130,
    }

    with pytest.raises(SystemExit, match=r"remaining leaf = not_checked=7443, mutmut_run_exit=130"):
        module.validate_stats(
            stats,
            min_score=0.64,
            min_effective_ratio=0.27,
            max_no_tests_ratio=0.72,
        )
