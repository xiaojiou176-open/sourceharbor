#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

STATUS_BY_EXIT_CODE = {
    1: "killed",
    3: "killed",
    -24: "timeout",
    0: "survived",
    5: "no_tests",
    2: "check_was_interrupted_by_user",
    None: "not_checked",
    33: "no_tests",
    34: "skipped",
    35: "suspicious",
    36: "timeout",
    37: "caught_by_type_check",
    24: "timeout",
    152: "timeout",
    255: "timeout",
    -11: "segfault",
    -9: "segfault",
}

STATUS_KEYS = (
    "killed",
    "survived",
    "no_tests",
    "skipped",
    "suspicious",
    "timeout",
    "check_was_interrupted_by_user",
    "segfault",
    "not_checked",
    "caught_by_type_check",
)


def summarize_mutants(mutants_dir: Path, output_path: Path, run_exit: int | None = None) -> dict[str, int]:
    meta_paths = sorted(mutants_dir.glob("**/*.meta"))
    if not meta_paths:
        raise SystemExit(
            f"[quality-gate] mutation gate failed: no mutmut meta files found under {mutants_dir.as_posix()}."
        )

    stats = {key: 0 for key in STATUS_KEYS}
    total = 0
    for meta_path in meta_paths:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        exit_code_by_key = meta.get("exit_code_by_key", {})
        for exit_code in exit_code_by_key.values():
            status = STATUS_BY_EXIT_CODE.get(exit_code, "suspicious")
            stats[status] += 1
            total += 1

    payload = {**stats, "total": total}
    if run_exit is not None:
        payload["mutmut_run_exit"] = run_exit

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"[quality-gate] wrote mutation stats to {output_path.as_posix()}")
    return payload


def validate_stats(
    stats: dict[str, int],
    *,
    min_score: float,
    min_effective_ratio: float,
    max_no_tests_ratio: float,
) -> None:
    killed = int(stats.get("killed", 0))
    survived = int(stats.get("survived", 0))
    total = int(stats.get("total", killed + survived))
    no_tests = int(stats.get("no_tests", stats.get("skipped", 0)))
    skipped = int(stats.get("skipped", 0))
    suspicious = int(stats.get("suspicious", 0))
    timeout = int(stats.get("timeout", 0))
    interrupted = int(stats.get("check_was_interrupted_by_user", 0))
    segfault = int(stats.get("segfault", 0))
    not_checked = int(stats.get("not_checked", 0))
    caught_by_type_check = int(stats.get("caught_by_type_check", 0))
    effective = killed + survived
    accounted_total = (
        effective
        + no_tests
        + skipped
        + suspicious
        + timeout
        + interrupted
        + segfault
        + not_checked
        + caught_by_type_check
    )
    unclassified = max(total - accounted_total, 0)
    run_exit = stats.get("mutmut_run_exit")

    if effective <= 0:
        exact_leaf = []
        if not_checked:
            exact_leaf.append(f"not_checked={not_checked}")
        if caught_by_type_check:
            exact_leaf.append(f"caught_by_type_check={caught_by_type_check}")
        if interrupted:
            exact_leaf.append(f"interrupted={interrupted}")
        if timeout:
            exact_leaf.append(f"timeout={timeout}")
        if suspicious:
            exact_leaf.append(f"suspicious={suspicious}")
        if skipped:
            exact_leaf.append(f"skipped={skipped}")
        if no_tests:
            exact_leaf.append(f"no_tests={no_tests}")
        if segfault:
            exact_leaf.append(f"segfault={segfault}")
        if unclassified:
            exact_leaf.append(f"unclassified={unclassified}")
        if run_exit not in (None, 0):
            exact_leaf.append(f"mutmut_run_exit={run_exit}")

        if exact_leaf:
            raise SystemExit(
                "[quality-gate] mutation gate failed: "
                f"killed+survived=0 (total={total}); remaining leaf = {', '.join(exact_leaf)}."
            )

        raise SystemExit(
            f"[quality-gate] mutation gate failed: killed+survived=0 (total={total}), no effective mutants."
        )

    score = killed / effective
    effective_ratio = effective / total if total > 0 else 0.0
    no_tests_ratio = no_tests / total if total > 0 else 1.0

    print(
        f"[quality-gate] mutation stats: killed={killed}, survived={survived}, "
        f"effective={effective}, total={total}, no_tests={no_tests}, "
        f"not_checked={not_checked}, caught_by_type_check={caught_by_type_check}, "
        f"score={score:.4f}, threshold={min_score:.4f}, "
        f"effective_ratio={effective_ratio:.4f}, min_effective_ratio={min_effective_ratio:.4f}, "
        f"no_tests_ratio={no_tests_ratio:.4f}, max_no_tests_ratio={max_no_tests_ratio:.4f}"
    )

    if score < min_score:
        raise SystemExit(
            f"[quality-gate] mutation gate failed: score {score:.4f} < threshold {min_score:.4f}."
        )
    if effective_ratio < min_effective_ratio:
        raise SystemExit(
            "[quality-gate] mutation gate failed: "
            f"effective_ratio {effective_ratio:.4f} < min_effective_ratio {min_effective_ratio:.4f}."
        )
    if no_tests_ratio > max_no_tests_ratio:
        raise SystemExit(
            "[quality-gate] mutation gate failed: "
            f"no_tests_ratio {no_tests_ratio:.4f} > max_no_tests_ratio {max_no_tests_ratio:.4f}."
        )


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "--summarize-mutants":
        if len(sys.argv) not in (4, 5):
            raise SystemExit(
                "usage: check_mutation_stats.py --summarize-mutants <mutants_dir> <output_path> [mutmut_run_exit]"
            )
        run_exit = int(sys.argv[4]) if len(sys.argv) == 5 else None
        summarize_mutants(Path(sys.argv[2]), Path(sys.argv[3]), run_exit)
        return 0

    if len(sys.argv) != 5:
        raise SystemExit(
            "usage: check_mutation_stats.py <stats_path> <min_score> <min_effective_ratio> <max_no_tests_ratio>"
        )

    stats_path = Path(sys.argv[1])
    min_score = float(sys.argv[2])
    min_effective_ratio = float(sys.argv[3])
    max_no_tests_ratio = float(sys.argv[4])

    if not stats_path.exists():
        raise SystemExit(
            f"[quality-gate] mutation gate failed: stats file missing at {stats_path.as_posix()}."
        )

    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    validate_stats(
        stats,
        min_score=min_score,
        min_effective_ratio=min_effective_ratio,
        max_no_tests_ratio=max_no_tests_ratio,
    )
    print("[quality-gate] mutation gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
