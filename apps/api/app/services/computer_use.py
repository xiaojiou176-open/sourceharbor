from __future__ import annotations

import base64
import concurrent.futures
import os
from dataclasses import dataclass, field
from typing import Any

from integrations.providers.gemini import build_gemini_client, load_gemini_sdk

from ..config import Settings

_DEFAULT_MODEL_TIMEOUT_SECONDS = 12.0
_DEFAULT_MODEL_MAX_RETRIES = 1


@dataclass(frozen=True)
class ComputerUseSafetyConfig:
    confirm_before_execute: bool = True
    blocked_actions: list[str] = field(default_factory=list)
    max_actions: int = 8


class ComputerUseService:
    def __init__(self) -> None:
        settings = Settings.from_env()
        self._api_key = (settings.gemini_api_key or "").strip()
        self._model = (
            settings.gemini_computer_use_model or "gemini-2.5-computer-use-preview-10-2025"
        ).strip()
        self._thinking_level = (settings.gemini_thinking_level or "high").strip().upper()

    def run(
        self,
        *,
        instruction: str,
        screenshot_base64: str,
        safety: ComputerUseSafetyConfig,
    ) -> dict[str, Any]:
        normalized_instruction = instruction.strip()
        if not normalized_instruction:
            raise ValueError("instruction must not be empty")
        screenshot_bytes = self._decode_base64_image(screenshot_base64)
        if not self._api_key:
            raise ValueError("gemini_api_key_missing")

        try:
            sdk = load_gemini_sdk()
            genai_types = sdk.genai_types
        except Exception as exc:
            raise ValueError(f"gemini_sdk_unavailable:{exc}") from exc

        try:
            client = build_gemini_client(api_key=self._api_key)
            timeout_seconds = self._read_float_env(
                "COMPUTER_USE_MODEL_TIMEOUT_SECONDS",
                default=_DEFAULT_MODEL_TIMEOUT_SECONDS,
                min_value=1.0,
                max_value=120.0,
            )
            max_retries = self._read_int_env(
                "COMPUTER_USE_MODEL_MAX_RETRIES",
                default=_DEFAULT_MODEL_MAX_RETRIES,
                min_value=0,
                max_value=3,
            )
            config_kwargs: dict[str, Any] = {
                "tools": [genai_types.Tool(computer_use=genai_types.ComputerUse())]
            }
            if "computer-use" not in self._model:
                config_kwargs["thinking_config"] = genai_types.ThinkingConfig(
                    thinking_level=self._thinking_level,
                )
            response = self._generate_with_timeout_and_retry(
                client=client,
                model=self._model,
                contents=[
                    normalized_instruction,
                    genai_types.Part.from_bytes(
                        data=screenshot_bytes,
                        mime_type="image/png",
                    ),
                ],
                config=genai_types.GenerateContentConfig(**config_kwargs),
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
        except Exception as exc:
            raise ValueError(f"computer_use_provider_error:{exc}") from exc

        actions = self._extract_actions(response, max_actions=safety.max_actions)
        blocked_actions = self._detect_blocked_actions(
            actions=actions, blocked_keywords=safety.blocked_actions
        )
        require_confirmation = bool(blocked_actions) or safety.confirm_before_execute

        final_text = str(getattr(response, "text", "") or "").strip()
        if not final_text:
            final_text = self._build_final_text(
                total_actions=len(actions),
                require_confirmation=require_confirmation,
                blocked_actions=blocked_actions,
            )

        return {
            "actions": actions,
            "require_confirmation": require_confirmation,
            "blocked_actions": blocked_actions,
            "final_text": final_text,
            "thought_metadata": {
                "provider": "gemini",
                "model": self._model,
                "planner": "gemini_computer_use",
                "instruction_chars": len(normalized_instruction),
                "screenshot_bytes": len(screenshot_bytes),
                "max_actions": safety.max_actions,
                "confirm_before_execute": safety.confirm_before_execute,
                "blocked_keyword_count": len(safety.blocked_actions),
                "request_id": str(
                    getattr(response, "response_id", None) or getattr(response, "id", "") or ""
                ),
                "finish_reason": self._extract_finish_reason(response),
                "action_count": len(actions),
            },
        }

    def _generate_with_timeout_and_retry(
        self,
        *,
        client: Any,
        model: str,
        contents: list[Any],
        config: Any,
        timeout_seconds: float,
        max_retries: int,
    ) -> Any:
        attempts = max_retries + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        client.models.generate_content,
                        model=model,
                        contents=contents,
                        config=config,
                    )
                    return future.result(timeout=timeout_seconds)
            except concurrent.futures.TimeoutError:
                last_error = TimeoutError(
                    f"computer_use model timeout after {timeout_seconds:.1f}s (attempt {attempt}/{attempts})"
                )
            except Exception as exc:
                last_error = exc
            if attempt >= attempts:
                break
        raise RuntimeError(
            str(last_error) if last_error is not None else "computer_use model call failed"
        )

    def _read_float_env(
        self, name: str, *, default: float, min_value: float, max_value: float
    ) -> float:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = float(raw.strip())
        except (TypeError, ValueError):
            return default
        return min(max(value, min_value), max_value)

    def _read_int_env(self, name: str, *, default: int, min_value: int, max_value: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = int(raw.strip())
        except (TypeError, ValueError):
            return default
        return min(max(value, min_value), max_value)

    def _decode_base64_image(self, payload: str) -> bytes:
        raw = payload.strip()
        if not raw:
            raise ValueError("screenshot must not be empty")
        if raw.startswith("data:") and "," in raw:
            raw = raw.split(",", 1)[1]
        try:
            return base64.b64decode(raw, validate=True)
        except Exception as exc:
            raise ValueError("screenshot must be valid base64") from exc

    def _extract_finish_reason(self, response: Any) -> str | None:
        candidates = getattr(response, "candidates", None)
        if not isinstance(candidates, list) or not candidates:
            return None
        first = candidates[0]
        raw = getattr(first, "finish_reason", None)
        if raw is None and isinstance(first, dict):
            raw = first.get("finish_reason")
        if raw is None:
            return None
        text = str(raw).strip()
        return text or None

    def _extract_actions(self, response: Any, *, max_actions: int) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        candidates = getattr(response, "candidates", None)
        if isinstance(candidates, list):
            for candidate in candidates:
                content = getattr(candidate, "content", None)
                parts = getattr(content, "parts", None)
                if not isinstance(parts, list):
                    continue
                for part in parts:
                    function_call = getattr(part, "function_call", None)
                    if function_call is None and isinstance(part, dict):
                        function_call = part.get("function_call")
                    if function_call is None:
                        continue

                    if isinstance(function_call, dict):
                        name = str(function_call.get("name") or "").strip()
                        args = function_call.get("args")
                    else:
                        name = str(getattr(function_call, "name", "") or "").strip()
                        args = getattr(function_call, "args", None)
                    if not isinstance(args, dict):
                        args = {}
                    if not name:
                        continue

                    action = (
                        str(args.get("action") or args.get("operation") or name).strip() or name
                    )
                    target = self._to_str_or_none(
                        args.get("target") or args.get("selector") or args.get("url")
                    )
                    input_text = self._to_str_or_none(args.get("text") or args.get("input_text"))
                    reasoning = self._to_str_or_none(args.get("reason") or args.get("reasoning"))
                    actions.append(
                        {
                            "step": len(actions) + 1,
                            "action": action,
                            "target": target,
                            "input_text": input_text,
                            "reasoning": reasoning,
                        }
                    )
                    if len(actions) >= max(1, max_actions):
                        return actions

        if not actions:
            actions.append(
                {
                    "step": 1,
                    "action": "observe",
                    "target": None,
                    "input_text": None,
                    "reasoning": "no function_call returned by model",
                }
            )
        return actions

    def _detect_blocked_actions(
        self,
        *,
        actions: list[dict[str, Any]],
        blocked_keywords: list[str],
    ) -> list[str]:
        normalized_keywords = [
            item.strip().lower()
            for item in blocked_keywords
            if isinstance(item, str) and item.strip()
        ]
        if not normalized_keywords:
            return []

        blocked_hits: list[str] = []
        for action in actions:
            haystack = " ".join(
                str(action.get(key) or "")
                for key in ("action", "target", "input_text", "reasoning")
            ).lower()
            for keyword in normalized_keywords:
                if keyword in haystack and keyword not in blocked_hits:
                    blocked_hits.append(keyword)
        return blocked_hits

    def _build_final_text(
        self, *, total_actions: int, require_confirmation: bool, blocked_actions: list[str]
    ) -> str:
        if blocked_actions:
            return (
                f"Planned {total_actions} action(s). "
                f"Confirmation is required because blocked keywords were detected: {', '.join(blocked_actions)}."
            )
        if require_confirmation:
            return f"Planned {total_actions} action(s). Confirmation is required by safety policy."
        return f"Planned {total_actions} action(s). Ready for execution."

    def _to_str_or_none(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
