#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# shellcheck source=./scripts/lib/standard_env.sh
source "$ROOT_DIR/scripts/lib/standard_env.sh"

mkdir -p .runtime-cache .runtime-cache/reports/python .runtime-cache/logs/tests
find .runtime-cache/reports/python -maxdepth 1 -type f -name '.coverage*' -delete 2>/dev/null || true
export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"
python3 scripts/runtime/clean_source_runtime_residue.py --apply
ensure_external_uv_project_environment "$ROOT_DIR"
uv sync --frozen --extra dev --extra e2e
PYTEST_XDIST_WORKERS="${PYTHON_TESTS_XDIST_WORKERS:-2}"
PYTEST_XDIST_ARGS=()
if [[ "$PYTEST_XDIST_WORKERS" =~ ^[0-9]+$ ]] && (( PYTEST_XDIST_WORKERS > 0 )); then
  PYTEST_XDIST_ARGS=(-n "$PYTEST_XDIST_WORKERS")
fi
set -o pipefail
(
  PYTHONPATH="$PWD:$PWD/apps/worker" \
  PYTHONDONTWRITEBYTECODE=1 \
  DATABASE_URL='sqlite+pysqlite:///:memory:' \
  COVERAGE_FILE=.runtime-cache/reports/python/.coverage \
  uv run pytest apps/worker/tests apps/api/tests apps/mcp/tests -q -rA "${PYTEST_XDIST_ARGS[@]}" \
    --cov=apps/worker/worker \
    --cov=apps/api/app \
    --cov=apps/mcp/server.py \
    --cov=apps/mcp/tools \
    --cov-report=term-missing:skip-covered \
    --cov-report=xml:.runtime-cache/reports/python/python-coverage.xml \
    --cov-fail-under=95 \
    --junitxml=.runtime-cache/reports/python/python-tests-junit.xml \
    2>&1 | tee .runtime-cache/logs/tests/python-tests.log
) &
test_pid=$!

while kill -0 "${test_pid}" >/dev/null 2>&1; do
  echo "[heartbeat] python tests still running ($(date -u +'%Y-%m-%dT%H:%M:%SZ'))"
  sleep 25
done

wait "${test_pid}"
python3 scripts/runtime/clean_source_runtime_residue.py --apply

python3 - <<'PY'
from __future__ import annotations

import sqlite3
from pathlib import Path

coverage_db = Path(".runtime-cache/reports/python/.coverage")
repo_root = Path.cwd()


def merge_file_rows(conn: sqlite3.Connection, source_id: int, target_id: int) -> None:
    if source_id == target_id:
        return

    target_bits = conn.execute(
        "select count(*) from line_bits where file_id = ?",
        (target_id,),
    ).fetchone()[0]
    if target_bits == 0:
        conn.execute(
            "update line_bits set file_id = ? where file_id = ?",
            (target_id, source_id),
        )
    else:
        conn.execute("delete from line_bits where file_id = ?", (source_id,))
    conn.execute("delete from arc where file_id = ?", (source_id,))
    conn.execute("delete from tracer where file_id = ?", (source_id,))
    conn.execute("delete from file where id = ?", (source_id,))


if coverage_db.is_file():
    conn = sqlite3.connect(coverage_db)
    try:
        rows = conn.execute("select id, path from file").fetchall()
        updated = 0
        for file_id, raw_path in rows:
            if not isinstance(raw_path, str):
                continue
            path = Path(raw_path)
            if path.exists():
                continue
            replacement = None
            for marker in ("/apps/", "/integrations/", "/packages/", "/scripts/"):
                marker_index = raw_path.find(marker)
                if marker_index == -1:
                    continue
                candidate = repo_root / raw_path[marker_index + 1 :]
                if candidate.exists():
                    replacement = str(candidate)
                    break
            if replacement and replacement != raw_path:
                existing = conn.execute(
                    "select id from file where path = ?",
                    (replacement,),
                ).fetchone()
                if existing:
                    merge_file_rows(conn, int(file_id), int(existing[0]))
                else:
                    try:
                        conn.execute(
                            "update file set path = ? where id = ?",
                            (replacement, file_id),
                        )
                    except sqlite3.IntegrityError:
                        collided = conn.execute(
                            "select id from file where path = ?",
                            (replacement,),
                        ).fetchone()
                        if not collided:
                            raise
                        merge_file_rows(conn, int(file_id), int(collided[0]))
                updated += 1
        if updated:
            conn.commit()
    finally:
        conn.close()
PY

find .runtime-cache/reports/python -maxdepth 1 -type f -name '.coverage*.meta.json' -delete 2>/dev/null || true

