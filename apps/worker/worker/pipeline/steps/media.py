from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import is_dataclass, replace
from pathlib import Path
from typing import Any

from integrations.binaries.media_commands import (
    bbdown_commands,
    build_download_provider_chain,
    yt_dlp_download_command,
)
from integrations.providers.bilibili_comments import build_bilibili_headers
from integrations.providers.bilibili_support import build_bilibili_download_plan
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


def _with_subprocess_timeout(ctx: PipelineContext, timeout_seconds: int) -> PipelineContext:
    updated_settings = replace(
        ctx.settings,
        pipeline_subprocess_timeout_seconds=timeout_seconds,
    )
    if is_dataclass(ctx):
        return replace(ctx, settings=updated_settings)

    state = dict(getattr(ctx, "__dict__", {}))
    state["settings"] = updated_settings
    return type(ctx)(**state)


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
    metadata = dict(state.get("metadata") or {})
    run_ctx = ctx
    if platform == "bilibili":
        download_plan = build_bilibili_download_plan(metadata)
        download_timeout = int(download_plan.get("subprocess_timeout_seconds") or 0)
        if download_timeout > int(
            getattr(ctx.settings, "pipeline_subprocess_timeout_seconds", 180) or 180
        ):
            run_ctx = _with_subprocess_timeout(ctx, download_timeout)
    output_tmpl = str((ctx.download_dir / "media.%(ext)s").resolve())
    attempts: list[dict[str, Any]] = []

    for provider in providers:
        provider_result: CommandResult | None = None
        if provider == "yt-dlp":
            ytdlp_headers = (
                build_bilibili_headers(cookie=getattr(ctx.settings, "bilibili_cookie", None))
                if platform == "bilibili"
                else None
            )
            provider_result = await run_command(
                run_ctx,
                yt_dlp_download_command(source_url, output_tmpl, headers=ytdlp_headers),
            )
        elif provider == "bbdown":
            for cmd in bbdown_commands(source_url, ctx.download_dir):
                provider_result = await run_command(run_ctx, cmd)
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
    if not only_binary_missing:
        for candidate in attempts:
            if str(candidate.get("reason")) != "binary_not_found":
                last_attempt = candidate
                break
    return StepExecution(
        status=status,
        output={"mode": "text_only", "providers_tried": providers, "attempts": attempts},
        state_updates={"media_path": None, "download_mode": "text_only"},
        reason=str(last_attempt.get("reason") or "download_provider_chain_failed"),
        error=str(last_attempt.get("error") or "download_provider_chain_failed"),
        degraded=True,
    )
