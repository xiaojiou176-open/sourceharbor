from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_ci_autofix_module():
    module_path = Path(__file__).resolve().parents[3] / "scripts" / "ci" / "autofix.py"
    spec = importlib.util.spec_from_file_location("ci_autofix", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_junit_failure_element_without_truthy_children(tmp_path: Path) -> None:
    module = _load_ci_autofix_module()
    junit = tmp_path / "junit.xml"
    junit.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<testsuite tests="1" failures="1">
  <testcase classname="suite.alpha" name="test_failure_short_circuit">
    <failure message="AssertionError: expected 1 to equal 2"/>
  </testcase>
</testsuite>
""",
        encoding="utf-8",
    )

    findings = module._parse_junit_file(junit)

    assert len(findings) == 1
    assert findings[0]["source_type"] == "junit"
    assert findings[0]["examples"][0] == "suite.alpha::test_failure_short_circuit"
    assert "expected # to equal #" in findings[0]["signal"]


def test_parse_junit_with_xml_namespace(tmp_path: Path) -> None:
    module = _load_ci_autofix_module()
    junit = tmp_path / "junit-ns.xml"
    junit.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<testsuite xmlns="urn:example:junit" tests="1" failures="1">
  <testcase classname="suite.ns" name="test_namespaced_case">
    <failure message="AssertionError: expected 3 to equal 4"/>
  </testcase>
</testsuite>
""",
        encoding="utf-8",
    )

    findings = module._parse_junit_file(junit)

    assert len(findings) == 1
    assert findings[0]["examples"][0] == "suite.ns::test_namespaced_case"
    assert findings[0]["category"] == "test_assertion"


def test_expand_inputs_supports_relative_glob(monkeypatch, tmp_path: Path) -> None:
    module = _load_ci_autofix_module()
    rel_xml = tmp_path / "relative.xml"
    rel_xml.write_text("<testsuite/>", encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    expanded = module._expand_inputs([], ["*.xml"])

    assert [path.name for path in expanded] == ["relative.xml"]


def test_expand_inputs_supports_absolute_glob(tmp_path: Path) -> None:
    module = _load_ci_autofix_module()
    abs_dir = tmp_path / "reports"
    abs_dir.mkdir()
    abs_xml = abs_dir / "absolute.xml"
    abs_xml.write_text("<testsuite/>", encoding="utf-8")
    (abs_dir / "ignore.log").write_text("x", encoding="utf-8")

    expanded = module._expand_inputs([], [str(abs_dir / "*.xml")])

    assert [path.resolve() for path in expanded] == [abs_xml.resolve()]


def test_parse_log_file_redacts_and_truncates_examples(tmp_path: Path) -> None:
    module = _load_ci_autofix_module()
    log_file = tmp_path / "ci.log"
    secret = "redaction-target-abcdefghijklmnopqrstuvwxyz123456"
    long_suffix = "x" * 400
    log_file.write_text(
        f"npm ERR! request failed token={secret} authorization=Bearer AAA.BBB.CCC {long_suffix}\n",
        encoding="utf-8",
    )

    findings = module._parse_log_file(log_file)

    assert len(findings) == 1
    assert findings[0]["source_type"] == "log"
    assert "<redacted>" in findings[0]["examples"][0]
    assert secret not in findings[0]["examples"][0]
    assert len(findings[0]["examples"][0]) <= module.MAX_EXAMPLE_CHARS


def test_parse_junit_file_rejects_oversized_input(tmp_path: Path) -> None:
    module = _load_ci_autofix_module()
    junit = tmp_path / "oversized.xml"
    junit.write_text("<testsuite>" + ("a" * 4096) + "</testsuite>", encoding="utf-8")

    findings = module._parse_junit_file(junit, max_bytes=64)

    assert len(findings) == 1
    assert findings[0]["source_type"] == "junit"
    assert findings[0]["category"] == "resource_limit"
    assert "file too large" in findings[0]["signal"]


def test_parse_junit_signal_is_redacted(tmp_path: Path) -> None:
    module = _load_ci_autofix_module()
    secret = "redaction-target-abcdefghijklmnopqrstuvwxyz123456"
    junit = tmp_path / "junit-secret.xml"
    junit.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<testsuite tests="1" failures="1">
  <testcase classname="suite.secret" name="test_secret_signal">
    <failure message="RuntimeError: provider token={secret}"/>
  </testcase>
</testsuite>
""",
        encoding="utf-8",
    )

    findings = module._parse_junit_file(junit)

    assert len(findings) == 1
    assert "<redacted>" in findings[0]["signal"]
    assert secret not in findings[0]["signal"]


def test_parse_log_signal_is_redacted(tmp_path: Path) -> None:
    module = _load_ci_autofix_module()
    secret = "ghp_" + "abcdefghijklmnopqrstuvwxyz123456"
    log_file = tmp_path / "secret.log"
    log_file.write_text(
        f"RuntimeError: request failed token={secret}\n",
        encoding="utf-8",
    )

    findings = module._parse_log_file(log_file)

    assert len(findings) == 1
    assert "<redacted>" in findings[0]["signal"]
    assert secret not in findings[0]["signal"]
