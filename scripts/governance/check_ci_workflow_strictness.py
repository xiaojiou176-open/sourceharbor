#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

WORKFLOW_DIR = Path(".github/workflows")
WORKFLOW_PATH = WORKFLOW_DIR / "ci.yml"
BUILD_PUBLIC_API_IMAGE_WORKFLOW_PATH = WORKFLOW_DIR / "build-public-api-image.yml"
BUILD_STANDARD_IMAGE_WORKFLOW_PATH = WORKFLOW_DIR / "build-ci-standard-image.yml"
RELEASE_EVIDENCE_WORKFLOW_PATH = WORKFLOW_DIR / "release-evidence-attest.yml"
PUBLISH_PYPI_WORKFLOW_PATH = WORKFLOW_DIR / "publish-pypi.yml"
PUBLISH_MCP_REGISTRY_WORKFLOW_PATH = WORKFLOW_DIR / "publish-mcp-registry.yml"
RUNNER_HEALTH_WORKFLOW_PATH = WORKFLOW_DIR / "runner-health.yml"
REMOTE_INTEGRITY_WORKFLOW_PATH = WORKFLOW_DIR / "remote-integrity-audit.yml"
TRUSTED_BOUNDARY_REUSABLE_WORKFLOW_PATH = WORKFLOW_DIR / "_trusted-pr-boundary.yml"
CONTRACT_PATH = Path("infra/config/strict_ci_contract.json")
RUNNER_BASELINE_CONTRACT_PATH = Path("infra/config/self_hosted_runner_baseline.json")
CHECKOUT_ACTION = "actions/checkout@"
CACHE_ACTION = "actions/cache@"
PRE_CHECKOUT_NORMALIZATION_STEP = "Normalize self-hosted workspace (pre-checkout)"
SELF_HOSTED_RUNS_ON_MARKERS = (
    "runs-on: [self-hosted",
    'runs-on: \'["self-hosted"',
    "runs-on: ${{ fromJSON(inputs.runs-on) }}",
)
SAFE_CACHE_PATH_MARKERS = (
    "${{ runner.temp }}",
    "${{ env.CI_CACHE_ROOT }}",
    "${{ env.PRE_COMMIT_HOME }}",
    "${{ env.UV_CACHE_DIR }}",
    "${{ env.PLAYWRIGHT_BROWSERS_PATH }}",
    "${{ needs.ci-contract.outputs.cache_root }}",
    "${{ needs.ci-contract.outputs.uv_cache_dir }}",
    "${{ needs.ci-contract.outputs.playwright_browsers_path }}",
    "${{ needs.ci-contract.outputs.pre_commit_home }}",
    "/tmp/ci-cache",
)
TOOL_CACHE_ENV_VARS = (
    "PRE_COMMIT_HOME",
    "UV_CACHE_DIR",
    "PLAYWRIGHT_BROWSERS_PATH",
    "PIP_CACHE_DIR",
    "XDG_CACHE_HOME",
    "npm_config_cache",
)
LOCAL_REAL_CHROME_PROFILE_ENV_VARS = (
    "SOURCE_HARBOR_CHROME_USER_DATA_DIR",
    "SOURCE_HARBOR_CHROME_PROFILE_NAME",
    "SOURCE_HARBOR_CHROME_PROFILE_DIR",
    "SOURCE_HARBOR_CHROME_CDP_PORT",
)
MIN_MUTATION_SCORE = 0.64
MIN_MUTATION_EFFECTIVE_RATIO = 0.27
MAX_MUTATION_NO_TESTS_RATIO = 0.72
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def _job_blocks(text: str) -> list[tuple[str, str]]:
    jobs_section = re.search(r"^jobs:\s*$", text, flags=re.MULTILINE)
    if not jobs_section:
        return []

    section_start = jobs_section.end()
    section_end = len(text)
    next_top_level = re.search(r"^[A-Za-z0-9_-]+:\s*$", text[section_start:], flags=re.MULTILINE)
    if next_top_level:
        section_end = section_start + next_top_level.start()

    jobs: list[tuple[str, int]] = []
    jobs_text = text[section_start:section_end]
    for match in re.finditer(r"^  ([A-Za-z0-9_-]+):\n", jobs_text, flags=re.MULTILINE):
        jobs.append((match.group(1), section_start + match.start()))
    blocks: list[tuple[str, str]] = []
    for i, (name, start) in enumerate(jobs):
        end = jobs[i + 1][1] if i + 1 < len(jobs) else section_end
        blocks.append((name, text[start:end]))
    return blocks


def _contains_required_ci_gate(block: str) -> bool:
    return "check_required_ci_secrets.py" in block and "--required GEMINI_API_KEY" in block


def _has_job_level_uses(block: str) -> bool:
    return re.search(r"^\s{4}uses:\s+\S+", block, flags=re.MULTILINE) is not None


def _job_level_uses_target(block: str) -> str | None:
    match = re.search(r"^\s{4}uses:\s+(\S+?)(?:\s+#.*)?\s*$", block, flags=re.MULTILINE)
    return match.group(1) if match else None


def _local_reusable_workflow_has_timeouts(uses_target: str) -> bool:
    reusable_path = Path(uses_target[2:])
    if not reusable_path.is_file():
        return False
    reusable_text = reusable_path.read_text(encoding="utf-8")
    reusable_blocks = dict(_job_blocks(reusable_text))
    for block in reusable_blocks.values():
        has_direct_runs_on = re.search(r"^\s{4}runs-on:", block, flags=re.MULTILINE) is not None
        has_uses = _has_job_level_uses(block)
        if has_direct_runs_on and not has_uses and "timeout-minutes:" not in block:
            return False
    return True


def _has_needs_dep(block: str, dep: str) -> bool:
    lines = block.splitlines()
    for i, line in enumerate(lines):
        match = re.match(r"^\s{4}needs:\s*(.*)$", line)
        if not match:
            continue

        tail = match.group(1).strip()
        if tail.startswith("&"):
            tail = ""

        if tail:
            # needs: [a, b] (single or multi-line flow style)
            if tail.startswith("["):
                flow = tail
                j = i + 1
                while "]" not in flow and j < len(lines):
                    flow += lines[j].strip()
                    j += 1
                inner = flow[flow.find("[") + 1 : flow.rfind("]")]
                items = [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]
                return dep in items

            value = tail.split("#", 1)[0].strip().strip("'\"")
            return dep == value

        # needs:
        #   - a
        #   - b
        j = i + 1
        items: list[str] = []
        while j < len(lines):
            item_line = lines[j]
            if item_line.strip() == "":
                j += 1
                continue
            if not re.match(r"^\s{6,}", item_line):
                break
            item_match = re.match(r"^\s{6,}-\s*(.+?)\s*$", item_line)
            if item_match:
                item = item_match.group(1).split("#", 1)[0].strip().strip("'\"")
                if item:
                    items.append(item)
            j += 1
        return dep in items

    return False


