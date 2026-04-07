from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_module(path: str, name: str):
    module_path = _repo_root() / path
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bootstrap_repo_chrome_fails_when_real_chrome_process_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module("scripts/runtime/bootstrap_repo_chrome.py", "bootstrap_repo_chrome")

    monkeypatch.setattr(
        module,
        "list_default_root_chrome_processes",
        lambda default_user_data_dir: [
            {"pid": "123", "command": "/Applications/Google Chrome.app/..."}
        ],
    )
    monkeypatch.setattr(sys, "argv", ["bootstrap_repo_chrome.py", "--json"])

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "close default-root Chrome windows first" in captured.err


def test_start_repo_chrome_reports_already_running_without_second_launch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module("scripts/runtime/start_repo_chrome.py", "start_repo_chrome")
    payload = {
        "chrome_channel": "chrome",
        "user_data_dir": str(tmp_path / "chrome-user-data"),
        "profile_dir": "Profile 1",
        "profile_path": str(tmp_path / "chrome-user-data" / "Profile 1"),
        "profile_name": "sourceharbor",
        "cdp_port": 9339,
        "cdp_url": "http://127.0.0.1:9339",
    }
    (tmp_path / "chrome-user-data" / "Profile 1").mkdir(parents=True)

    monkeypatch.setattr(module, "resolve_repo_runtime", lambda **_: payload)
    monkeypatch.setattr(
        module,
        "list_repo_chrome_processes",
        lambda user_data_dir: [{"pid": "321", "command": f"--user-data-dir={user_data_dir}"}],
    )
    monkeypatch.setattr(module, "list_actual_chrome_processes", list)
    monkeypatch.setattr(module, "is_cdp_alive", lambda port: True)
    monkeypatch.setattr(
        module,
        "write_json_artifact",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["start_repo_chrome.py", "--user-data-dir", str(tmp_path / "chrome-user-data"), "--json"],
    )

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    response = json.loads(captured.out)
    assert response["status"] == "already-running"
    assert response["cdp_url"] == "http://127.0.0.1:9339"


def test_start_repo_chrome_rejects_machine_with_more_than_four_instances(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module("scripts/runtime/start_repo_chrome.py", "start_repo_chrome_busy")
    payload = {
        "chrome_channel": "chrome",
        "user_data_dir": str(tmp_path / "chrome-user-data"),
        "profile_dir": "Profile 1",
        "profile_path": str(tmp_path / "chrome-user-data" / "Profile 1"),
        "profile_name": "sourceharbor",
        "cdp_port": 9339,
        "cdp_url": "http://127.0.0.1:9339",
    }
    (tmp_path / "chrome-user-data" / "Profile 1").mkdir(parents=True)

    monkeypatch.setattr(module, "resolve_repo_runtime", lambda **_: payload)
    monkeypatch.setattr(module, "list_repo_chrome_processes", lambda user_data_dir: [])
    monkeypatch.setattr(
        module,
        "list_actual_chrome_processes",
        lambda: [{"pid": str(i), "command": f"chrome-{i}"} for i in range(7)],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["start_repo_chrome.py", "--user-data-dir", str(tmp_path / "chrome-user-data"), "--json"],
    )

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "more than 6 Chrome instances" in captured.err


def test_start_repo_chrome_allows_explicit_over_cap_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module(
        "scripts/runtime/start_repo_chrome.py", "start_repo_chrome_allow_over_cap"
    )
    payload = {
        "chrome_channel": "chrome",
        "user_data_dir": str(tmp_path / "chrome-user-data"),
        "profile_dir": "Profile 1",
        "profile_path": str(tmp_path / "chrome-user-data" / "Profile 1"),
        "profile_name": "sourceharbor",
        "cdp_port": 9339,
        "cdp_url": "http://127.0.0.1:9339",
    }
    (tmp_path / "chrome-user-data" / "Profile 1").mkdir(parents=True)

    class _FakeProcess:
        pid = 999

    monkeypatch.setattr(module, "resolve_repo_runtime", lambda **_: payload)
    monkeypatch.setattr(module, "list_repo_chrome_processes", lambda user_data_dir: [])
    monkeypatch.setattr(
        module,
        "list_actual_chrome_processes",
        lambda: [{"pid": str(i), "command": f"chrome-{i}"} for i in range(8)],
    )
    monkeypatch.setattr(
        module,
        "resolve_chrome_binary",
        lambda explicit_binary="": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    )
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(
        module, "wait_for_cdp", lambda port, timeout_seconds=20.0: {"Browser": "Chrome"}
    )
    monkeypatch.setattr(module, "write_json_artifact", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "start_repo_chrome.py",
            "--user-data-dir",
            str(tmp_path / "chrome-user-data"),
            "--allow-over-cap",
            "--json",
        ],
    )

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    response = json.loads(captured.out)
    assert response["status"] == "started"
    assert response["allow_over_cap"] is True


