from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Literal, NotRequired, TypedDict
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Browser, sync_playwright
from support.mock_api import (
    MockApiServer,
    MockApiState,
    start_mock_api_server,
    stop_mock_api_server,
)
from support.runtime_utils import (
    parse_external_web_base_url,
    resolve_worker_id,
    slugify_nodeid,
    wait_http_ok,
    with_free_port_retry,
    worker_dist_dir,
)

PROJECT_ROOT = Path(
    os.environ.get("SOURCE_HARBOR_REPO_ROOT") or Path(__file__).resolve().parents[4]
)
WEB_DIR = PROJECT_ROOT / "apps" / "web"
WEB_E2E_ARTIFACT_ROOT = PROJECT_ROOT / ".runtime-cache" / "evidence" / "tests" / "web-e2e-artifacts"
WEB_E2E_VIDEO_DIR = WEB_E2E_ARTIFACT_ROOT / "videos"
WEB_E2E_TRACE_DIR = WEB_E2E_ARTIFACT_ROOT / "traces"
WEB_E2E_SCREENSHOT_DIR = WEB_E2E_ARTIFACT_ROOT / "screenshots"
WEB_E2E_WRITE_TOKEN = "sourceharbor-local-dev-token"

DeviceProfile = Literal["desktop", "tablet", "mobile"]
ReducedMotion = Literal["no-preference", "reduce"]


class BrowserNewContextKwargs(TypedDict):
    base_url: str
    viewport: dict[str, int]
    is_mobile: bool
    has_touch: bool
    device_scale_factor: int
    record_video_dir: NotRequired[str]


for artifact_dir in (WEB_E2E_VIDEO_DIR, WEB_E2E_TRACE_DIR, WEB_E2E_SCREENSHOT_DIR):
    artifact_dir.mkdir(parents=True, exist_ok=True)


class _PortInUseStartupError(RuntimeError):
    pass


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_use_mock_api(config: pytest.Config) -> bool:
    option_value = config.getoption("--web-e2e-use-mock-api")
    env_value = os.environ.get("WEB_E2E_USE_MOCK_API")
    option_enabled = _is_truthy(None if option_value is None else str(option_value))
    env_enabled = _is_truthy(env_value)
    return option_enabled or env_enabled


def _mock_api_disabled_message() -> str:
    return (
        "Mock API fixtures are disabled by default for real API E2E coverage. "
        "Enable local debug mode with --web-e2e-use-mock-api=1 "
        "(or WEB_E2E_USE_MOCK_API=1). "
        "CI/mainline E2E should run against the real API. "
        "If a test still requests mock_api_server/mock_api_state, migrate it to real API assertions."
    )


