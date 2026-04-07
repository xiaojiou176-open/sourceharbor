from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from integrations.binaries.media_commands import (
    bbdown_commands,
    build_download_provider_chain,
    yt_dlp_download_command,
)
from worker.pipeline.types import CommandResult, PipelineContext, StepExecution, StepStatus


def extract_media_file(download_dir: Path, command_stdout: str) -> str | None:
    for line in reversed(command_stdout.splitlines()):
        candidate = line.strip()
        if not candidate:
            continue
        if Path(candidate).exists():
            return str(Path(candidate).resolve())

    suffixes = {".mp4", ".mkv", ".webm", ".flv", ".mov", ".m4v", ".ts"}
    files = sorted(
        [
            p
            for p in download_dir.glob("*")
            if p.is_file()
            and p.suffix.lower() not in {".part", ".tmp"}
            and (p.name.startswith("media.") or p.suffix.lower() in suffixes)
        ],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if files:
        return str(files[0].resolve())
    return None


async def step_download_media(
    ctx: PipelineContext,
    state: dict[str, Any],
    *,
    run_command: Callable[[PipelineContext, list[str]], Awaitable[CommandResult]],
) -> StepExecution:
    source_url = str(state.get("source_url") or "")
    platform = str(state.get("platform") or "").strip().lower()
    if not source_url:
        return StepExecution(
            status="skipped",
            state_updates={"media_path": None, "download_mode": "text_only"},
            reason="source_url_missing",
            degraded=True,
        )

    providers = build_download_provider_chain(
        platform, getattr(ctx.settings, "bilibili_downloader", "auto")
    )
    output_tmpl = str((ctx.download_dir / "media.%(ext)s").resolve())
    attempts: list[dict[str, Any]] = []

    for provider in providers:
        provider_result: CommandResult | None = None
        if provider == "yt-dlp":
            provider_result = await run_command(
                ctx, yt_dlp_download_command(source_url, output_tmpl)
            )
        elif provider == "bbdown":
            for cmd in bbdown_commands(source_url, ctx.download_dir):
                provider_result = await run_command(ctx, cmd)
                if provider_result.ok:
                    break
                if provider_result.reason != "binary_not_found":
                    break
            if provider_result is None:
                provider_result = CommandResult(ok=False, reason="binary_not_found")
        else:
            provider_result = CommandResult(ok=False, reason="provider_unsupported")

        media_path = extract_media_file(ctx.download_dir, provider_result.stdout)
        if provider_result.ok and media_path:
            return StepExecution(
                status="succeeded",
                output={"mode": "media", "provider": provider, "providers_tried": providers},
                state_updates={"media_path": media_path, "download_mode": "media"},
            )

        reason = provider_result.reason or "provider_failed"
        if provider_result.ok and not media_path:
            reason = "media_not_found_after_download"
        attempts.append(
            {
                "provider": provider,
                "reason": reason,
                "error": (provider_result.stderr or "").strip()[-500:] or reason,
                "returncode": provider_result.returncode,
            }
        )

    only_binary_missing = bool(attempts) and all(
        str(item.get("reason")) == "binary_not_found" for item in attempts
    )
    status: StepStatus = "skipped" if only_binary_missing else "failed"
    last_attempt = attempts[-1] if attempts else {}
    return StepExecution(
        status=status,
        output={"mode": "text_only", "providers_tried": providers, "attempts": attempts},
        state_updates={"media_path": None, "download_mode": "text_only"},
        reason=str(last_attempt.get("reason") or "download_provider_chain_failed"),
        error=str(last_attempt.get("error") or "download_provider_chain_failed"),
        degraded=True,
    )