if find .runtime-cache/reports/python -maxdepth 1 -type f -name '.coverage.*' ! -name '*.meta.json' | grep -q .; then
  PYTHONDONTWRITEBYTECODE=1 COVERAGE_FILE=.runtime-cache/reports/python/.coverage uv run coverage combine --keep .runtime-cache/reports/python >/dev/null
fi
rm -f .runtime-cache/reports/python/.coverage.meta.json

set -o pipefail
PYTHONDONTWRITEBYTECODE=1 uv run coverage report \
  --data-file=.runtime-cache/reports/python/.coverage \
  --include="apps/worker/worker/pipeline/orchestrator.py,*/apps/worker/worker/pipeline/orchestrator.py,apps/worker/worker/pipeline/policies.py,*/apps/worker/worker/pipeline/policies.py,apps/worker/worker/pipeline/runner.py,*/apps/worker/worker/pipeline/runner.py,apps/worker/worker/pipeline/types.py,*/apps/worker/worker/pipeline/types.py" \
  --show-missing \
  --fail-under=95 \
  2>&1 | tee .runtime-cache/logs/tests/python-coverage-worker-core.log

set -o pipefail
PYTHONDONTWRITEBYTECODE=1 uv run coverage report \
  --data-file=.runtime-cache/reports/python/.coverage \
  --include="apps/api/app/routers/ingest.py,*/apps/api/app/routers/ingest.py,apps/api/app/routers/jobs.py,*/apps/api/app/routers/jobs.py,apps/api/app/routers/subscriptions.py,*/apps/api/app/routers/subscriptions.py,apps/api/app/routers/videos.py,*/apps/api/app/routers/videos.py,apps/api/app/services/jobs.py,*/apps/api/app/services/jobs.py,apps/api/app/services/subscriptions.py,*/apps/api/app/services/subscriptions.py,apps/api/app/services/videos.py,*/apps/api/app/services/videos.py" \
  --show-missing \
  --fail-under=95 \
  2>&1 | tee .runtime-cache/logs/tests/python-coverage-api-core.log

python3 - <<'PY'
import xml.etree.ElementTree as ET
from pathlib import Path

report = Path(".runtime-cache/reports/python/python-tests-junit.xml")
if not report.is_file():
    raise SystemExit("python skip guard failed: junit report missing")

root = ET.parse(report).getroot()
suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
tests = sum(int(suite.attrib.get("tests", "0")) for suite in suites)
skipped = sum(int(suite.attrib.get("skipped", "0")) for suite in suites)

if tests == 0:
    raise SystemExit("python skip guard failed: collected 0 tests")
if skipped > 0:
    raise SystemExit(f"python skip guard failed: skipped={skipped} (no silent skip allowed)")
print(f"python skip guard passed: tests={tests}, skipped={skipped}")
PY

# Coverage report reads can leave transient shard files behind; remove them
# before writing final runtime metadata so governance only sees durable outputs.
find .runtime-cache/reports/python -maxdepth 1 -type f -name '.coverage.*.meta.json' -delete 2>/dev/null || true
find .runtime-cache/reports/python -maxdepth 1 -type f -name '.coverage.*' -delete 2>/dev/null || true

python3 - <<'PY'
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "scripts" / "governance"))
from common import write_runtime_metadata

reports_dir = ROOT / ".runtime-cache" / "reports" / "python"
gate_run_id = os.getenv("sourceharbor_gate_run_id", "") or os.getenv("sourceharbor_log_run_id", "") or "python-tests-with-coverage"
repo_commit = os.getenv("sourceharbor_log_repo_commit", "")

for artifact in sorted(reports_dir.glob(".coverage*")):
    if artifact.name.endswith(".meta.json") or not artifact.is_file():
        continue
    write_runtime_metadata(
        artifact,
        source_entrypoint="scripts/ci/python_tests.sh",
        verification_scope="python-tests-coverage-shard",
        source_run_id=gate_run_id,
        source_commit=repo_commit,
        freshness_window_hours=24,
        extra={"report_kind": "python-coverage-shard"},
    )

for artifact_name, report_kind in (
    ("coverage.json", "python-coverage-summary"),
    ("python-coverage.xml", "python-coverage-xml"),
    ("python-tests-junit.xml", "python-tests-junit"),
):
    artifact = reports_dir / artifact_name
    if not artifact.is_file():
        continue
    write_runtime_metadata(
        artifact,
        source_entrypoint="scripts/ci/python_tests.sh",
        verification_scope=report_kind,
        source_run_id=gate_run_id,
        source_commit=repo_commit,
        freshness_window_hours=24,
        extra={"report_kind": report_kind},
    )
PY

python3 scripts/runtime/clean_source_runtime_residue.py --apply