def _workflow_has_pull_request_trigger(text: str) -> bool:
    return bool(re.search(r"^on:\n(?:.+\n)*?\s{2}pull_request:\s*$", text, flags=re.MULTILINE))


def _block_has_self_hosted_runs_on(block: str) -> bool:
    return any(marker in block for marker in SELF_HOSTED_RUNS_ON_MARKERS)


def _trusted_boundary_reusable_is_valid() -> bool:
    if not TRUSTED_BOUNDARY_REUSABLE_WORKFLOW_PATH.is_file():
        return False
    text = TRUSTED_BOUNDARY_REUSABLE_WORKFLOW_PATH.read_text(encoding="utf-8")
    blocks = dict(_job_blocks(text))
    run_block = blocks.get("trusted-pr-boundary", "")
    return (
        "permissions: {}" in text
        and "runs-on: ubuntu-latest" in run_block
        and "trusted internal PR boundary violated" in run_block
        and "timeout-minutes:" in run_block
    )


def _trusted_boundary_job_is_valid(workflow_name: str, block: str, failures: list[str]) -> None:
    if not block:
        failures.append(f"{workflow_name}: trusted-pr-boundary: missing job")
        return
    uses_target = _job_level_uses_target(block)
    if uses_target != "./.github/workflows/_trusted-pr-boundary.yml":
        failures.append(
            f"{workflow_name}: trusted-pr-boundary: must use `./.github/workflows/_trusted-pr-boundary.yml`"
        )
        return
    if not _trusted_boundary_reusable_is_valid():
        failures.append(
            f"{workflow_name}: trusted-pr-boundary: reusable workflow `_trusted-pr-boundary.yml` must keep empty permissions, hosted runner, and explicit failure messaging"
        )


def _check_shared_self_hosted_pr_boundary_rules(
    workflow_path: Path, text: str, blocks: dict[str, str], failures: list[str]
) -> None:
    if workflow_path == WORKFLOW_PATH or not _workflow_has_pull_request_trigger(text):
        return

    self_hosted_jobs = [
        name
        for name, block in blocks.items()
        if name != "trusted-pr-boundary" and _block_has_self_hosted_runs_on(block)
    ]
    if not self_hosted_jobs:
        return

    _trusted_boundary_job_is_valid(
        workflow_path.name, blocks.get("trusted-pr-boundary", ""), failures
    )
    for job_name in self_hosted_jobs:
        block = blocks[job_name]
        if not _has_needs_dep(block, "trusted-pr-boundary"):
            failures.append(
                f"{workflow_path.name}: {job_name}: missing needs dependency `trusted-pr-boundary`"
            )
        if_expr = _extract_job_level_if_expression(block)
        if not if_expr or not _if_expr_checks_success_for_job(if_expr, "trusted-pr-boundary"):
            failures.append(
                f"{workflow_path.name}: {job_name}: must gate self-hosted execution on trusted-pr-boundary success"
            )


def _extract_flag_value(block: str, flag: str) -> float | None:
    pattern = rf"{re.escape(flag)}\s+([0-9]+(?:\.[0-9]+)?)"
    match = re.search(pattern, block)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_job_level_if_expression(block: str) -> str | None:
    lines = block.splitlines()
    for i, line in enumerate(lines):
        match = re.match(r"^\s{4}if:\s*(.+)$", line)
        if not match:
            continue

        value = match.group(1).strip()
        if value.startswith("${{"):
            expr = value
            j = i + 1
            while "}}" not in expr and j < len(lines):
                cont = lines[j]
                if not re.match(r"^\s{6,}", cont):
                    break
                expr += " " + cont.strip()
                j += 1
            if "}}" in expr:
                return expr[expr.find("${{") + 3 : expr.rfind("}}")].strip()
        return value
    return None


def _if_expr_checks_success_for_job(if_expr: str, job_name: str) -> bool:
    patterns = (
        rf"needs\.{re.escape(job_name)}\.result\s*==\s*['\"]success['\"]",
        rf"needs\[['\"]{re.escape(job_name)}['\"]\]\.result\s*==\s*['\"]success['\"]",
    )
    return any(re.search(pattern, if_expr) is not None for pattern in patterns)


def _if_expr_enforces_trusted_internal_pr_boundary(if_expr: str) -> bool:
    patterns = (
        r"github\.event_name\s*!=\s*['\"]pull_request['\"]",
        r"github\.event\.pull_request\.head\.repo\.full_name\s*==\s*github\.repository",
    )
    return all(re.search(pattern, if_expr) is not None for pattern in patterns)


def _aggregate_maps_required_ci_result(block: str) -> bool:
    patterns = (
        r"results\[required_ci_secrets\]\s*=\s*['\"]\$\{\{\s*needs\.required-ci-secrets\.result\s*\}\}['\"]",
        r"results\[required_ci_secrets\]\s*=\s*['\"]\$\{\{\s*needs\[['\"]required-ci-secrets['\"]\]\.result\s*\}\}['\"]",
    )
    return any(re.search(pattern, block) is not None for pattern in patterns)


def _aggregate_enforces_required_ci_success(block: str) -> bool:
    normalized = " ".join(block.split())
    direct_checks = (
        'if [[ "${results[required_ci_secrets]}" != "success" ]]',
        "check_required_job required_ci_secrets 1",
        "check_required_job required_ci_secrets '1'",
        'check_required_job required_ci_secrets "1"',
    )
    if any(check in normalized for check in direct_checks):
        return True

    has_required_in_for_loop = "for job in" in normalized and "required_ci_secrets" in normalized
    has_success_only_guard = 'if [[ "$result" != "success" ]]; then failed=1' in normalized
    return has_required_in_for_loop and has_success_only_guard


def _leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _collect_step_block(lines: list[str], start_index: int) -> list[str]:
    block = [lines[start_index]]
    step_indent = _leading_spaces(lines[start_index])
    index = start_index + 1
    while index < len(lines):
        line = lines[index]
        stripped = line.lstrip()
        if stripped.startswith("- ") and _leading_spaces(line) <= step_indent:
            break
        block.append(line)
        index += 1
    return block


def _self_hosted_job_ranges(text: str) -> list[tuple[int, int]]:
    lines = text.splitlines()
    jobs_start_index: int | None = None
    for index, line in enumerate(lines):
        if re.match(r"^jobs:\s*$", line):
            jobs_start_index = index
            break
    if jobs_start_index is None:
        return []

    job_positions: list[int] = []
    for index in range(jobs_start_index + 1, len(lines)):
        line = lines[index]
        if re.match(r"^[A-Za-z0-9_-]+:\s*$", line):
            break
        if re.match(r"^  [A-Za-z0-9_-]+:\s*$", line):
            job_positions.append(index)

    ranges: list[tuple[int, int]] = []
    for idx, start in enumerate(job_positions):
        end = job_positions[idx + 1] if idx + 1 < len(job_positions) else len(lines)
        block = "\n".join(lines[start:end])
        if any(marker in block for marker in SELF_HOSTED_RUNS_ON_MARKERS):
            ranges.append((start + 1, end))
    return ranges