def _read_real_api_base_url(config: pytest.Config) -> str:
    raw_value = str(config.getoption("--web-e2e-api-base-url")).strip().rstrip("/")
    if not raw_value:
        raise RuntimeError("--web-e2e-api-base-url cannot be empty")
    parsed = urlparse(raw_value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError(
            f"--web-e2e-api-base-url must be an absolute http(s) URL, got: {raw_value!r}"
        )
    return raw_value


def _runtime_web_dir() -> Path:
    runtime_dir = os.environ.get("WEB_E2E_RUNTIME_WEB_DIR") or os.environ.get("WEB_RUNTIME_WEB_DIR")
    if runtime_dir:
        return Path(runtime_dir)
    return WEB_DIR


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--web-e2e-base-url",
        action="store",
        default="",
        help="Optional absolute http(s) base URL for reusing an existing web instance",
    )
    parser.addoption(
        "--web-e2e-browser",
        action="store",
        default="chromium",
        help="Playwright browser for web e2e: chromium|firefox|webkit",
    )
    parser.addoption(
        "--web-e2e-trace-mode",
        action="store",
        default="off",
        help="Playwright tracing mode: off|on|retain-on-failure",
    )
    parser.addoption(
        "--web-e2e-video-mode",
        action="store",
        default="retain-on-failure",
        help="Playwright video mode: off|on|retain-on-failure",
    )
    parser.addoption(
        "--web-e2e-worker-id",
        action="store",
        default="",
        help="Optional worker id suffix for isolated Next.js dist dir",
    )
    parser.addoption(
        "--web-e2e-api-base-url",
        action="store",
        default="http://127.0.0.1:18080",
        help="Real API base URL injected into NEXT_PUBLIC_API_BASE_URL when conftest starts Next.js.",
    )
    parser.addoption(
        "--web-e2e-use-mock-api",
        action="store",
        default="",
        help="Enable mock API wiring for local debug only (1/true/yes/on); CI defaults to real API.",
    )
    parser.addoption(
        "--web-e2e-device-profile",
        action="store",
        default="desktop",
        help="Device profile for Playwright context: desktop|tablet|mobile",
    )
    parser.addoption(
        "--web-e2e-reduced-motion",
        action="store",
        default="no-preference",
        help="reduced motion preference: no-preference|reduce",
    )
    parser.addoption(
        "--web-e2e-cpu-throttle",
        action="store",
        default="1",
        help="Chromium-only CPU throttle rate (integer >=1)",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "web_e2e_device(profile): override Playwright device profile for this test/file.",
    )
    config.addinivalue_line(
        "markers",
        "web_e2e_reduced_motion(value): override reduced-motion preference for this test/file.",
    )
    config.addinivalue_line(
        "markers",
        "web_e2e_cpu_throttle(rate): override CPU throttle rate for this test/file.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _read_use_mock_api(config):
        return

    deselected = [item for item in items if item.nodeid.endswith("_with_mock_api")]
    if not deselected:
        return

    kept = [item for item in items if not item.nodeid.endswith("_with_mock_api")]
    items[:] = kept
    config.hook.pytest_deselected(items=deselected)


def _read_trace_mode(config: pytest.Config) -> str:
    mode = str(config.getoption("--web-e2e-trace-mode")).strip().lower()
    allowed = {"off", "on", "retain-on-failure"}
    if mode not in allowed:
        raise RuntimeError(
            f"unsupported --web-e2e-trace-mode={mode!r}; expected one of {sorted(allowed)}"
        )
    return mode


def _read_video_mode(config: pytest.Config) -> str:
    mode = str(config.getoption("--web-e2e-video-mode")).strip().lower()
    allowed = {"off", "on", "retain-on-failure"}
    if mode not in allowed:
        raise RuntimeError(
            f"unsupported --web-e2e-video-mode={mode!r}; expected one of {sorted(allowed)}"
        )
    return mode


def _read_device_profile(config: pytest.Config) -> DeviceProfile:
    profile = str(config.getoption("--web-e2e-device-profile")).strip().lower()
    allowed: set[DeviceProfile] = {"desktop", "tablet", "mobile"}
    if profile not in allowed:
        raise RuntimeError(
            f"unsupported --web-e2e-device-profile={profile!r}; expected one of {sorted(allowed)}"
        )
    return profile


def _read_reduced_motion(config: pytest.Config) -> ReducedMotion:
    value = str(config.getoption("--web-e2e-reduced-motion")).strip().lower()
    allowed: set[ReducedMotion] = {"no-preference", "reduce"}
    if value not in allowed:
        raise RuntimeError(
            f"unsupported --web-e2e-reduced-motion={value!r}; expected one of {sorted(allowed)}"
        )
    return value


def _read_cpu_throttle(config: pytest.Config) -> int:
    raw = str(config.getoption("--web-e2e-cpu-throttle")).strip()
    try:
        throttle = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"--web-e2e-cpu-throttle must be an integer >=1, got: {raw!r}") from exc
    if throttle < 1:
        raise RuntimeError(f"--web-e2e-cpu-throttle must be >=1, got: {throttle}")
    return throttle


def _marker_override(request: pytest.FixtureRequest, name: str) -> object | None:
    marker = request.node.get_closest_marker(name)
    if marker is None or not marker.args:
        return None
    return marker.args[0]


def _resolve_device_profile(request: pytest.FixtureRequest) -> DeviceProfile:
    override = _marker_override(request, "web_e2e_device")
    if isinstance(override, str):
        profile = override.strip().lower()
        if profile:
            return profile
    return _read_device_profile(request.config)


def _resolve_reduced_motion(request: pytest.FixtureRequest) -> ReducedMotion:
    override = _marker_override(request, "web_e2e_reduced_motion")
    if isinstance(override, str):
        value = override.strip().lower()
        if value:
            return value
    return _read_reduced_motion(request.config)


def _resolve_cpu_throttle(request: pytest.FixtureRequest) -> int:
    override = _marker_override(request, "web_e2e_cpu_throttle")
    if isinstance(override, int):
        if override < 1:
            raise RuntimeError(f"web_e2e_cpu_throttle marker must be >=1, got: {override}")
        return override
    return _read_cpu_throttle(request.config)


def _device_profile_context_kwargs(profile: DeviceProfile) -> BrowserNewContextKwargs:
    presets: dict[DeviceProfile, BrowserNewContextKwargs] = {
        "desktop": {
            "viewport": {"width": 1280, "height": 720},
            "is_mobile": False,
            "has_touch": False,
            "device_scale_factor": 1,
        },
        "tablet": {
            "viewport": {"width": 820, "height": 1180},
            "is_mobile": True,
            "has_touch": True,
            "device_scale_factor": 2,
        },
        "mobile": {
            "viewport": {"width": 390, "height": 844},
            "is_mobile": True,
            "has_touch": True,
            "device_scale_factor": 3,
        },
    }
    return presets[profile]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[object]):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


