"""
test_mock_poc.py — Smoke test: run the complete mock POC and verify exit code 0.

This is the Phase 1 acceptance gate test.
It runs without any dataset, SUMO, or trained models.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure src/ is importable
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def test_mock_poc_exits_zero():
    """run_mock_poc() must complete all scenarios and return 0."""
    from lifelane_engine.poc.mock_poc import run_mock_poc
    exit_code = run_mock_poc()
    assert exit_code == 0, "Mock POC returned non-zero — one or more scenarios failed"


def test_cli_run_poc_exits_zero():
    """python -m lifelane_engine.main --mode run-poc must return exit code 0."""
    from lifelane_engine.main import main
    exit_code = main(["--mode", "run-poc"])
    assert exit_code == 0


def test_cli_train_audio_exits_zero():
    """train-audio mode (implemented in Phase 4) must return exit code 0.

    Previously this was a stub returning 1. Phase 4 fully implemented it.
    All six CLI modes are now implemented and must return 0 on success.
    """
    from lifelane_engine.main import main
    exit_code = main(["--mode", "train-audio"])
    assert exit_code == 0, "train-audio mode failed — expected exit code 0"


def test_cli_invalid_mode_raises():
    """An unrecognised --mode value must be rejected by argparse (SystemExit 2)."""
    import pytest
    from lifelane_engine.main import main
    with pytest.raises(SystemExit) as exc_info:
        main(["--mode", "not-a-real-mode"])
    assert exc_info.value.code == 2, "argparse must exit with code 2 for invalid choices"