def _line_in_ranges(lineno: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= lineno <= end for start, end in ranges)


def _check_checkout_clean_rule(workflow_path: Path, text: str, failures: list[str]) -> None:
    lines = text.splitlines()
    self_hosted_ranges = _self_hosted_job_ranges(text)
    for lineno, line in enumerate(lines, start=1):
        if CHECKOUT_ACTION not in line:
            continue
        block = "\n".join(_collect_step_block(lines, lineno - 1))
        if "clean: true" not in block:
            failures.append(
                f"{workflow_path.name}:{lineno}: actions/checkout must declare with.clean: true on shared self-hosted runners"
            )

        if not _line_in_ranges(lineno, self_hosted_ranges):
            continue

        step_start = lineno - 1
        while step_start >= 0 and not re.match(r"^\s*-\s+", lines[step_start]):
            step_start -= 1

        prev_step = step_start - 1
        while prev_step >= 0 and not re.match(r"^\s*-\s+", lines[prev_step]):
            prev_step -= 1

        prev_step_block = "\n".join(_collect_step_block(lines, prev_step)) if prev_step >= 0 else ""
        if prev_step < 0 or (
            PRE_CHECKOUT_NORMALIZATION_STEP not in prev_step_block
            and "./.github/actions/normalize-self-hosted-workspace" not in prev_step_block
        ):
            failures.append(
                f"{workflow_path.name}:{lineno}: self-hosted checkout must be preceded by `{PRE_CHECKOUT_NORMALIZATION_STEP}`"
            )


def _is_forbidden_cache_value(value: str) -> bool:
    normalized = value.strip()
    if not normalized:
        return True
    if "~/.cache" in normalized or "${{ github.workspace }}" in normalized:
        return True
    if normalized.startswith((".", "cache/", ".venv")):
        return True
    return "/.runtime-cache" in normalized or "/.cache/" in normalized


def _is_safe_cache_value(value: str) -> bool:
    normalized = value.strip()
    return any(marker in normalized for marker in SAFE_CACHE_PATH_MARKERS)


def _extract_cache_paths_from_step(block_lines: list[str]) -> list[str]:
    paths: list[str] = []
    in_with = False
    in_path = False
    path_indent = 0
    for line in block_lines[1:]:
        stripped = line.strip()
        indent = _leading_spaces(line)
        if not stripped:
            continue
        if stripped == "with:":
            in_with = True
            in_path = False
            continue
        if not in_with:
            continue
        if re.match(r"^[A-Za-z0-9_-]+:\s*", stripped) and not stripped.startswith("path:"):
            in_path = False
        if stripped.startswith("path:"):
            in_path = True
            path_indent = indent
            value = stripped.split("path:", 1)[1].strip()
            if value and value != "|":
                paths.append(value)
            continue
        if in_path:
            if indent <= path_indent:
                in_path = False
                continue
            paths.append(stripped)
    return [item for item in paths if item and item != "|"]


def _check_cache_path_rules(workflow_path: Path, text: str, failures: list[str]) -> None:
    lines = text.splitlines()
    uses_cache_action = False
    for lineno, line in enumerate(lines, start=1):
        env_match = re.match(
            rf"^\s+({'|'.join(re.escape(name) for name in TOOL_CACHE_ENV_VARS)}):\s*(.+?)\s*$",
            line,
        )
        if env_match:
            env_name, env_value = env_match.groups()
            if _is_forbidden_cache_value(env_value) or not _is_safe_cache_value(env_value):
                failures.append(
                    f"{workflow_path.name}:{lineno}: {env_name} must resolve under runner.temp/CI_CACHE_ROOT, not repo paths or ~/.cache"
                )

        if CACHE_ACTION not in line:
            continue
        uses_cache_action = True
        block_lines = _collect_step_block(lines, lineno - 1)
        for cache_path in _extract_cache_paths_from_step(block_lines):
            if _is_forbidden_cache_value(cache_path) or not _is_safe_cache_value(cache_path):
                failures.append(
                    f"{workflow_path.name}:{lineno}: actions/cache path `{cache_path}` must resolve under runner.temp/CI_CACHE_ROOT"
                )

    if uses_cache_action and "CI_CACHE_ROOT:" not in text:
        failures.append(
            f"{workflow_path.name}: workflows using actions/cache must declare CI_CACHE_ROOT under runner.temp"
        )


def _check_ci_concurrency_rules(workflow_path: Path, text: str, failures: list[str]) -> None:
    if workflow_path.name != WORKFLOW_PATH.name:
        return
    lines = text.splitlines()
    in_concurrency = False
    group_value: str | None = None
    for line in lines:
        if re.match(r"^concurrency:\s*$", line):
            in_concurrency = True
            continue
        if not in_concurrency:
            continue
        if line and not line.startswith(" "):
            break
        match = re.match(r"^\s{2}group:\s*(.+?)\s*$", line)
        if match:
            group_value = match.group(1).strip()
            break
    if group_value is None:
        failures.append(f"{workflow_path.name}: missing top-level concurrency.group")
        return
    if "github.sha" in group_value:
        failures.append(
            f"{workflow_path.name}: top-level concurrency.group must not include github.sha; use a stable workflow/event/ref key"
        )


def _workflow_has_explicit_trigger(text: str, trigger_name: str) -> bool:
    return trigger_name in _top_level_on_triggers(text)


def _workflow_has_only_workflow_dispatch(text: str) -> bool:
    triggers = _top_level_on_triggers(text)
    return bool(triggers) and set(triggers) == {"workflow_dispatch"}


def _top_level_on_triggers(text: str) -> list[str]:
    lines = text.splitlines()
    in_on = False
    triggers: list[str] = []
    for line in lines:
        if not in_on:
            if re.match(r"^on:\s*$", line):
                in_on = True
            continue
        if line and not line.startswith(" "):
            break
        match = re.match(r"^\s{2}([A-Za-z0-9_-]+):\s*$", line)
        if match:
            triggers.append(match.group(1))
    return triggers


def _push_branches(text: str) -> list[str]:
    lines = text.splitlines()
    in_push = False
    in_branches = False
    branches: list[str] = []
    for line in lines:
        if not in_push:
            if re.match(r"^\s{2}push:\s*$", line):
                in_push = True
            continue
        if line and not line.startswith(" "):
            break
        if not in_branches:
            if re.match(r"^\s{4}branches:\s*$", line):
                in_branches = True
            continue
        if re.match(r"^\s{4}[A-Za-z0-9_-]+:\s*$", line):
            break
        match = re.match(r"^\s{6}-\s*(.+?)\s*$", line)
        if match:
            branches.append(match.group(1))
    return branches


def _check_job_runs_on_hosted(
    workflow_name: str, blocks: dict[str, str], job_name: str, failures: list[str]
) -> None:
    block = blocks.get(job_name, "")
    if not block:
        failures.append(f"{workflow_name}: {job_name}: missing job")
        return
    if "runs-on: ubuntu-latest" not in block:
        failures.append(f"{workflow_name}: {job_name}: must run on ubuntu-latest")


