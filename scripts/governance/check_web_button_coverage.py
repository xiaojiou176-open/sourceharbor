#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

BUTTON_PATTERN = re.compile(r"<button\b[^>]*>(?P<label>.*?)</button>", re.IGNORECASE | re.DOTALL)
BUTTON_COMPONENT_PATTERN = re.compile(
    r"<Button\b(?P<attrs>[^>]*)>(?P<label>.*?)</Button>", re.IGNORECASE | re.DOTALL
)
LINK_PATTERN = re.compile(r"<Link\b[^>]*>(?P<label>.*?)</Link>", re.IGNORECASE | re.DOTALL)
ANCHOR_PATTERN = re.compile(r"<a\b[^>]*>(?P<label>.*?)</a>", re.IGNORECASE | re.DOTALL)
ARIA_LABEL_PATTERN = re.compile(
    r"""aria-label\s*=\s*(?:"(?P<double>[^"]+)"|'(?P<single>[^']+)')""",
    re.IGNORECASE,
)
PYTEST_ROLE_CLICK_PATTERN = re.compile(
    r"""get_by_role\(\s*["'](?P<role>button|link)["']\s*,\s*name\s*=\s*["'](?P<label>[^"']+)["']\s*\)\.click\(""",
    re.DOTALL,
)
PYTEST_ROLE_ASSIGN_PATTERN = re.compile(
    r"""(?P<var>[a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*[^=\n]*?get_by_role\(\s*["'](?P<role>button|link)["']\s*,\s*name\s*=\s*["'](?P<label>[^"']+)["']\s*\)""",
    re.DOTALL,
)
RTL_ROLE_PATTERN = re.compile(
    r"""getByRole\(\s*["'](?P<role>button|link)["']\s*,\s*\{\s*name\s*:\s*["'](?P<label>[^"']+)["']\s*\}\s*\)""",
    re.DOTALL,
)


def normalize_label(raw: str) -> str:
    cleaned = re.sub(r"{[^{}]*}", " ", raw)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def should_track_label(raw: str, normalized: str) -> bool:
    if not normalized:
        return False
    if "{" in raw or "}" in raw:
        return False
    if normalized in {"（在新标签页打开）", "(在新标签页打开)"}:
        return False
    return re.fullmatch(r"[^\w\u4e00-\u9fff]+", normalized) is None


def _extract_aria_label(attrs: str) -> str | None:
    match = ARIA_LABEL_PATTERN.search(attrs)
    if not match:
        return None
    return match.group("double") or match.group("single")


def _iter_source_files(source_roots: list[Path], source_files: list[Path]) -> list[Path]:
    files: list[Path] = []
    if source_files:
        for file_path in source_files:
            if not file_path.is_file():
                continue
            if file_path.suffix != ".tsx":
                continue
            parts = set(file_path.parts)
            if {"__tests__", "node_modules", ".next"} & parts:
                continue
            files.append(file_path)
        return files
    for root in source_roots:
        for file_path in sorted(root.glob("**/*.tsx")):
            parts = set(file_path.parts)
            if {"__tests__", "node_modules", ".next"} & parts:
                continue
            files.append(file_path)
    return files


def collect_interactive_labels(source_roots: list[Path], source_files: list[Path]) -> dict[str, set[str]]:
    labels: dict[str, set[str]] = {}
    for file_path in _iter_source_files(source_roots, source_files):
        content = file_path.read_text(encoding="utf-8")
        for pattern in (BUTTON_PATTERN, LINK_PATTERN, ANCHOR_PATTERN):
            for match in pattern.finditer(content):
                label = normalize_label(match.group("label"))
                if not should_track_label(match.group("label"), label):
                    continue
                labels.setdefault(label, set()).add(str(file_path))
        for match in BUTTON_COMPONENT_PATTERN.finditer(content):
            raw_label = match.group("label")
            aria_label = _extract_aria_label(match.group("attrs"))
            candidates = [raw_label]
            if aria_label:
                candidates.append(aria_label)
            for candidate in candidates:
                label = normalize_label(candidate)
                if not should_track_label(candidate, label):
                    continue
                labels.setdefault(label, set()).add(str(file_path))
    return labels


def collect_pytest_e2e_labels(e2e_root: Path) -> set[str]:
    labels: set[str] = set()
    for file_path in sorted(e2e_root.glob("*.py")):
        content = file_path.read_text(encoding="utf-8")
        for match in PYTEST_ROLE_CLICK_PATTERN.finditer(content):
            label = normalize_label(match.group("label"))
            if label:
                labels.add(label)
        assigned_labels: dict[str, set[str]] = {}
        for match in PYTEST_ROLE_ASSIGN_PATTERN.finditer(content):
            variable = match.group("var")
            label = normalize_label(match.group("label"))
            if not label:
                continue
            assigned_labels.setdefault(variable, set()).add(label)
        for variable, variable_labels in assigned_labels.items():
            if re.search(rf"\b{re.escape(variable)}\.click\(", content):
                labels.update(variable_labels)
    return labels


