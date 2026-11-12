"""
test_route_planner.py — Unit tests for RoutePlanner and mock hospital directory.
"""
from __future__ import annotations

import pytest
from lifelane_engine.ambulance.route_planner import RoutePlanner, MOCK_HOSPITALS


class TestRoutePlanner:
    def test_mock_grid_builds_without_error(self):
        planner = RoutePlanner()
        planner.build_mock_grid()  # should not raise

    def test_route_exists_J1_to_H1(self):
        planner = RoutePlanner()
        planner.build_mock_grid()
        result = planner.find_route("J1", "H1")
        assert result is not None
        edges, nodes, cost = result
        assert len(edges) > 0
        assert "J1" in nodes
        assert "H1" in nodes
        assert cost > 0

    def test_route_uses_only_open_edges(self):
        planner = RoutePlanner()
        planner.build_mock_grid()
        result = planner.find_route("J1", "J4")
        assert result is not None
        # Close all edges
        for edge in planner._edges:
            edge.closed = True
        result_closed = planner.find_route("J1", "J4")
        assert result_closed is None

    def test_no_route_for_unknown_nodes(self):
        planner = RoutePlanner()
        planner.build_mock_grid()
        result = planner.find_route("J1", "NONEXISTENT")
        assert result is None

    def test_two_routes_exist_to_J4(self):
        """Both J1→J2→J4 and J1→J3→J4 must be reachable."""
        planner = RoutePlanner()
        planner.build_mock_grid()
        # Close J2 path — should still route via J3
        for edge in planner._edges:
            if "J2" in (edge.from_node, edge.to_node):
                edge.closed = True
        result = planner.find_route("J1", "J4")
        assert result is not None, "Route via J3 should still exist"
        _, nodes, _ = result
        assert "J3" in nodes

    def test_cost_is_positive(self):
        planner = RoutePlanner()
        planner.build_mock_grid()
        result = planner.find_route("J1", "H1")
        assert result is not None
        _, _, cost = result
        assert cost > 0

    def test_hospital_lookup_valid(self):
        planner = RoutePlanner()
        planner.build_mock_grid()
        h = planner.get_hospital("H1")
        assert h is not None
        assert h.hospital_id == "H1"
        assert h.available

    def test_hospital_lookup_unknown(self):
        planner = RoutePlanner()
        planner.build_mock_grid()
        h = planner.get_hospital("H_NONEXISTENT")
        assert h is None

    def test_list_hospitals_returns_all(self):
        planner = RoutePlanner()
        hospitals = planner.list_hospitals()
        assert len(hospitals) == len(MOCK_HOSPITALS)

