"""
test_config.py — Unit tests for config loader.
"""
from __future__ import annotations

import pytest
from lifelane_engine import config


def test_load_settings_returns_dict():
    settings = config.load_settings()
    assert isinstance(settings, dict)
    assert len(settings) > 0


def test_get_audio_section():
    audio = config.get("audio")
    assert isinstance(audio, dict)
    assert audio.get("sample_rate_hz") == 16000


def test_get_nested_key():
    rate = config.get("audio", "sample_rate_hz")
    assert rate == 16000


def test_get_missing_key_returns_default():
    val = config.get("audio", "nonexistent_key", default="fallback")
    assert val == "fallback"


def test_get_missing_section_returns_empty():
    section = config.get("no_such_section")
    assert section == {}


def test_project_root_exists():
    root = config.project_root()
    assert root.exists()
    assert (root / "config" / "settings.yaml").exists()

