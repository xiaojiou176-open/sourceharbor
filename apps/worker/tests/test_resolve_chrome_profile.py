from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_module():
    module_path = _repo_root() / "scripts" / "runtime" / "resolve_chrome_profile.py"
    spec = importlib.util.spec_from_file_location("resolve_chrome_profile", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_chrome_profile_source_mode_by_display_name(tmp_path: Path) -> None:
    module = _load_module()
    user_data_dir = tmp_path / "Chrome"
    profile_dir = user_data_dir / "Profile 27"
    profile_dir.mkdir(parents=True)
    (user_data_dir / "Local State").write_text(
        json.dumps(
            {
                "profile": {
                    "info_cache": {
                        "Profile 27": {
                            "name": "sourceharbor",
                            "user_name": "sourceharbor-test@example.com",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    payload = module.resolve_chrome_profile(
        user_data_dir=str(user_data_dir),
        profile_name="sourceharbor",
        profile_dir="",
    )

    assert payload["chrome_channel"] == "chrome"
    assert payload["user_data_dir"] == str(user_data_dir)
    assert payload["profile_dir"] == "Profile 27"
    assert payload["profile_path"] == str(profile_dir)


def test_resolve_repo_runtime_uses_profile1_and_cdp_defaults(tmp_path: Path) -> None:
    module = _load_module()
    user_data_dir = tmp_path / "chrome-user-data"
    profile_dir = user_data_dir / "Profile 1"
    profile_dir.mkdir(parents=True)
    (user_data_dir / "Local State").write_text(
        json.dumps(
            {
                "profile": {
                    "last_used": "Profile 1",
                    "last_active_profiles": ["Profile 1"],
                    "info_cache": {"Profile 1": {"name": "sourceharbor"}},
                }
            }
        ),
        encoding="utf-8",
    )

    payload = module.resolve_repo_runtime(
        user_data_dir=str(user_data_dir),
        profile_name="sourceharbor",
        profile_dir="Profile 1",
        cdp_port="9339",
    )

    assert payload["profile_dir"] == "Profile 1"
    assert payload["profile_name"] == "sourceharbor"
    assert payload["cdp_port"] == 9339
    assert payload["cdp_url"] == "http://127.0.0.1:9339"


def test_resolve_repo_runtime_fails_when_profile_name_mismatches(tmp_path: Path) -> None:
    module = _load_module()
    user_data_dir = tmp_path / "chrome-user-data"
    profile_dir = user_data_dir / "Profile 1"
    profile_dir.mkdir(parents=True)
    (user_data_dir / "Local State").write_text(
        json.dumps(
            {"profile": {"info_cache": {"Profile 1": {"name": "other"}}}},
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="expected `sourceharbor`"):
        module.resolve_repo_runtime(
            user_data_dir=str(user_data_dir),
            profile_name="sourceharbor",
            profile_dir="Profile 1",
            cdp_port="9339",
        )