def _uses_public_hosted_first_ci(blocks: dict[str, str]) -> bool:
    return set(blocks) == {"python-tests", "web-lint"}


def _check_public_hosted_first_ci_specific_rules(
    text: str, blocks: dict[str, str], failures: list[str]
) -> None:
    if not _workflow_has_pull_request_trigger(text):
        failures.append("ci.yml: must trigger on pull_request")
    if _push_branches(text) != ["main"]:
        failures.append("ci.yml: push trigger must be limited to main")
    if "self-hosted" in text or "shared-pool" in text:
        failures.append("ci.yml: current PR path must not reference self-hosted or shared-pool")
    for token in LOCAL_REAL_CHROME_PROFILE_ENV_VARS:
        if token in text:
            failures.append(
                f"ci.yml: hosted PR path must not reference local-only real Chrome profile env `{token}`"
            )

    python_tests = blocks.get("python-tests", "")
    if "python3 scripts/governance/check_env_contract.py --strict" not in python_tests:
        failures.append("ci.yml: python-tests: missing env contract check")
    if "python3 scripts/governance/check_host_safety_contract.py" not in python_tests:
        failures.append("ci.yml: python-tests: missing host safety contract check")
    if "python3 scripts/governance/check_test_assertions.py" not in python_tests:
        failures.append("ci.yml: python-tests: missing placebo assertion guard")
    if "bash scripts/ci/python_tests.sh" not in python_tests:
        failures.append("ci.yml: python-tests: missing canonical python test command")
    if "secrets." in python_tests:
        failures.append("ci.yml: python-tests: public PR path must not consume secrets context")

    web_lint = blocks.get("web-lint", "")
    has_deterministic_web_install = (
        "npm --prefix apps/web ci" in web_lint
        or "install-command: bash scripts/ci/prepare_web_runtime.sh" in web_lint
    )
    if not has_deterministic_web_install:
        failures.append("ci.yml: web-lint: missing deterministic npm ci step")
    has_frontend_lint = (
        "npm --prefix apps/web run lint" in web_lint
        or 'npm --prefix "$WEB_RUNTIME_WEB_DIR" run lint' in web_lint
    )
    if not has_frontend_lint:
        failures.append("ci.yml: web-lint: missing frontend lint command")
    if "secrets." in web_lint:
        failures.append("ci.yml: web-lint: public PR path must not consume secrets context")


def _check_global_rules(
    workflow_path: Path, text: str, blocks: dict[str, str], failures: list[str]
) -> None:
    # Third-party actions must be pinned to immutable commit SHAs.
    for match in re.finditer(r"^\s+uses:\s+([^\s#]+)", text, flags=re.MULTILINE):
        uses_target = match.group(1).strip()
        if uses_target.startswith(("./", "docker://")):
            continue
        if "@" not in uses_target:
            failures.append(
                f"{workflow_path.name}: unpinned action reference `{uses_target}` (missing @<commit-sha>)"
            )
            continue
        action_ref = uses_target.rsplit("@", 1)[1]
        if not re.fullmatch(r"[0-9a-f]{40}", action_ref):
            failures.append(
                f"{workflow_path.name}: action `{uses_target}` must pin a 40-char commit SHA"
            )

    # Inline pipe-to-shell patterns are forbidden in workflows.
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if re.search(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:bash|sh)\b", stripped):
            failures.append(
                f"{workflow_path.name}:{lineno}: forbidden pipe-to-shell command detected (`curl|sh` or `wget|sh`)"
            )
        if re.search(r"(?:^|\s)(?:\./)?(?:config\.sh|run\.sh|remove\.sh)(?:\s|$)", stripped):
            failures.append(
                f"{workflow_path.name}:{lineno}: forbidden runner registration command detected (config.sh/run.sh/remove.sh)"
            )

    # Skip reusable workflows (workflow_call).
    is_reusable = "on:\n  workflow_call:" in text or "on:\n    workflow_call:" in text

    # Any runnable job must declare timeout-minutes.
    # Jobs that delegate to reusable workflows (uses:) have timeout in the reusable workflow.
    for job, block in blocks.items():
        has_direct_runs_on = re.search(r"^\s{4}runs-on:", block, flags=re.MULTILINE) is not None
        has_uses = _has_job_level_uses(block)
        if has_direct_runs_on and not has_uses and "timeout-minutes:" not in block:
            failures.append(f"{workflow_path.name}: {job}: missing timeout-minutes")
            continue
        if has_uses and "timeout-minutes:" not in block:
            uses_target = _job_level_uses_target(block)
            if not uses_target:
                failures.append(f"{workflow_path.name}: {job}: missing timeout-minutes")
                continue
            if not uses_target.startswith("./"):
                failures.append(
                    f"{workflow_path.name}: {job}: reusable workflow jobs without local `uses: ./...` must set timeout-minutes explicitly"
                )
                continue
            if not _local_reusable_workflow_has_timeouts(uses_target):
                failures.append(
                    f"{workflow_path.name}: {job}: reusable workflow {uses_target} must define timeout-minutes on runnable jobs"
                )

    # continue-on-error=true is only allowed on hosted jobs that have explicit
    # fallback partners. This lets hosted billing/capacity failures degrade
    # gracefully without masking real failures in non-hosted jobs.
    for job, block in blocks.items():
        has_continue = (
            re.search(r"^\s{4}continue-on-error:\s*true\s*$", block, flags=re.MULTILINE) is not None
        )
        if not has_continue:
            continue
        if not job.endswith("-hosted"):
            failures.append(
                f"{workflow_path.name}: {job}: continue-on-error=true is only allowed on *-hosted jobs"
            )
            continue
        base = job[: -len("-hosted")]
        fallback_name = f"{base}-fallback"
        if fallback_name not in blocks:
            failures.append(
                f"{workflow_path.name}: {job}: continue-on-error=true requires companion fallback job {fallback_name}"
            )

    # Reusable workflows (workflow_call) don't need required-ci-secrets job.
    if is_reusable:
        _check_checkout_clean_rule(workflow_path, text, failures)
        return

    _check_ci_concurrency_rules(workflow_path, text, failures)
    _check_checkout_clean_rule(workflow_path, text, failures)
    _check_cache_path_rules(workflow_path, text, failures)

    if workflow_path.name != WORKFLOW_PATH.name:
        return

    if _uses_public_hosted_first_ci(blocks):
        _check_public_hosted_first_ci_specific_rules(text, blocks, failures)
        return

    # Every workflow must hard-fail when required CI secrets are missing.
    required_ci_secrets = blocks.get("required-ci-secrets", "")
    if not required_ci_secrets:
        failures.append(f"{workflow_path.name}: required-ci-secrets: missing job")
    elif not _contains_required_ci_gate(required_ci_secrets):
        failures.append(
            f"{workflow_path.name}: required-ci-secrets: must run check_required_ci_secrets.py with --required GEMINI_API_KEY"
        )

    # Hosted -> fallback -> resolver chain checks for small tasks.
    for job_name, hosted_block in blocks.items():
        if not job_name.endswith("-hosted"):
            continue

        base = job_name[: -len("-hosted")]
        fallback_name = f"{base}-fallback"
        resolver_name = base
        fallback_block = blocks.get(fallback_name, "")
        resolver_block = blocks.get(resolver_name, "")

        if (
            "runs-on: [self-hosted, sourceharbor]" not in hosted_block
            and 'runs-on: \'["self-hosted","sourceharbor"]\'' not in hosted_block
        ):
            failures.append(
                f"{workflow_path}: {job_name}: hosted jobs must run on [self-hosted, sourceharbor]"
            )

        if not fallback_block:
            failures.append(
                f"{workflow_path}: {fallback_name}: missing fallback job for {job_name}"
            )
        else:
            if (
                "runs-on: [self-hosted, sourceharbor]" not in fallback_block
                and 'runs-on: \'["self-hosted","sourceharbor"]\'' not in fallback_block
            ):
                failures.append(
                    f"{workflow_path}: {fallback_name}: fallback jobs must run on [self-hosted, sourceharbor]"
                )
            if not re.search(
                rf"^\s+if:\s+\$\{{\{{.*always\(\).*(needs\['{re.escape(job_name)}'\]\.result\s*!=\s*['\"]success['\"]|needs\.{re.escape(job_name)}\.result\s*!=\s*['\"]success['\"]).*\}}\}}\s*$",
                fallback_block,
                flags=re.MULTILINE,
            ):
                failures.append(
                    f"{workflow_path}: {fallback_name}: fallback must use always() and trigger only when {job_name} != success"
                )

        if not resolver_block:
            failures.append(
                f"{workflow_path}: {resolver_name}: missing resolver job for hosted/fallback chain"
            )
        else:
            if not _has_needs_dep(resolver_block, job_name) or not _has_needs_dep(
                resolver_block, fallback_name
            ):
                failures.append(
                    f"{workflow_path}: {resolver_name}: resolver needs must include both {job_name} and {fallback_name}"
                )
            if not re.search(r"^\s+if:\s+\$\{\{\s*always\(\)", resolver_block, flags=re.MULTILINE):
                failures.append(
                    f"{workflow_path}: {resolver_name}: resolver must use if: ${{{{ always() ... }}}}"
                )
            resolver_if_expr = _extract_job_level_if_expression(resolver_block) or ""
            hosted_ok = _if_expr_checks_success_for_job(resolver_if_expr, job_name)
            fallback_ok = _if_expr_checks_success_for_job(resolver_if_expr, fallback_name)
            if not (hosted_ok and fallback_ok):
                failures.append(
                    f"{workflow_path}: {resolver_name}: resolver must only pass when hosted or fallback is successful"
                )


