from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_quality_gate_uses_pre_push_base_resolver_without_head_tilde_fallback() -> None:
    content = (_repo_root() / "scripts" / "governance" / "quality_gate.sh").read_text(
        encoding="utf-8"
    )

    assert "resolve_pre_push_diff_base()" in content
    assert "fallback:HEAD~1..HEAD" not in content
    assert "git rev-list --max-parents=0 HEAD" in content
    assert 'if [[ -n "$head_sha" && "$root_commit" == "$head_sha" ]]; then' in content
    assert 'DIFF_BASE_SOURCE="root-commit-empty-tree"' in content
    assert "git hash-object -t tree /dev/null" in content


def test_quality_gate_contract_diff_and_design_token_share_base_resolver() -> None:
    content = (_repo_root() / "scripts" / "governance" / "quality_gate.sh").read_text(
        encoding="utf-8"
    )

    assert "DIFF_BASE_SHA=" in content
    assert "if ! resolve_pre_push_diff_base; then" in content
    assert "if resolve_pre_push_diff_base; then" in content


def test_doc_drift_push_base_resolver_avoids_head_tilde_fallback() -> None:
    content = (_repo_root() / "scripts" / "governance" / "ci_or_local_gate_doc_drift.sh").read_text(
        encoding="utf-8"
    )

    assert 'git -C "$ROOT_DIR" symbolic-ref --quiet --short refs/remotes/origin/HEAD' in content
    assert 'git -C "$ROOT_DIR" rev-list --max-parents=0 HEAD' in content
    assert 'if [[ -n "$head_sha" && "$root_commit" == "$head_sha" ]]; then' in content
    assert 'echo "$empty_tree_sha"' in content
    assert 'git -C "$ROOT_DIR" rev-parse HEAD~1' not in content
