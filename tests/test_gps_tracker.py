"""
test_gps_tracker.py — Unit tests for GpsTracker, GpsUpdate, and deviation detection.
"""
import pytest
from lifelane_engine.dispatch.gps_tracker import (
    GpsSource,
    GpsTracker,
    GpsUpdate,
    NODE_POSITIONS,
)

T0 = 50_000.0


def _make_update(
    ambulance_id="AMB-T",
    lat=33.720,
    lon=73.040,
    speed_ms=10.0,
    heading_deg=90.0,
    timestamp=T0,
    source=GpsSource.DEVICE,
) -> GpsUpdate:
    return GpsUpdate(
        ambulance_id=ambulance_id,
        latitude=lat,
        longitude=lon,
        speed_ms=speed_ms,
        heading_deg=heading_deg,
        timestamp=timestamp,
        source=source,
    )


class TestGpsUpdate:
    def test_negative_speed_raises(self):
        with pytest.raises(ValueError):
            _make_update(speed_ms=-1.0)

    def test_heading_out_of_range_raises(self):
        with pytest.raises(ValueError):
            _make_update(heading_deg=360.0)

    def test_valid_update(self):
        u = _make_update(speed_ms=0.0, heading_deg=0.0)
        assert u.speed_ms == 0.0


class TestGpsTracker:
    def test_latest_returns_none_before_updates(self):
        t = GpsTracker("AMB-T")
        assert t.latest() is None

    def test_latest_after_update(self):
        t = GpsTracker("AMB-T")
        u = _make_update()
        t.update(u)
        assert t.latest() is u

    def test_history_length(self):
        t = GpsTracker("AMB-T", max_history=3)
        for i in range(5):
            t.update(_make_update(timestamp=T0 + i))
        assert len(t.history()) == 3

    def test_wrong_ambulance_raises(self):
        t = GpsTracker("AMB-T")
        with pytest.raises(ValueError):
            t.update(_make_update(ambulance_id="OTHER"))

    def test_clear(self):
        t = GpsTracker("AMB-T")
        t.update(_make_update())
        t.clear()
        assert t.latest() is None


class TestStaleness:
    def test_stale_before_any_update(self):
        t = GpsTracker("AMB-T", stale_threshold_s=10.0)
        assert t.is_stale(now=T0) is True

    def test_not_stale_immediately_after_update(self):
        t = GpsTracker("AMB-T", stale_threshold_s=10.0)
        t.update(_make_update(timestamp=T0))
        assert t.is_stale(now=T0 + 5) is False

    def test_stale_after_threshold(self):
        t = GpsTracker("AMB-T", stale_threshold_s=10.0)
        t.update(_make_update(timestamp=T0))
        assert t.is_stale(now=T0 + 11) is True


class TestDeviation:
    def test_no_deviation_when_on_route_node(self):
        # J1 is at (33.720, 73.040) exactly
        t = GpsTracker("AMB-T", deviation_corridor_m=30.0)
        lat, lon = NODE_POSITIONS["J1"]
        t.update(_make_update(lat=lat, lon=lon))
        assert t.check_deviation() is False

    def test_deviation_when_far_from_route(self):
        # Place ambulance far away from any mock node
        t = GpsTracker("AMB-T", deviation_corridor_m=30.0)
        t.update(_make_update(lat=34.0, lon=74.0))  # ~100 km away
        assert t.check_deviation() is True

    def test_no_deviation_with_no_gps(self):
        t = GpsTracker("AMB-T")
        assert t.check_deviation() is False

    def test_manual_source_accepted(self):
        t = GpsTracker("AMB-T")
        lat, lon = NODE_POSITIONS["J2"]
        t.update(_make_update(lat=lat, lon=lon, source=GpsSource.MANUAL))
        assert t.latest().source == GpsSource.MANUAL