def _check_ci_specific_rules(blocks: dict[str, str], failures: list[str]) -> None:
    if "runner-bootstrap" in blocks:
        failures.append(
            "ci.yml: runner-bootstrap: runner health must live in runner-health.yml, not the main CI workflow"
        )

    standard_env_jobs = (
        "preflight-heavy",
        "quality-gate-pre-push",
        "db-migration-smoke",
        "python-tests",
        "api-real-smoke",
        "pr-llm-real-smoke",
        "dependency-vuln-scan",
        "backend-lint",
        "frontend-lint",
        "web-test-build",
        "web-e2e",
        "web-e2e-perceived",
        "live-smoke",
    )
    for job_name in standard_env_jobs:
        block = blocks.get(job_name, "")
        if not block:
            failures.append(f"ci.yml: {job_name}: missing job")
            continue
        if "container:" not in block or "needs.ci-contract.outputs.standard_image_ref" not in block:
            failures.append(
                f"ci.yml: {job_name}: must run inside the strict ci standard image from ci-contract outputs"
            )
        if (
            "services:\n      postgres:" in block
            and "needs.ci-contract.outputs.service_image_pgvector_pg16" not in block
        ):
            failures.append(
                f"ci.yml: {job_name}: postgres service image must come from ci-contract outputs"
            )
    _check_ci_post_container_rules(blocks, failures)


def _check_runner_health_specific_rules(
    text: str, blocks: dict[str, str], failures: list[str]
) -> None:
    runner_bootstrap = blocks.get("runner-bootstrap", "")
    if not runner_bootstrap:
        failures.append("runner-health.yml: runner-bootstrap: missing job")
        return

    if (
        "EXPECTED_RUNNERS_SORTED=" in runner_bootstrap
        or "EXPECTED_RUNNERS_JSON=" in runner_bootstrap
        or "exactly match expected" in runner_bootstrap
    ):
        failures.append(
            "runner-health.yml: runner-bootstrap: must not hardcode exact org runner name lists; use label/pattern online thresholds"
        )
    if "MIN_ONLINE_CORE_RUNNERS" not in runner_bootstrap:
        failures.append(
            "runner-health.yml: runner-bootstrap: missing pool-core online threshold guard (MIN_ONLINE_CORE_RUNNERS)"
        )
    if "MIN_ONLINE_LABEL_RUNNERS" not in runner_bootstrap or "sourceharbor" not in runner_bootstrap:
        failures.append(
            "runner-health.yml: runner-bootstrap: missing label-route online threshold guard for sourceharbor"
        )
    if (
        "python3 scripts/governance/check_runner_baseline.py --profile runner-health"
        not in runner_bootstrap
    ):
        failures.append(
            "runner-health.yml: runner-bootstrap: must validate the runner-health baseline contract before cloud bootstrap"
        )
    if "sudo apt-get install -y gh" in runner_bootstrap:
        failures.append(
            "runner-health.yml: runner-bootstrap: must not install gh dynamically; enforce runner baseline instead"
        )
    if "concurrency:\n  group: runner-health-" not in text:
        failures.append(
            "runner-health.yml: must serialize overlapping wake-up runs with a stable top-level concurrency group"
        )
    if "not a current-head closure proof" not in text:
        failures.append(
            "runner-health.yml: must publish a platform-only summary that explicitly rejects current-head closure semantics"
        )


