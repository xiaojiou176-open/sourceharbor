#!/usr/bin/env python3
"""Fail fast on placebo assertions in test files."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED_DIRS = {
    ".git",
    ".next",
    "参考Repo",
    ".runtime-cache",
    "node_modules",
    "build",
    "dist",
    "vendor",
    "__pycache__",
}
TEST_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}


@dataclass(frozen=True)
class PatternRule:
    name: str
    regex: re.Pattern[str]
    message: str


RULES = [
    PatternRule(
        name="js-same-literal-assertion",
        regex=re.compile(
            r"expect\s*\(\s*(?P<lit>true|false|null|undefined|NaN|-?\d+(?:\.\d+)?|\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)\s*\)"
            r"\s*\.\s*(?:toBe|toEqual|toStrictEqual)\s*\(\s*(?P=lit)\s*\)",
            re.IGNORECASE,
        ),
        message="Asserting a literal against the exact same literal is forbidden.",
    ),
    PatternRule(
        name="js-self-identifier-assertion",
        regex=re.compile(
            r"expect\s*\(\s*(?P<ident>[A-Za-z_$][A-Za-z0-9_$.]*)\s*\)"
            r"\s*\.\s*(?:toBe|toEqual|toStrictEqual)\s*\(\s*(?P=ident)\s*\)",
            re.IGNORECASE,
        ),
        message="Asserting an identifier against itself is forbidden.",
    ),
    PatternRule(
        name="js-low-value-toBeDefined",
        regex=re.compile(r"expect\s*\(\s*.+?\s*\)\s*\.\s*toBeDefined\s*\(\s*\)"),
        message=(
            "`toBeDefined()` is forbidden by default. "
            "Use an explicit allow marker for exceptional cases."
        ),
    ),
    PatternRule(
        name="python-assert-true",
        regex=re.compile(r"^\s*assert\s+True\s*(?:#.*)?$", re.MULTILINE),
        message="`assert True` is forbidden in tests.",
    ),
    PatternRule(
        name="python-unittest-assert-true",
        regex=re.compile(r"self\.assertTrue\s*\(\s*True\s*\)"),
        message="`self.assertTrue(True)` is forbidden in tests.",
    ),
]


def is_test_file(path: Path) -> bool:
    if path.suffix not in TEST_EXTENSIONS:
        return False
    parts = set(path.parts)
    if "__tests__" in parts:
        return True
    name = path.name.lower()
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in name
        or ".spec." in name
    )


def iter_test_files(start_path: Path) -> list[Path]:
    files: list[Path] = []
    for path in start_path.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if is_test_file(path):
            files.append(path)
    return sorted(files)


def line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def is_allowed_tobe_defined(text: str, start_index: int) -> bool:
    marker = "allow-low-value-assertion: toBeDefined"
    line_idx = line_number(text, start_index)
    lines = text.splitlines()
    current = lines[line_idx - 1] if 0 <= line_idx - 1 < len(lines) else ""
    previous = lines[line_idx - 2] if 0 <= line_idx - 2 < len(lines) else ""
    return marker in current or marker in previous


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Block placebo assertions such as expect(true).toBe(true)."
    )
    parser.add_argument(
        "--path",
        default=".",
        help="Path to scan (relative to repo root). Default: .",
    )
    args = parser.parse_args()

    scan_root = (ROOT / args.path).resolve()
    if not scan_root.exists():
        print(f"scan path does not exist: {scan_root}", file=sys.stderr)
        return 2

    files = iter_test_files(scan_root)
    violations: list[str] = []
    for file_path in files:
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = file_path.relative_to(ROOT)
        for rule in RULES:
            for match in rule.regex.finditer(text):
                ln = line_number(text, match.start())
                if rule.name == "js-low-value-toBeDefined" and is_allowed_tobe_defined(
                    text, match.start()
                ):
                    continue
                snippet = match.group(0).strip().replace("\n", " ")
                violations.append(f"{rel}:{ln} [{rule.name}] {rule.message} :: {snippet}")

    if violations:
        print("Placebo assertion guard failed. Found forbidden assertions:")
        for item in violations:
            print(f"- {item}")
        print(
            f"Evidence: scanned_files={len(files)}, rules={len(RULES)}, violations={len(violations)}"
        )
        return 1

    print(
        "Placebo assertion guard passed: "
        f"scanned_files={len(files)}, rules={len(RULES)}, violations=0."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
