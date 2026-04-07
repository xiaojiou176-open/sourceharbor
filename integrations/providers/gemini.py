from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode


@dataclass(frozen=True)
class GeminiSdkBundle:
    genai: Any
    genai_types: Any


def build_models_probe_url(api_key: str) -> str:
    return "https://generativelanguage.googleapis.com/v1beta/models?" + urlencode({"key": api_key})


def load_gemini_sdk(*, import_module: Any = importlib.import_module) -> GeminiSdkBundle:
    genai = import_module("google.genai")
    try:
        genai_types = import_module("google.genai.types")
    except ModuleNotFoundError:
        genai_types = getattr(genai, "types", None)
        if genai_types is None:
            raise
    return GeminiSdkBundle(genai=genai, genai_types=genai_types)


def build_gemini_client(*, api_key: str, import_module: Any = importlib.import_module) -> Any:
    sdk = load_gemini_sdk(import_module=import_module)
    return sdk.genai.Client(api_key=api_key)