def _check_build_standard_image_specific_rules(text: str, failures: list[str]) -> None:
    blocks = dict(_job_blocks(text))
    if not _workflow_has_only_workflow_dispatch(text):
        failures.append(
            "build-ci-standard-image.yml: external publish lane must be workflow_dispatch only"
        )
    if not _workflow_has_explicit_trigger(text, "workflow_dispatch"):
        failures.append("build-ci-standard-image.yml: missing workflow_dispatch trigger")
    publish = blocks.get("publish", "")
    if not publish:
        failures.append("build-ci-standard-image.yml: publish: missing job")
    else:
        if "environment:\n      name: external-ghcr-publish" not in publish:
            failures.append(
                "build-ci-standard-image.yml: publish: must use protected environment `external-ghcr-publish`"
            )
        if "runs-on: ubuntu-latest" not in publish:
            failures.append("build-ci-standard-image.yml: publish: must run on ubuntu-latest")
    if re.search(r"^\s{2}contents:\s+write\s*$", text, flags=re.MULTILINE):
        failures.append(
            "build-ci-standard-image.yml: permissions.contents must stay read-only; image publish must not mutate the repository"
        )
    for token in LOCAL_REAL_CHROME_PROFILE_ENV_VARS:
        if token in text:
            failures.append(
                f"build-ci-standard-image.yml: hosted external lane must not reference local-only real Chrome profile env `{token}`"
            )
    forbidden_markers = (
        "git push",
        "git commit",
        "git add infra/config/strict_ci_contract.json",
        "contract_path.write_text(",
        "Update strict CI contract digest",
        "Commit strict CI contract digest",
    )
    for marker in forbidden_markers:
        if marker in text:
            failures.append(
                f"build-ci-standard-image.yml: forbidden repository write-back marker detected (`{marker}`)"
            )
    if "contract-candidate.json" not in text:
        failures.append(
            "build-ci-standard-image.yml: must emit a contract-candidate artifact instead of writing infra/config/strict_ci_contract.json"
        )


def _check_build_public_api_image_specific_rules(text: str, failures: list[str]) -> None:
    blocks = dict(_job_blocks(text))
    if not _workflow_has_only_workflow_dispatch(text):
        failures.append(
            "build-public-api-image.yml: external publish lane must be workflow_dispatch only"
        )
    if not _workflow_has_explicit_trigger(text, "workflow_dispatch"):
        failures.append("build-public-api-image.yml: missing workflow_dispatch trigger")
    publish = blocks.get("publish", "")
    if not publish:
        failures.append("build-public-api-image.yml: publish: missing job")
        return
    if "environment:\n      name: external-ghcr-publish" not in publish:
        failures.append(
            "build-public-api-image.yml: publish: must use protected environment `external-ghcr-publish`"
        )
    if "runs-on: ubuntu-latest" not in publish:
        failures.append("build-public-api-image.yml: publish: must run on ubuntu-latest")
    if "build_public_api_image.sh" not in text:
        failures.append(
            "build-public-api-image.yml: must build through scripts/ci/build_public_api_image.sh"
        )
    if "sourceharbor-api" not in text:
        failures.append(
            "build-public-api-image.yml: must target the dedicated sourceharbor-api image repository"
        )
    for token in LOCAL_REAL_CHROME_PROFILE_ENV_VARS:
        if token in text:
            failures.append(
                f"build-public-api-image.yml: hosted external lane must not reference local-only real Chrome profile env `{token}`"
            )


def _check_release_evidence_specific_rules(text: str, failures: list[str]) -> None:
    blocks = dict(_job_blocks(text))
    if not _workflow_has_only_workflow_dispatch(text):
        failures.append(
            "release-evidence-attest.yml: external attestation lane must be workflow_dispatch only"
        )
    if not _workflow_has_explicit_trigger(text, "workflow_dispatch"):
        failures.append("release-evidence-attest.yml: missing workflow_dispatch trigger")
    release_evidence = blocks.get("release-evidence", "")
    if not release_evidence:
        failures.append("release-evidence-attest.yml: release-evidence: missing job")
        return
    if "environment:\n      name: external-release-evidence" not in release_evidence:
        failures.append(
            "release-evidence-attest.yml: release-evidence: must use protected environment `external-release-evidence`"
        )
    if "runs-on: ubuntu-latest" not in release_evidence:
        failures.append("release-evidence-attest.yml: release-evidence: must run on ubuntu-latest")
    for token in LOCAL_REAL_CHROME_PROFILE_ENV_VARS:
        if token in text:
            failures.append(
                f"release-evidence-attest.yml: hosted external lane must not reference local-only real Chrome profile env `{token}`"
            )
    if not re.search(
        r"workflow_dispatch:\n(?:\s{4}.+\n)*\s{6}release_tag:\n(?:\s{8}.+\n)*\s{8}required:\s+true",
        text,
        flags=re.MULTILINE,
    ):
        failures.append(
            "release-evidence-attest.yml: workflow_dispatch.release_tag must stay required for manual attestation runs"
        )


def _check_publish_pypi_specific_rules(text: str, failures: list[str]) -> None:
    blocks = dict(_job_blocks(text))
    if not _workflow_has_only_workflow_dispatch(text):
        failures.append("publish-pypi.yml: external publish lane must be workflow_dispatch only")
    if not _workflow_has_explicit_trigger(text, "workflow_dispatch"):
        failures.append("publish-pypi.yml: missing workflow_dispatch trigger")
    if not re.search(
        r"workflow_dispatch:\n(?:\s{4}.+\n)*\s{6}expected_version:\n(?:\s{8}.+\n)*\s{8}required:\s+true",
        text,
        flags=re.MULTILINE,
    ):
        failures.append(
            "publish-pypi.yml: workflow_dispatch.expected_version must stay required for manual publish runs"
        )
    publish = blocks.get("publish", "")
    if not publish:
        failures.append("publish-pypi.yml: publish: missing job")
        return
    if "environment:\n      name: external-pypi-publish" not in publish:
        failures.append(
            "publish-pypi.yml: publish: must use protected environment `external-pypi-publish`"
        )
    if "runs-on: ubuntu-latest" not in publish:
        failures.append("publish-pypi.yml: publish: must run on ubuntu-latest")
    if "id-token: write" not in publish:
        failures.append(
            "publish-pypi.yml: publish: must request `id-token: write` for Trusted Publishing"
        )
    if "pypa/gh-action-pypi-publish@" not in text:
        failures.append(
            "publish-pypi.yml: must publish through `pypa/gh-action-pypi-publish@release/v1`"
        )
    if "uv build" not in text:
        failures.append("publish-pypi.yml: must build distributions through `uv build`")
    if "README.md must keep the MCP ownership marker" not in text:
        failures.append("publish-pypi.yml: must fail-close when the MCP ownership marker is missing")
    for token in LOCAL_REAL_CHROME_PROFILE_ENV_VARS:
        if token in text:
            failures.append(
                f"publish-pypi.yml: hosted external lane must not reference local-only real Chrome profile env `{token}`"
            )
    if re.search(r"^\s{2}contents:\s+write\s*$", text, flags=re.MULTILINE):
        failures.append(
            "publish-pypi.yml: permissions.contents must stay read-only; publish must not mutate the repository"
        )


