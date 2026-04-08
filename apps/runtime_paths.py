from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_runtime_root() -> Path:
    explicit = os.getenv("SOURCE_HARBOR_RUNTIME_ROOT", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve(strict=False)
    return Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def get_runtime_cache_root() -> Path:
    explicit = os.getenv("SOURCE_HARBOR_CACHE_ROOT", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve(strict=False)
    return get_runtime_root() / ".runtime-cache"


@lru_cache(maxsize=1)
def get_runtime_config_root() -> Path:
    return get_runtime_root() / "config"


@lru_cache(maxsize=1)
def get_runtime_scripts_root() -> Path:
    return get_runtime_root() / "scripts"
