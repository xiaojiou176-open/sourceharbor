from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_governance_language_gate_covers_contract_and_eval_deep_water_surfaces() -> None:
    script = (_repo_root() / "scripts" / "governance" / "check_governance_language.py").read_text(
        encoding="utf-8"
    )

    strict_section = script.split("STRICT_ENGLISH_PATHS =", 1)[1].split(
        "PRODUCT_OUTPUT_LOCALE_ALLOWLIST_PATHS =", 1
    )[0]

    assert '"contracts/AGENTS.md"' in strict_section
    assert '"contracts/CLAUDE.md"' in strict_section
    assert '"contracts/README.md"' in strict_section
    assert '"evals/README.md"' in strict_section
    assert '"evals/rubric.md"' in strict_section