def _check_publish_mcp_registry_specific_rules(text: str, failures: list[str]) -> None:
    blocks = dict(_job_blocks(text))
    if not _workflow_has_only_workflow_dispatch(text):
        failures.append(
            "publish-mcp-registry.yml: external publish lane must be workflow_dispatch only"
        )
    if not _workflow_has_explicit_trigger(text, "workflow_dispatch"):
        failures.append("publish-mcp-registry.yml: missing workflow_dispatch trigger")
    if not re.search(
        r"workflow_dispatch:\n(?:\s{4}.+\n)*\s{6}expected_version:\n(?:\s{8}.+\n)*\s{8}required:\s+true",
        text,
        flags=re.MULTILINE,
    ):
        failures.append(
            "publish-mcp-registry.yml: workflow_dispatch.expected_version must stay required for manual publish runs"
        )
    publish = blocks.get("publish", "")
    if not publish:
        failures.append("publish-mcp-registry.yml: publish: missing job")
        return
    if "environment:\n      name: external-mcp-registry-publish" not in publish:
        failures.append(
            "publish-mcp-registry.yml: publish: must use protected environment `external-mcp-registry-publish`"
        )
    if "runs-on: ubuntu-latest" not in publish:
        failures.append("publish-mcp-registry.yml: publish: must run on ubuntu-latest")
    if "id-token: write" not in publish:
        failures.append(
            "publish-mcp-registry.yml: publish: must request `id-token: write` for registry OIDC auth"
        )
    if "mcp-publisher login github-oidc" not in text:
        failures.append(
            "publish-mcp-registry.yml: must authenticate through `mcp-publisher login github-oidc`"
        )
    if "mcp-publisher publish" not in text:
        failures.append("publish-mcp-registry.yml: must call `mcp-publisher publish`")
    if "https://pypi.org/pypi/sourceharbor/json" not in text:
        failures.append(
            "publish-mcp-registry.yml: must verify the expected SourceHarbor version is already live on PyPI before registry publish"
        )
    if "starter-packs/mcp-registry/sourceharbor-server.template.json" not in text:
        failures.append(
            "publish-mcp-registry.yml: must source registry metadata from starter-packs/mcp-registry/sourceharbor-server.template.json"
        )
    for token in LOCAL_REAL_CHROME_PROFILE_ENV_VARS:
        if token in text:
            failures.append(
                f"publish-mcp-registry.yml: hosted external lane must not reference local-only real Chrome profile env `{token}`"
            )
    if re.search(r"^\s{2}contents:\s+write\s*$", text, flags=re.MULTILINE):
        failures.append(
            "publish-mcp-registry.yml: permissions.contents must stay read-only; publish must not mutate the repository"
        )


def _check_remote_integrity_specific_rules(
    text: str, blocks: dict[str, str], failures: list[str]
) -> None:
    if "workflow_call:\n    secrets:\n      REMOTE_INTEGRITY_GH_TOKEN:" not in text:
        failures.append(
            "remote-integrity-audit.yml: workflow_call must declare REMOTE_INTEGRITY_GH_TOKEN as an explicit optional secret"
        )
    if "scope: remote required-check alignment and platform truth only" not in text:
        failures.append(
            "remote-integrity-audit.yml: must publish a summary that scopes the workflow to remote alignment/platform truth only"
        )
    block = blocks.get("remote-integrity", "")
    if not block:
        failures.append("remote-integrity-audit.yml: remote-integrity: missing job")
        return
    if "runs-on: ubuntu-latest" not in block:
        failures.append("remote-integrity-audit.yml: remote-integrity: must run on hosted runner")


def _check_ci_post_container_rules(blocks: dict[str, str], failures: list[str]) -> None:
    _trusted_boundary_job_is_valid("ci.yml", blocks.get("trusted-pr-boundary", ""), failures)

    for guarded_job in (
        "required-ci-secrets",
        "ci-contract",
        "changes",
        "preflight-fast",
        "aggregate-gate",
        "ci-final-gate",
        "ci-kpi",
    ):
        block = blocks.get(guarded_job, "")
        if not block:
            failures.append(f"ci.yml: {guarded_job}: missing job")
            continue
        if guarded_job != "preflight-fast" and not _has_needs_dep(block, "trusted-pr-boundary"):
            failures.append(
                f"ci.yml: {guarded_job}: missing needs dependency `trusted-pr-boundary`"
            )
        if_expr = _extract_job_level_if_expression(block)
        if not if_expr or not _if_expr_checks_success_for_job(if_expr, "trusted-pr-boundary"):
            failures.append(
                f"ci.yml: {guarded_job}: must gate self-hosted execution on trusted-pr-boundary success"
            )
    # quality-gate-pre-push must run broadly (not main/schedule-only gated).
    qg_block = blocks.get("quality-gate-pre-push", "")
    if qg_block:
        if re.search(r"^\s{4}if:\s", qg_block, flags=re.MULTILINE):
            failures.append(
                "ci.yml: quality-gate-pre-push: should not narrow execution with job-level if"
            )
        if "./bin/strict-ci" not in qg_block or "--mode pre-push" not in qg_block:
            failures.append("ci.yml: quality-gate-pre-push: missing pre-push quality gate command")
        if not re.search(r"--ci-dedupe\s+1\b", qg_block):
            failures.append(
                "ci.yml: quality-gate-pre-push: must set --ci-dedupe 1 to avoid duplicate heavy checks already enforced by standalone CI jobs"
            )
        if not re.search(r"--skip-mutation\s+1\b", qg_block):
            failures.append(
                "ci.yml: quality-gate-pre-push: must set --skip-mutation 1 because mutation-testing runs as a dedicated standalone CI job"
            )
        if "needs.ci-contract.outputs.mutation_min_score" in qg_block:
            min_score = MIN_MUTATION_SCORE
        else:
            min_score = _extract_flag_value(qg_block, "--mutation-min-score")
        if min_score is None:
            failures.append("ci.yml: quality-gate-pre-push: missing mutation score floor")
        elif min_score < MIN_MUTATION_SCORE:
            failures.append(
                "ci.yml: quality-gate-pre-push: mutation threshold must be at least 0.64"
            )
        if "needs.ci-contract.outputs.mutation_min_effective_ratio" in qg_block:
            min_effective_ratio = MIN_MUTATION_EFFECTIVE_RATIO
        else:
            min_effective_ratio = _extract_flag_value(qg_block, "--mutation-min-effective-ratio")
        if min_effective_ratio is None:
            failures.append("ci.yml: quality-gate-pre-push: missing mutation effective ratio floor")
        elif min_effective_ratio < MIN_MUTATION_EFFECTIVE_RATIO:
            failures.append(
                "ci.yml: quality-gate-pre-push: mutation effective ratio floor must be at least 0.27"
            )
        if "needs.ci-contract.outputs.mutation_max_no_tests_ratio" in qg_block:
            max_no_tests_ratio = MAX_MUTATION_NO_TESTS_RATIO
        else:
            max_no_tests_ratio = _extract_flag_value(qg_block, "--mutation-max-no-tests-ratio")
        if max_no_tests_ratio is None:
            failures.append(
                "ci.yml: quality-gate-pre-push: missing mutation no-tests ratio ceiling"
            )
        elif max_no_tests_ratio > MAX_MUTATION_NO_TESTS_RATIO:
            failures.append(
                "ci.yml: quality-gate-pre-push: mutation no-tests ratio ceiling must be at most 0.72"
            )

    # Real smoke jobs must not bypass write auth.
    for job_name in ("api-real-smoke", "pr-llm-real-smoke"):
        block = blocks.get(job_name, "")
        if not block:
            failures.append(f"ci.yml: {job_name}: missing job")
            continue
        if "SOURCE_HARBOR_ALLOW_UNAUTH_WRITE" in block:
            failures.append(
                f"ci.yml: {job_name}: forbidden SOURCE_HARBOR_ALLOW_UNAUTH_WRITE bypass detected"
            )
        if job_name == "api-real-smoke":
            if 'SOURCE_HARBOR_API_KEY: "ci-smoke-write-token"' not in block:
                failures.append("ci.yml: api-real-smoke: missing explicit smoke write token wiring")
            if 'WEB_ACTION_SESSION_TOKEN: "ci-smoke-write-token"' not in block:
                failures.append(
                    "ci.yml: api-real-smoke: missing explicit smoke web-session token wiring"
                )

    # Aggregate gate must require critical jobs.
    aggregate = blocks.get("aggregate-gate", "")
    if not aggregate:
        failures.append("ci.yml: aggregate-gate: missing job")
    if aggregate and not _has_needs_dep(aggregate, "required-ci-secrets"):
        failures.append("ci.yml: aggregate-gate: missing needs dependency `required-ci-secrets`")
    for required_job in ("quality-gate-pre-push", "api-real-smoke", "web-e2e", "python-tests"):
        if aggregate and not _has_needs_dep(aggregate, required_job):
            failures.append(f"ci.yml: aggregate-gate: missing needs dependency `{required_job}`")
    if aggregate and not _aggregate_maps_required_ci_result(aggregate):
        failures.append(
            "ci.yml: aggregate-gate: must map required-ci-secrets job result into runtime gate logic (results[required_ci_secrets]=...)"
        )
    if aggregate and not _aggregate_enforces_required_ci_success(aggregate):
        failures.append(
            "ci.yml: aggregate-gate: must hard-fail when required-ci-secrets result is not success"
        )
    remote_integrity = blocks.get("remote-integrity", "")
    if not remote_integrity:
        failures.append("ci.yml: remote-integrity: missing job")
    else:
        if "secrets: inherit" in remote_integrity:
            failures.append(
                "ci.yml: remote-integrity: must not use secrets: inherit; pass only REMOTE_INTEGRITY_GH_TOKEN explicitly"
            )
        if "REMOTE_INTEGRITY_GH_TOKEN:" not in remote_integrity:
            failures.append(
                "ci.yml: remote-integrity: must pass REMOTE_INTEGRITY_GH_TOKEN explicitly to the reusable workflow"
            )

    # Preflight must include focused-test guard steps.
    required_preflight_markers = {
        "Test focus/todo marker guard": "test focus/todo marker guard step",
        "E2E strictness guard": "e2e strictness guard step",
        "Mutation scope guard": "mutation scope guard step",
        "Mutation test selection guard": "mutation test selection guard step",
    }
    preflight_fast = blocks.get("preflight-fast", "")
    missing_in_preflight = [
        description
        for marker, description in required_preflight_markers.items()
        if marker not in preflight_fast
    ]
    if missing_in_preflight:
        reusable_path = Path(".github/workflows/_preflight-fast-steps.yml")
        if reusable_path.is_file():
            reusable_text = reusable_path.read_text(encoding="utf-8")
            for marker, description in required_preflight_markers.items():
                if marker not in reusable_text:
                    failures.append(
                        f"ci.yml: preflight-fast: missing {description} (delegated to _preflight-fast-steps.yml)"
                    )
        else:
            failures.append(
                "ci.yml: preflight-fast: reusable workflow _preflight-fast-steps.yml not found"
            )

    # live-smoke must run on a fully provisioned local stack and enforce secrets.
    live_smoke = blocks.get("live-smoke", "")
    if live_smoke:
        required_live_smoke_markers = {
            "services:\n      postgres:": "postgres service",
            "./bin/strict-ci --mode live-smoke": "strict ci entry live-smoke command",
            "GEMINI_API_KEY": "gemini secret wiring",
            "RESEND_API_KEY": "resend secret wiring",
            "YOUTUBE_API_KEY": "youtube secret wiring",
        }
        for marker, description in required_live_smoke_markers.items():
            if marker not in live_smoke:
                failures.append(f"ci.yml: live-smoke: missing {description}")


