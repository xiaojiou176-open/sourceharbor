from __future__ import annotations

import socket
import threading

import conftest as e2e_conftest
import pytest
from support.assertions import wait_for_call_count, wait_for_http_call
from support.mock_api import MockApiState
from support.runtime_utils import (
    is_port_in_use_error,
    resolve_worker_id,
    with_free_port_retry,
    worker_dist_dir,
)


def test_with_free_port_retry_recovers_from_port_contention() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        occupied_port = int(occupied.getsockname()[1])

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as free_sock:
            free_sock.bind(("127.0.0.1", 0))
            free_port = int(free_sock.getsockname()[1])

        attempts: list[int] = []
        ports = iter([occupied_port, free_port])

        def _start_on_port(port: int) -> str:
            attempts.append(port)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", port))
            return f"started:{port}"

        result, selected_port = with_free_port_retry(
            _start_on_port,
            attempts=2,
            port_supplier=lambda: next(ports),
            retry_if=is_port_in_use_error,
        )

        assert selected_port == free_port
        assert attempts == [occupied_port, free_port]
        assert result == f"started:{free_port}"


def test_wait_helpers_resume_on_state_notification() -> None:
    state = MockApiState()

    def _emit_call() -> None:
        state.record("poll_ingest", {"max_new_videos": 50})
        state.record(
            "http",
            {
                "method": "POST",
                "path": "/api/v1/ingest/poll",
                "query": "",
                "status": 202,
                "payload": {"max_new_videos": 50},
            },
        )

    timer = threading.Timer(0.01, _emit_call)
    timer.start()
    wait_for_call_count(state, "poll_ingest", 1, timeout_sec=1.0)
    call = wait_for_http_call(
        state,
        method="POST",
        path="/api/v1/ingest/poll",
        status=202,
        payload_contains={"max_new_videos": 50},
        timeout_sec=1.0,
    )
    timer.join(timeout=1)

    assert call["method"] == "POST"


def test_resolve_worker_id_prefers_xdist_worker() -> None:
    resolved = resolve_worker_id(
        "gw9",
        xdist_worker_id="gw2",
        browser_name="chromium",
        process_id=123,
    )
    assert resolved == "gw2"


def test_resolve_worker_id_falls_back_to_cli_worker() -> None:
    resolved = resolve_worker_id(
        "gw1",
        xdist_worker_id="",
        browser_name="firefox",
        process_id=456,
    )
    assert resolved == "gw1"


def test_resolve_worker_id_generates_process_scoped_default() -> None:
    resolved = resolve_worker_id(
        "",
        xdist_worker_id=None,
        browser_name="webkit stable",
        process_id=789,
    )
    assert resolved == "webkit-stable-p789"
    assert worker_dist_dir(resolved) == ".next-e2e-webkit-stable-p789"


class _StubConfig:
    def __init__(self, options: dict[str, str]) -> None:
        self._options = options

    def getoption(self, key: str) -> str:
        return self._options[key]


def test_e2e_runtime_options_parse_valid_values() -> None:
    config = _StubConfig(
        {
            "--web-e2e-device-profile": "mobile",
            "--web-e2e-reduced-motion": "reduce",
            "--web-e2e-cpu-throttle": "3",
        }
    )
    assert e2e_conftest._read_device_profile(config) == "mobile"
    assert e2e_conftest._read_reduced_motion(config) == "reduce"
    assert e2e_conftest._read_cpu_throttle(config) == 3


def test_e2e_runtime_options_reject_invalid_device_profile() -> None:
    config = _StubConfig({"--web-e2e-device-profile": "watch"})
    with pytest.raises(RuntimeError, match="--web-e2e-device-profile"):
        e2e_conftest._read_device_profile(config)


def test_e2e_runtime_options_reject_invalid_reduced_motion() -> None:
    config = _StubConfig({"--web-e2e-reduced-motion": "fast"})
    with pytest.raises(RuntimeError, match="--web-e2e-reduced-motion"):
        e2e_conftest._read_reduced_motion(config)


def test_e2e_runtime_options_reject_invalid_cpu_throttle() -> None:
    non_int = _StubConfig({"--web-e2e-cpu-throttle": "bad"})
    with pytest.raises(RuntimeError, match="--web-e2e-cpu-throttle"):
        e2e_conftest._read_cpu_throttle(non_int)

    too_small = _StubConfig({"--web-e2e-cpu-throttle": "0"})
    with pytest.raises(RuntimeError, match=">=1"):
        e2e_conftest._read_cpu_throttle(too_small)
