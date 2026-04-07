from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_module():
    module_path = _repo_root() / "scripts" / "runtime" / "sourceharbor_chrome.py"
    spec = importlib.util.spec_from_file_location("sourceharbor_chrome", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_copy_profile_into_repo_root_rewrites_local_state_and_profile_dir(tmp_path: Path) -> None:
    module = _load_module()
    source_root = tmp_path / "default-chrome"
    source_profile = source_root / "Profile 27"
    source_profile.mkdir(parents=True)
    (source_root / "Local State").write_text(
        json.dumps(
            {
                "profile": {
                    "last_used": "Profile 19",
                    "last_active_profiles": ["Profile 19"],
                    "info_cache": {
                        "Profile 27": {
                            "name": "sourceharbor",
                            "user_name": "sourceharbor-test@example.com",
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    (source_profile / "Cookies").write_text("cookies", encoding="utf-8")
    (source_profile / "Login Data").write_text("login", encoding="utf-8")
    (source_profile / "Preferences").write_text("prefs", encoding="utf-8")
    (source_profile / "Extensions").mkdir()
    (source_profile / "LOCK").write_text("lock", encoding="utf-8")

    target_root = tmp_path / "repo-chrome"
    report = module.copy_profile_into_repo_root(
        source_user_data_dir=source_root,
        source_profile_dir="Profile 27",
        target_user_data_dir=target_root,
        target_profile_dir="Profile 1",
        profile_name="sourceharbor",
    )

    target_profile = target_root / "Profile 1"
    assert target_profile.is_dir()
    assert not (target_profile / "LOCK").exists()
    payload = json.loads((target_root / "Local State").read_text(encoding="utf-8"))
    assert payload["profile"]["last_used"] == "Profile 1"
    assert payload["profile"]["last_active_profiles"] == ["Profile 1"]
    assert payload["profile"]["info_cache"]["Profile 1"]["name"] == "sourceharbor"
    assert report["copied_state_markers"]["Cookies"] is True
    assert report["copied_state_markers"]["Login Data"] is True


def test_build_launch_command_uses_isolated_root_profile_and_cdp_port(tmp_path: Path) -> None:
    module = _load_module()
    command = module.build_launch_command(
        chrome_binary="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        user_data_dir=tmp_path / "chrome-user-data",
        profile_dir="Profile 1",
        cdp_port=9339,
        start_url="about:blank",
    )

    assert f"--user-data-dir={tmp_path / 'chrome-user-data'}" in command
    assert "--profile-directory=Profile 1" in command
    assert "--remote-debugging-port=9339" in command
    assert "--remote-debugging-address=127.0.0.1" in command


def test_list_repo_chrome_processes_filters_by_user_data_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    output = (
        "123 /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --user-data-dir=/tmp/sourceharbor/browser/chrome-user-data --profile-directory=Profile 1\n"
        "124 /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --user-data-dir=/tmp/other --profile-directory=Default\n"
        "125 /Library/PrivilegedHelperTools/ChromeRemoteDesktopHost.app/Contents/MacOS/remoting_me2me_host"
    )

    def _fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    rows = module.list_repo_chrome_processes(Path("/tmp/sourceharbor/browser/chrome-user-data"))

    assert len(rows) == 1
    assert rows[0]["pid"] == "123"
