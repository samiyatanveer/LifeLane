"""
conftest.py — Shared pytest fixtures for LifeLane engine tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure src/ is importable during test runs
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@pytest.fixture()
def mock_request_factory():
    """Return a factory for creating mock ambulance requests."""
    from lifelane_engine.ambulance.request import make_mock_request
    return make_mock_request


@pytest.fixture()
def route_planner():
    """Return a RoutePlanner pre-loaded with the mock 2x2 grid."""
    from lifelane_engine.ambulance.route_planner import RoutePlanner
    planner = RoutePlanner()
    planner.build_mock_grid()
    return planner


@pytest.fixture()
def approach_selector():
    """Return an ApproachSelector for junction J1."""
    from lifelane_engine.audio.approach_selector import ApproachSelector
    return ApproachSelector("J1")


@pytest.fixture()
def signal_controller():
    """Return a JunctionSignalController for junction J1."""
    from lifelane_engine.traffic.signal_controller import JunctionSignalController
    return JunctionSignalController("J1")