@pytest.fixture(scope="session")
def mock_api_server(pytestconfig: pytest.Config):
    if not _read_use_mock_api(pytestconfig):
        raise RuntimeError(_mock_api_disabled_message())
    running = start_mock_api_server()
    try:
        yield running.api_server
    finally:
        stop_mock_api_server(running)


@pytest.fixture(scope="session")
def web_base_url(pytestconfig: pytest.Config, request: pytest.FixtureRequest):
    use_mock_api = _read_use_mock_api(pytestconfig)
    real_api_base_url = _read_real_api_base_url(pytestconfig)
    external_base_url = parse_external_web_base_url(
        str(pytestconfig.getoption("--web-e2e-base-url"))
    )
    if external_base_url is not None:
        if use_mock_api:
            raise RuntimeError(
                "--web-e2e-use-mock-api cannot be combined with --web-e2e-base-url. "
                "Mock API wiring only works when conftest starts the local Next.js server."
            )
        wait_http_ok(f"{external_base_url}/")
        yield external_base_url
        return

    if shutil.which("npm") is None:
        raise RuntimeError(
            "npm is required for web E2E. Install Node.js/npm in CI before running tests."
        )
    runtime_web_dir = _runtime_web_dir()
    if not (runtime_web_dir / "node_modules").exists():
        raise RuntimeError(
            f"runtime web workspace is missing node_modules: {runtime_web_dir}. "
            "Prepare it via scripts/ci/prepare_web_runtime.sh before E2E."
        )

    process: subprocess.Popen[str] | None = None
    output_thread: threading.Thread | None = None
    output_lines: list[str] = []
    mock_api_server: MockApiServer | None = None
    browser_name = str(pytestconfig.getoption("--web-e2e-browser")).strip().lower()
    configured_worker_id = str(pytestconfig.getoption("--web-e2e-worker-id")).strip()
    worker_id = resolve_worker_id(
        configured_worker_id,
        xdist_worker_id=os.environ.get("PYTEST_XDIST_WORKER"),
        browser_name=browser_name,
    )
    next_dist_dir = worker_dist_dir(worker_id)

    if use_mock_api:
        mock_api_server = request.getfixturevalue("mock_api_server")

    def _start_web_server_on_port(
        web_port: int,
    ) -> tuple[subprocess.Popen[str], threading.Thread, list[str]]:
        nonlocal output_lines
        output_lines = []
        base_url = f"http://127.0.0.1:{web_port}"
        env = os.environ.copy()
        if mock_api_server is not None:
            env["NEXT_PUBLIC_API_BASE_URL"] = mock_api_server.base_url
        else:
            env["NEXT_PUBLIC_API_BASE_URL"] = real_api_base_url
        env.setdefault("SOURCE_HARBOR_API_KEY", WEB_E2E_WRITE_TOKEN)
        env.setdefault("WEB_ACTION_SESSION_TOKEN", WEB_E2E_WRITE_TOKEN)
        env["SOURCE_HARBOR_REPO_ROOT"] = str(PROJECT_ROOT)
        env["PORT"] = str(web_port)
        env["HOSTNAME"] = "127.0.0.1"
        env["CI"] = "1"
        env["WEB_E2E_NEXT_DIST_DIR"] = next_dist_dir

        next_bin = runtime_web_dir / "node_modules" / ".bin" / "next"
        command = (
            [
                str(next_bin),
                "dev",
                "--hostname",
                "127.0.0.1",
                "--port",
                str(web_port),
            ]
            if next_bin.exists()
            else ["npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", str(web_port)]
        )

        local_process = subprocess.Popen(
            command,
            cwd=runtime_web_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        def _capture_output() -> None:
            if local_process.stdout is None:
                return
            for line in local_process.stdout:
                output_lines.append(line.rstrip())

        local_output_thread = threading.Thread(target=_capture_output, daemon=True)
        local_output_thread.start()

        try:
            wait_http_ok(f"{base_url}/")
            return local_process, local_output_thread, output_lines
        except Exception as exc:
            local_process.terminate()
            local_process.wait(timeout=10)
            local_output_thread.join(timeout=2)
            tail = "\n".join(output_lines[-60:])
            message = f"Next.js web server failed to start on port {web_port}.\n--- server output ---\n{tail}"
            if "EADDRINUSE" in tail:
                raise _PortInUseStartupError(message) from exc
            raise RuntimeError(message) from exc

    (process, output_thread, output_lines), web_port = with_free_port_retry(
        _start_web_server_on_port,
        attempts=4,
        retry_if=lambda exc: isinstance(exc, _PortInUseStartupError),
    )
    base_url = f"http://127.0.0.1:{web_port}"

    try:
        yield base_url
    finally:
        assert process is not None
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        assert output_thread is not None
        output_thread.join(timeout=2)


@pytest.fixture
def mock_api_state(mock_api_server: MockApiServer, pytestconfig: pytest.Config) -> MockApiState:
    if not _read_use_mock_api(pytestconfig):
        raise RuntimeError(_mock_api_disabled_message())
    mock_api_server.state.reset()
    return mock_api_server.state


@pytest.fixture(scope="session")
def browser(pytestconfig: pytest.Config):
    browser_name = str(pytestconfig.getoption("--web-e2e-browser")).strip().lower()
    launchers = {"chromium", "firefox", "webkit"}
    if browser_name not in launchers:
        raise RuntimeError(
            f"unsupported --web-e2e-browser={browser_name!r}; expected one of {sorted(launchers)}"
        )
    with sync_playwright() as playwright:
        browser = getattr(playwright, browser_name).launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser: Browser, web_base_url: str, request: pytest.FixtureRequest):
    artifact_slug = slugify_nodeid(request.node.nodeid)
    trace_mode = _read_trace_mode(request.config)
    video_mode = _read_video_mode(request.config)
    device_profile = _resolve_device_profile(request)
    reduced_motion = _resolve_reduced_motion(request)
    cpu_throttle = _resolve_cpu_throttle(request)

    new_context_kwargs: BrowserNewContextKwargs = {"base_url": web_base_url}
    new_context_kwargs.update(_device_profile_context_kwargs(device_profile))
    video_test_dir = WEB_E2E_VIDEO_DIR / artifact_slug
    if video_mode != "off":
        video_test_dir.mkdir(parents=True, exist_ok=True)
        new_context_kwargs["record_video_dir"] = str(video_test_dir)

    context = browser.new_context(**new_context_kwargs)
    if trace_mode != "off":
        context.tracing.start(screenshots=True, snapshots=True, sources=False)
    page = context.new_page()
    page.emulate_media(reduced_motion=reduced_motion)
    if browser.browser_type.name == "chromium" and cpu_throttle > 1:
        try:
            cdp_session = context.new_cdp_session(page)
            cdp_session.send("Emulation.setCPUThrottlingRate", {"rate": cpu_throttle})
        except Exception as exc:
            print(f"[web-e2e] cpu throttle setup skipped for {artifact_slug}: {exc}")
    if browser.browser_type.name == "webkit":
        page.set_default_timeout(30_000)
        page.set_default_navigation_timeout(45_000)
    else:
        page.set_default_timeout(30_000)
        page.set_default_navigation_timeout(45_000)
    yield page
    call_report = getattr(request.node, "rep_call", None)
    failed = call_report is not None and call_report.failed
    if failed:
        try:
            page.screenshot(
                path=str(WEB_E2E_SCREENSHOT_DIR / f"{artifact_slug}.png"),
                full_page=True,
            )
        except Exception as exc:
            print(f"[web-e2e] screenshot capture skipped for {artifact_slug}: {exc}")

    try:
        if trace_mode == "on":
            context.tracing.stop(path=str(WEB_E2E_TRACE_DIR / f"{artifact_slug}.zip"))
        elif trace_mode == "retain-on-failure":
            if failed:
                context.tracing.stop(path=str(WEB_E2E_TRACE_DIR / f"{artifact_slug}.zip"))
            else:
                context.tracing.stop()
    except Exception as exc:
        print(f"[web-e2e] trace finalize skipped for {artifact_slug}: {exc}")

    video_obj = page.video
    try:
        context.close()
    except Exception as exc:
        print(f"[web-e2e] browser context close warning for {artifact_slug}: {exc}")
    if video_mode == "retain-on-failure":
        kept_video_path: Path | None = None
        if video_obj is not None:
            try:
                kept_video_path = Path(video_obj.path())
            except Exception:
                kept_video_path = None

        if failed and kept_video_path is not None and kept_video_path.exists():
            target_path = WEB_E2E_VIDEO_DIR / f"{artifact_slug}{kept_video_path.suffix or '.webm'}"
            if target_path.exists():
                target_path.unlink()
            kept_video_path.replace(target_path)

        shutil.rmtree(video_test_dir, ignore_errors=True)