def main() -> int:
    if not WORKFLOW_PATH.is_file():
        raise SystemExit(f"missing workflow file: {WORKFLOW_PATH}")

    failures: list[str] = []
    if not CONTRACT_PATH.is_file():
        failures.append(f"missing strict CI contract file: {CONTRACT_PATH}")
    else:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        digest = str(contract.get("standard_image", {}).get("digest", "")).strip()
        if not DIGEST_PATTERN.fullmatch(digest):
            failures.append(
                "strict_ci_contract.json: standard_image.digest must be a sha256 digest"
            )
        service_images = contract.get("service_images", {})
        if not isinstance(service_images, dict) or not service_images:
            failures.append(
                "strict_ci_contract.json: service_images must define pinned image references"
            )
        else:
            for name, image_ref in service_images.items():
                if "@sha256:" not in str(image_ref):
                    failures.append(
                        f"strict_ci_contract.json: service_images.{name} must be pinned by digest"
                    )
    if not RUNNER_BASELINE_CONTRACT_PATH.is_file():
        failures.append(f"missing runner baseline contract file: {RUNNER_BASELINE_CONTRACT_PATH}")
    workflow_files = sorted(WORKFLOW_DIR.glob("*.yml"))
    if not workflow_files:
        failures.append("missing workflow files under .github/workflows")
    for workflow in workflow_files:
        text = workflow.read_text(encoding="utf-8")
        blocks = dict(_job_blocks(text))
        _check_global_rules(workflow, text, blocks, failures)
        _check_shared_self_hosted_pr_boundary_rules(workflow, text, blocks, failures)
        if workflow == WORKFLOW_PATH:
            if not _uses_public_hosted_first_ci(blocks):
                _check_ci_specific_rules(blocks, failures)
        elif workflow == BUILD_PUBLIC_API_IMAGE_WORKFLOW_PATH:
            _check_build_public_api_image_specific_rules(text, failures)
        elif workflow == BUILD_STANDARD_IMAGE_WORKFLOW_PATH:
            _check_build_standard_image_specific_rules(text, failures)
        elif workflow == RELEASE_EVIDENCE_WORKFLOW_PATH:
            _check_release_evidence_specific_rules(text, failures)
        elif workflow == PUBLISH_PYPI_WORKFLOW_PATH:
            _check_publish_pypi_specific_rules(text, failures)
        elif workflow == PUBLISH_MCP_REGISTRY_WORKFLOW_PATH:
            _check_publish_mcp_registry_specific_rules(text, failures)
        elif workflow == RUNNER_HEALTH_WORKFLOW_PATH:
            _check_runner_health_specific_rules(text, blocks, failures)
        elif workflow == REMOTE_INTEGRITY_WORKFLOW_PATH:
            _check_remote_integrity_specific_rules(text, blocks, failures)

    if failures:
        print("ci workflow strictness gate failed:")
        for item in failures:
            print(f"- {item}")
        return 1

    print("ci workflow strictness gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
