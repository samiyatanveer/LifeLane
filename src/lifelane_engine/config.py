"""
config.py — Configuration loader for LifeLane.

Loads config/settings.yaml relative to the project root and exposes
a singleton Settings object. All modules should import settings from here
rather than reading the YAML file directly.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Project root is two levels above this file:  src/lifelane_engine/config.py
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _project_root() -> Path:
    """Return the absolute project root directory."""
    return _PROJECT_ROOT


@lru_cache(maxsize=1)
def load_settings(settings_path: str | None = None) -> dict[str, Any]:
    """Load and return the settings YAML as a plain dict.

    Args:
        settings_path: Optional override path to the YAML file.
                       Defaults to <project_root>/config/settings.yaml.

    Returns:
        Parsed settings dictionary.

    Raises:
        FileNotFoundError: If the settings file does not exist.
        yaml.YAMLError: If the file cannot be parsed.
    """
    if settings_path is None:
        path = _project_root() / "config" / "settings.yaml"
    else:
        path = Path(settings_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Settings file not found: {path}\n"
            f"Expected at: {_project_root() / 'config' / 'settings.yaml'}"
        )

    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if data is None:
        raise ValueError(f"Settings file is empty: {path}")

    logger.debug("Loaded settings from %s", path)
    return data  # type: ignore[return-value]


def get(section: str, key: str | None = None, default: Any = None) -> Any:
    """Convenience accessor for a top-level section or nested key.

    Examples:
        get("audio")                        → full audio sub-dict
        get("audio", "sample_rate_hz")      → 16000
        get("audio", "missing", default=0)  → 0
    """
    settings = load_settings()
    section_data = settings.get(section, {})
    if key is None:
        return section_data
    return section_data.get(key, default)


def project_root() -> Path:
    """Return the project root Path for callers that need absolute paths."""
    return _project_root()