def test_stop_repo_chrome_reports_already_stopped(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module("scripts/runtime/stop_repo_chrome.py", "stop_repo_chrome")
    payload = {
        "chrome_channel": "chrome",
        "user_data_dir": str(tmp_path / "chrome-user-data"),
        "profile_dir": "Profile 1",
        "profile_path": str(tmp_path / "chrome-user-data" / "Profile 1"),
        "profile_name": "sourceharbor",
        "cdp_port": 9339,
        "cdp_url": "http://127.0.0.1:9339",
    }
    (tmp_path / "chrome-user-data" / "Profile 1").mkdir(parents=True)

    monkeypatch.setattr(module, "resolve_repo_runtime", lambda **_: payload)
    monkeypatch.setattr(module, "list_repo_chrome_processes", lambda user_data_dir: [])
    monkeypatch.setattr(module, "is_cdp_alive", lambda port: False)
    monkeypatch.setattr(module, "write_json_artifact", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["stop_repo_chrome.py", "--user-data-dir", str(tmp_path / "chrome-user-data"), "--json"],
    )

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    response = json.loads(captured.out)
    assert response["status"] == "already-stopped"


def test_stop_repo_chrome_stops_process_and_cleans_ephemerals(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module("scripts/runtime/stop_repo_chrome.py", "stop_repo_chrome_run")
    payload = {
        "chrome_channel": "chrome",
        "user_data_dir": str(tmp_path / "chrome-user-data"),
        "profile_dir": "Profile 1",
        "profile_path": str(tmp_path / "chrome-user-data" / "Profile 1"),
        "profile_name": "sourceharbor",
        "cdp_port": 9339,
        "cdp_url": "http://127.0.0.1:9339",
    }
    (tmp_path / "chrome-user-data" / "Profile 1").mkdir(parents=True)
    process_states = [
        [{"pid": "321", "command": "--user-data-dir=/tmp/chrome-user-data"}],
        [],
    ]
    killed: list[tuple[int, int]] = []
    cleaned: list[tuple[Path, str]] = []

    monkeypatch.setattr(module, "resolve_repo_runtime", lambda **_: payload)
    monkeypatch.setattr(
        module,
        "list_repo_chrome_processes",
        lambda user_data_dir: process_states.pop(0) if process_states else [],
    )
    monkeypatch.setattr(module, "is_cdp_alive", lambda port: False)
    monkeypatch.setattr(module.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        module,
        "remove_ephemeral_artifacts",
        lambda user_data_dir, profile_dir: cleaned.append((user_data_dir, profile_dir)),
    )
    monkeypatch.setattr(module, "write_json_artifact", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["stop_repo_chrome.py", "--user-data-dir", str(tmp_path / "chrome-user-data"), "--json"],
    )

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    response = json.loads(captured.out)
    assert response["status"] == "stopped"
    assert response["terminated_pids"] == ["321"]
    assert killed[0][0] == 321
    assert cleaned == [(tmp_path / "chrome-user-data", "Profile 1")]


def test_open_repo_chrome_tabs_opens_login_site_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module("scripts/runtime/open_repo_chrome_tabs.py", "open_repo_chrome_tabs")
    payload = {
        "chrome_channel": "chrome",
        "user_data_dir": str(tmp_path / "chrome-user-data"),
        "profile_dir": "Profile 1",
        "profile_path": str(tmp_path / "chrome-user-data" / "Profile 1"),
        "profile_name": "sourceharbor",
        "cdp_port": 9339,
        "cdp_url": "http://127.0.0.1:9339",
    }
    (tmp_path / "chrome-user-data" / "Profile 1").mkdir(parents=True)
    closed: list[str] = []
    opened: list[str] = []

    monkeypatch.setattr(module, "resolve_repo_runtime", lambda **_: payload)
    monkeypatch.setattr(module, "is_cdp_alive", lambda port: True)
    monkeypatch.setattr(
        module,
        "list_repo_chrome_processes",
        lambda user_data_dir: [{"pid": "456", "command": f"--user-data-dir={user_data_dir}"}],
    )
    monkeypatch.setattr(
        module,
        "list_page_targets",
        lambda port: [{"id": "blank-a", "type": "page"}, {"id": "blank-b", "type": "page"}],
    )
    monkeypatch.setattr(
        module, "close_page_target", lambda port, target_id: closed.append(target_id)
    )
    monkeypatch.setattr(
        module,
        "open_page_target",
        lambda port, url: {"id": f"id-{len(opened) + 1}", "url": opened.append(url) or url},
    )
    monkeypatch.setattr(module, "write_json_artifact", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "open_repo_chrome_tabs.py",
            "--user-data-dir",
            str(tmp_path / "chrome-user-data"),
            "--json",
        ],
    )

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    response = json.loads(captured.out)
    assert response["status"] == "opened"
    assert response["site_set"] == "login-strong-check"
    assert closed == ["blank-a", "blank-b"]
    assert response["pid_candidates"] == ["456"]
    assert opened == [
        "https://myaccount.google.com/",
        "https://www.youtube.com/",
        "https://account.bilibili.com/account/home",
        "https://resend.com/login",
    ]


def test_open_repo_chrome_tabs_fails_when_repo_owned_process_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module(
        "scripts/runtime/open_repo_chrome_tabs.py",
        "open_repo_chrome_tabs_missing_process",
    )
    payload = {
        "chrome_channel": "chrome",
        "user_data_dir": str(tmp_path / "chrome-user-data"),
        "profile_dir": "Profile 1",
        "profile_path": str(tmp_path / "chrome-user-data" / "Profile 1"),
        "profile_name": "sourceharbor",
        "cdp_port": 9339,
        "cdp_url": "http://127.0.0.1:9339",
    }
    (tmp_path / "chrome-user-data" / "Profile 1").mkdir(parents=True)

    monkeypatch.setattr(module, "resolve_repo_runtime", lambda **_: payload)
    monkeypatch.setattr(module, "list_repo_chrome_processes", lambda user_data_dir: [])
    monkeypatch.setattr(module, "is_cdp_alive", lambda port: True)
    monkeypatch.setattr(
        sys,
        "argv",
        ["open_repo_chrome_tabs.py", "--user-data-dir", str(tmp_path / "chrome-user-data")],
    )

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "repo-owned Chrome process is not running" in captured.err
