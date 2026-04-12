from __future__ import annotations

import importlib.util
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_module():
    module_path = _repo_root() / "scripts" / "governance" / "common.py"
    spec = importlib.util.spec_from_file_location("sourceharbor_governance_common", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_write_text_artifact_redacts_sensitive_patterns(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / "artifact.txt"
    bearer_value = "Authorization: " + "Bearer " + "abc.def.ghi"
    api_key_value = "api" + "_key=" + "demo-test-key-value"
    private_key_header = "-----BEGIN " + "RSA PRIVATE KEY-----"

    module.write_text_artifact(
        target,
        f'{bearer_value}\n{api_key_value}\n{{"password":"super-secret-value"}}\n{private_key_header}',
        source_entrypoint="unit-test",
        verification_scope="test",
    )

    rendered = target.read_text(encoding="utf-8")
    assert "abc.def.ghi" not in rendered
    assert "demo-test-key-value" not in rendered
    assert "super-secret-value" not in rendered
    assert private_key_header not in rendered
    assert "Bearer ***REDACTED***" in rendered
    assert "api_key=***REDACTED***" in rendered
    assert '"password":***REDACTED***' in rendered
    assert "-----BEGIN ***REDACTED*** PRIVATE KEY-----" in rendered


def test_write_json_artifact_redacts_sensitive_payload_values(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / "artifact.json"
    example_token = "ghp_" + "12345678901234567890"
    db_url = "postgresql://" + "user:password" + "@example.com/db"

    module.write_json_artifact(
        target,
        {
            "token": example_token,
            "safe": "ok",
            "db": db_url,
        },
        source_entrypoint="unit-test",
        verification_scope="test",
    )

    rendered = target.read_text(encoding="utf-8")
    assert example_token not in rendered
    assert "password@example.com" not in rendered
    assert '"safe": "ok"' in rendered
    assert '"token": ***REDACTED***' in rendered
    assert "postgresql://***:***@" in rendered


def test_write_runtime_metadata_redacts_sensitive_extra_values(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / "artifact.txt"
    target.write_text("ok", encoding="utf-8")

    module.write_runtime_metadata(
        target,
        source_entrypoint="unit-test",
        verification_scope="test",
        extra={
            "password": "plain-text-should-not-land",
            "token": "ghp_" + "12345678901234567890",
            "nested": {
                "cookie": "session=top-secret-cookie",
                "safe": "ok",
            },
        },
    )

    metadata = module.read_runtime_metadata(target)
    assert metadata is not None
    rendered = module.runtime_metadata_path(target).read_text(encoding="utf-8")

    assert "plain-text-should-not-land" not in rendered
    assert "12345678901234567890" not in rendered
    assert "top-secret-cookie" not in rendered
    assert metadata["password"] == "***REDACTED***"
    assert metadata["token"] == "***REDACTED***"
    assert metadata["nested"]["cookie"] == "***REDACTED***"
    assert metadata["nested"]["safe"] == "ok"


def test_is_runtime_metadata_managed_artifact_skips_python_coverage_shards(tmp_path: Path) -> None:
    module = _load_module()
    shard = tmp_path / "reports" / "python" / ".coverage.demo.pid123"
    shard.parent.mkdir(parents=True, exist_ok=True)
    shard.write_text("stub", encoding="utf-8")

    combined = shard.with_name(".coverage")
    combined.write_text("stub", encoding="utf-8")
    report = shard.with_name("python-coverage.xml")
    report.write_text("<coverage/>", encoding="utf-8")

    assert module.is_runtime_metadata_managed_artifact(shard) is False
    assert module.is_runtime_metadata_managed_artifact(combined) is True
    assert module.is_runtime_metadata_managed_artifact(report) is True
