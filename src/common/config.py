"""Load YAML config files and ``.env`` settings.

Config is data, not code: models and thresholds live in ``config/*.yaml`` and
secrets in ``.env`` (never committed). This module only reads them.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

# Project root is two levels up from this file: src/common/config.py -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


def load_yaml(name: str) -> dict:
    """Load ``config/<name>.yaml`` (``.yaml`` optional) as a dict."""
    filename = name if name.endswith((".yaml", ".yml")) else f"{name}.yaml"
    path = CONFIG_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"expected a mapping at top level of {path}")
    return data


class Settings(BaseModel):
    """Environment settings sourced from ``.env`` / process environment."""

    max_spend_usd: float = 1.0
    data_dir: str = "./data"
    hosted_api_key: str = ""
    meta_model: str = "llama3.1:8b"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Read ``.env`` (if present) and the process environment into Settings."""
    load_dotenv(REPO_ROOT / ".env")
    return Settings(
        max_spend_usd=float(os.getenv("MAX_SPEND_USD", "1.0")),
        data_dir=os.getenv("DATA_DIR", "./data"),
        hosted_api_key=os.getenv("HOSTED_API_KEY", ""),
        meta_model=os.getenv("META_MODEL", "llama3.1:8b"),
    )