def collect_rtl_unit_labels(unit_test_root: Path) -> set[str]:
    labels: set[str] = set()
    for file_path in sorted(unit_test_root.rglob("*")):
        if not file_path.is_file():
            continue
        filename = file_path.name
        if not filename.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")):
            continue
        content = file_path.read_text(encoding="utf-8")
        for match in RTL_ROLE_PATTERN.finditer(content):
            label = normalize_label(match.group("label"))
            if label:
                labels.add(label)
    return labels


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check interactive control label coverage between web UI sources and "
            "test assertions. Reports combined, E2E-only, and unit-only coverage separately."
        )
    )
    parser.add_argument(
        "--source-root",
        action="append",
        type=Path,
        default=[],
        help=(
            "Root directory containing tsx source files. "
            "Repeatable. Defaults to apps/web/app and apps/web/components."
        ),
    )
    parser.add_argument(
        "--source-file",
        action="append",
        type=Path,
        default=[],
        help="Specific tsx source files to audit instead of scanning whole roots.",
    )
    parser.add_argument(
        "--app-root",
        type=Path,
        default=None,
        help="Deprecated alias for a single source root.",
    )
    parser.add_argument(
        "--e2e-root",
        type=Path,
        default=Path("apps/web/tests/e2e"),
        help="Root directory containing playwright pytest files. Default: apps/web/tests/e2e",
    )
    parser.add_argument(
        "--unit-test-root",
        type=Path,
        default=Path("apps/web/__tests__"),
        help="Root directory containing web unit tests. Default: apps/web/__tests__",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=1.0,
        help="Minimum combined (E2E ∪ unit) coverage ratio [0,1]. Default: 1.0",
    )
    parser.add_argument(
        "--e2e-threshold",
        type=float,
        default=0.6,
        help="Minimum E2E-only coverage ratio [0,1]. Default: 0.6",
    )
    parser.add_argument(
        "--unit-threshold",
        type=float,
        default=0.93,
        help="Minimum unit-test-only coverage ratio [0,1]. Default: 0.93",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for value, name in (
        (args.threshold, "threshold"),
        (args.e2e_threshold, "e2e-threshold"),
        (args.unit_threshold, "unit-threshold"),
    ):
        if not 0 <= value <= 1:
            raise SystemExit(f"{name} must be in [0,1]")
    source_roots = list(args.source_root)
    source_files = [path for path in args.source_file if path is not None]
    if args.app_root is not None:
        source_roots = [args.app_root]
    if not source_roots and not source_files:
        source_roots = [Path("apps/web/app"), Path("apps/web/components")]
    if source_files:
        for source_file in source_files:
            if not source_file.is_file():
                raise SystemExit(f"source file not found: {source_file}")
    for source_root in source_roots:
        if not source_root.is_dir():
            raise SystemExit(f"source root not found: {source_root}")
    if not args.e2e_root.is_dir():
        raise SystemExit(f"e2e root not found: {args.e2e_root}")
    if not args.unit_test_root.is_dir():
        raise SystemExit(f"unit test root not found: {args.unit_test_root}")

    app_labels = collect_interactive_labels(source_roots, source_files)
    e2e_labels = collect_pytest_e2e_labels(args.e2e_root)
    unit_labels = collect_rtl_unit_labels(args.unit_test_root)
    total = len(app_labels)
    if total == 0:
        raise SystemExit(
            "web interactive coverage gate failed: no interactive labels were discovered under "
            f"{', '.join(str(path) for path in source_roots)}"
        )
    combined_labels = e2e_labels | unit_labels
    combined_covered = sorted(label for label in app_labels if label in combined_labels)
    e2e_covered = sorted(label for label in app_labels if label in e2e_labels)
    unit_covered = sorted(label for label in app_labels if label in unit_labels)
    combined_uncovered = sorted(label for label in app_labels if label not in combined_labels)
    e2e_uncovered = sorted(label for label in app_labels if label not in e2e_labels)
    unit_uncovered = sorted(label for label in app_labels if label not in unit_labels)
    combined_ratio = len(combined_covered) / total
    e2e_ratio = len(e2e_covered) / total
    unit_ratio = len(unit_covered) / total

    print(
        "web interactive combined coverage: "
        f"covered={len(combined_covered)} total={total} ratio={combined_ratio:.2%} threshold={args.threshold:.2%} "
        f"(e2e_labels={len(e2e_labels)} unit_labels={len(unit_labels)})"
    )
    print(
        "web interactive e2e coverage: "
        f"covered={len(e2e_covered)} total={total} ratio={e2e_ratio:.2%} threshold={args.e2e_threshold:.2%}"
    )
    print(
        "web interactive unit coverage: "
        f"covered={len(unit_covered)} total={total} ratio={unit_ratio:.2%} threshold={args.unit_threshold:.2%}"
    )
    if combined_uncovered:
        print("combined uncovered interactive labels:")
        for label in combined_uncovered:
            files = ", ".join(sorted(app_labels[label]))
            print(f"  - {label} ({files})")
    if args.e2e_threshold > 0 and e2e_uncovered:
        print("e2e uncovered interactive labels:")
        for label in e2e_uncovered:
            files = ", ".join(sorted(app_labels[label]))
            print(f"  - {label} ({files})")
    if args.unit_threshold > 0 and unit_uncovered:
        print("unit uncovered interactive labels:")
        for label in unit_uncovered:
            files = ", ".join(sorted(app_labels[label]))
            print(f"  - {label} ({files})")

    failures: list[str] = []
    if combined_ratio < args.threshold:
        failures.append(f"combined_ratio={combined_ratio:.4f} < threshold={args.threshold:.4f}")
    if e2e_ratio < args.e2e_threshold:
        failures.append(f"e2e_ratio={e2e_ratio:.4f} < threshold={args.e2e_threshold:.4f}")
    if unit_ratio < args.unit_threshold:
        failures.append(f"unit_ratio={unit_ratio:.4f} < threshold={args.unit_threshold:.4f}")

    if failures:
        print("web interactive coverage gate failed:")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("web interactive coverage gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
