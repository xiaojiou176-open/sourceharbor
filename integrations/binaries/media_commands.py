from __future__ import annotations

from pathlib import Path
from typing import Any


def normalize_bilibili_downloader(value: Any) -> str:
    text = str(value or "auto").strip().lower()
    if text in {"auto", "yt-dlp", "bbdown"}:
        return text
    return "auto"


def build_download_provider_chain(platform: str, bilibili_downloader: Any) -> list[str]:
    if platform != "bilibili":
        return ["yt-dlp"]
    selected = normalize_bilibili_downloader(bilibili_downloader)
    if selected == "auto":
        return ["yt-dlp", "bbdown"]
    return [selected]


def _apply_headers(cmd: list[str], headers: dict[str, str] | None) -> list[str]:
    if not headers:
        return cmd
    for key, value in headers.items():
        normalized = str(value or "").strip()
        if not normalized:
            continue
        cmd.extend(["--add-header", f"{key}: {normalized}"])
    return cmd


def yt_dlp_metadata_command(
    source_url: str,
    *,
    headers: dict[str, str] | None = None,
) -> list[str]:
    cmd = [
        "yt-dlp",
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
    ]
    _apply_headers(cmd, headers)
    cmd.append(source_url)
    return cmd


def yt_dlp_download_command(
    source_url: str,
    output_tmpl: str,
    *,
    headers: dict[str, str] | None = None,
) -> list[str]:
    cmd = [
        "yt-dlp",
        "--no-progress",
        "--no-warnings",
        "--write-auto-sub",
        "--write-sub",
        "--sub-format",
        "vtt",
        "-o",
        output_tmpl,
        "--print",
        "after_move:filepath",
    ]
    _apply_headers(cmd, headers)
    cmd.append(source_url)
    return cmd


def bbdown_commands(source_url: str, download_dir: Path) -> list[list[str]]:
    target_dir = str(download_dir.resolve())
    return [
        ["BBDown", source_url, "--work-dir", target_dir, "--save-subtitle"],
        ["bbdown", source_url, "--work-dir", target_dir, "--save-subtitle"],
    ]


def ffmpeg_extract_frames_command(
    media_path: str,
    output_pattern: str,
    *,
    frame_method: str,
    frame_interval: int,
    max_frames: int,
) -> list[str]:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(media_path),
    ]
    if frame_method == "scene":
        cmd += ["-vf", "select='gt(scene,0.3)'", "-vsync", "vfr"]
    else:
        cmd += ["-vf", f"fps=1/{frame_interval}"]
    cmd += ["-frames:v", str(max_frames), output_pattern]
    return cmd
