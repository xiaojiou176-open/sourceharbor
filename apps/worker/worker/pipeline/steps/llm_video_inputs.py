from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

_GEMINI_VIDEO_PROXY_CLIP_SECONDS = 20
_GEMINI_VIDEO_PROXY_WIDTH = 426
_GEMINI_VIDEO_PROXY_FPS = 6
_GEMINI_VIDEO_DIRECT_MAX_BYTES = 25 * 1024 * 1024


def uploaded_file_state_name(file_obj: Any) -> str:
    raw_state = getattr(file_obj, "state", None)
    if raw_state is None:
        return ""
    state_name = getattr(raw_state, "name", None)
    if isinstance(state_name, str) and state_name.strip():
        return state_name.strip().upper()
    state_value = getattr(raw_state, "value", None)
    if isinstance(state_value, str) and state_value.strip():
        return state_value.strip().upper()
    text = str(raw_state).strip()
    if "." in text:
        text = text.split(".")[-1]
    return text.upper()


def wait_for_uploaded_file_ready(
    client: Any,
    uploaded_file: Any,
    *,
    timeout_seconds: float = 120.0,
    poll_interval_seconds: float = 2.0,
) -> Any:
    file_name = str(getattr(uploaded_file, "name", "") or "").strip()
    files_api = getattr(client, "files", None)
    get_file = getattr(files_api, "get", None)
    if not file_name or get_file is None:
        return uploaded_file

    deadline = time.time() + max(1.0, float(timeout_seconds))
    current = uploaded_file
    while True:
        state_name = uploaded_file_state_name(current)
        if not state_name or state_name == "ACTIVE":
            return current
        if state_name == "FAILED":
            raise RuntimeError(f"uploaded_file_failed:{file_name}")
        if time.time() >= deadline:
            raise RuntimeError(f"uploaded_file_not_ready:{file_name}:{state_name.lower()}")
        time.sleep(max(0.2, float(poll_interval_seconds)))
        current = get_file(name=file_name)


def prepare_video_proxy_for_gemini(media_path: str) -> str:
    source = Path(str(media_path or "").strip())
    if not source.exists() or not source.is_file():
        return str(source)
    if source.suffix.lower() == ".mp4" and source.stat().st_size <= _GEMINI_VIDEO_DIRECT_MAX_BYTES:
        return str(source)
    if source.name.endswith(".gemini-proxy.mp4"):
        return str(source)
    if shutil.which("ffmpeg") is None:
        return str(source)

    proxy_path = source.with_name(f"{source.stem}.gemini-proxy.mp4")
    if (
        proxy_path.exists()
        and proxy_path.is_file()
        and proxy_path.stat().st_size > 0
        and proxy_path.stat().st_mtime >= source.stat().st_mtime
    ):
        return str(proxy_path)

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        "0",
        "-t",
        str(_GEMINI_VIDEO_PROXY_CLIP_SECONDS),
        "-i",
        str(source),
        "-vf",
        f"fps={_GEMINI_VIDEO_PROXY_FPS},scale={_GEMINI_VIDEO_PROXY_WIDTH}:-2",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "32",
        "-movflags",
        "+faststart",
        str(proxy_path),
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError):
        return str(source)
    if proxy_path.exists() and proxy_path.is_file() and proxy_path.stat().st_size > 0:
        return str(proxy_path)
    return str(source)
