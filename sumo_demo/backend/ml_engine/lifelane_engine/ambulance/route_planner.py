"""
route_planner.py — Dijkstra / A* route planning with mock graph.

Implements Dijkstra's algorithm over a simple graph of junctions and edges.
The cost function follows the specification:

    route_cost = road_travel_time + expected_intersection_delay + congestion_penalty

In Phase 1 (mock POC) the graph is a hard-coded 2×2 grid.
In Phase 3 it will be replaced by graph data derived from the SUMO network.

SAFETY: This module only plans routes; it does not control signals.
"""
from __future__ import annotations

import heapq
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graph primitives
# ---------------------------------------------------------------------------

@dataclass
class Edge:
    """A directed road edge connecting two junctions."""
    edge_id: str
    from_node: str
    to_node: str
    length_m: float            # metres
    speed_limit_ms: float      # m/s
    lanes: int = 1
    closed: bool = False       # Closed/prohibited roads are unavailable

    @property
    def free_flow_time(self) -> float:
        """Free-flow travel time in seconds."""
        if self.speed_limit_ms <= 0:
            return float("inf")
        return self.length_m / self.speed_limit_ms


@dataclass(order=True)
class _PQItem:
    """Priority-queue item for Dijkstra."""
    cost: float
    node: str = field(compare=False)
    path_edges: List[str] = field(compare=False, default_factory=list)
    path_nodes: List[str] = field(compare=False, default_factory=list)


# ---------------------------------------------------------------------------
# Hospital directory
# ---------------------------------------------------------------------------

@dataclass
class Hospital:
    """Mock hospital entry."""
    hospital_id: str
    name: str
    node: str          # Junction/node ID nearest to the hospital
    capabilities: List[str]
    available: bool = True


MOCK_HOSPITALS: Dict[str, Hospital] = {
    "H1": Hospital(
        hospital_id="H1",
        name="Central Simulation Hospital",
        node="J4",
        capabilities=["trauma", "cardiac"],
        available=True,
    ),
    "H2": Hospital(
        hospital_id="H2",
        name="North Simulation Clinic",
        node="J2",
        capabilities=["minor_trauma"],
        available=True,
    ),
}


# ---------------------------------------------------------------------------
# Route planner
# ---------------------------------------------------------------------------

class RoutePlanner:
    """Dijkstra-based route planner over a junction graph.

    Edges can carry congestion and intersection-delay estimates.
    Closed edges are excluded.

    Usage::

        planner = RoutePlanner()
        planner.build_mock_grid()          # Phase 1 mock network
        route = planner.find_route("J1", "J4")
    """

    def __init__(self) -> None:
        self._edges: List[Edge] = []
        self._adjacency: Dict[str, List[Edge]] = {}   # node → outgoing edges

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def add_edge(self, edge: Edge) -> None:
        """Register one directed edge."""
        self._edges.append(edge)
        self._adjacency.setdefault(edge.from_node, []).append(edge)

    def build_mock_grid(self) -> None:
        """Populate a 2×2 mock grid (J1–J4) with two ambulance routes.

        Layout:
            J1 — J2
            |      |
            J3 — J4 → Hospital

        Ambulance routes:
            Route A: J1 → J2 → J4
            Route B: J1 → J3 → J4
        """
        mock_edges = [
            # Route A
            Edge("e_J1_J2", "J1", "J2", length_m=300, speed_limit_ms=13.9),
            Edge("e_J2_J4", "J2", "J4", length_m=300, speed_limit_ms=13.9),
            # Route B
            Edge("e_J1_J3", "J1", "J3", length_m=350, speed_limit_ms=13.9),
            Edge("e_J3_J4", "J3", "J4", length_m=350, speed_limit_ms=13.9),
            # Cross links (ordinary traffic)
            Edge("e_J2_J1", "J2", "J1", length_m=300, speed_limit_ms=13.9),
            Edge("e_J4_J2", "J4", "J2", length_m=300, speed_limit_ms=13.9),
            Edge("e_J3_J1", "J3", "J1", length_m=350, speed_limit_ms=13.9),
            Edge("e_J4_J3", "J4", "J3", length_m=350, speed_limit_ms=13.9),
            # Hospital stub
            Edge("e_J4_H1", "J4", "H1", length_m=50, speed_limit_ms=8.3),
        ]
        for edge in mock_edges:
            self.add_edge(edge)
        logger.info("[route_planner] Built mock 2x2 grid with %d edges", len(mock_edges))

    # ------------------------------------------------------------------
    # Cost model
    # ------------------------------------------------------------------

    def _edge_cost(
        self,
        edge: Edge,
        intersection_delay: float = 10.0,
        congestion_factor: float = 1.0,
    ) -> float:
        """Compute the cost of traversing an edge.

        route_cost = road_travel_time + expected_intersection_delay + congestion_penalty
        """
        if edge.closed:
            return float("inf")
        travel_time = edge.free_flow_time * congestion_factor
        congestion_penalty = travel_time * max(0.0, congestion_factor - 1.0)
        return travel_time + intersection_delay + congestion_penalty

    # ------------------------------------------------------------------
    # Dijkstra
    # ------------------------------------------------------------------

    def find_route(
        self,
        origin: str,
        destination: str,
        intersection_delays: Optional[Dict[str, float]] = None,
        congestion_factors: Optional[Dict[str, float]] = None,
    ) -> Optional[Tuple[List[str], List[str], float]]:
        """Find the lowest-cost route from origin to destination.

        Args:
            origin:              Starting junction/node ID.
            destination:         Target junction/node ID.
            intersection_delays: Optional per-node delay overrides (seconds).
            congestion_factors:  Optional per-edge congestion multiplier.

        Returns:
            Tuple of (edge_ids, node_ids, total_cost) for the best route,
            or None if no path exists.
        """
        if intersection_delays is None:
            intersection_delays = {}
        if congestion_factors is None:
            congestion_factors = {}

        dist: Dict[str, float] = {origin: 0.0}
        pq: list[_PQItem] = [_PQItem(0.0, origin, [], [origin])]

        while pq:
            item = heapq.heappop(pq)
            current_cost, current_node = item.cost, item.node
            path_edges, path_nodes = item.path_edges, item.path_nodes

            if current_node == destination:
                logger.info(
                    "[route_planner] Found route %s → %s: edges=%s cost=%.1fs",
                    origin, destination, path_edges, current_cost,
                )
                return path_edges, path_nodes, current_cost

            if current_cost > dist.get(current_node, float("inf")):
                continue  # Stale entry

            for edge in self._adjacency.get(current_node, []):
                delay = intersection_delays.get(edge.to_node, 10.0)
                cfactor = congestion_factors.get(edge.edge_id, 1.0)
                ecost = self._edge_cost(edge, intersection_delay=delay, congestion_factor=cfactor)
                new_cost = current_cost + ecost

                if new_cost < dist.get(edge.to_node, float("inf")):
                    dist[edge.to_node] = new_cost
                    heapq.heappush(
                        pq,
                        _PQItem(
                            new_cost,
                            edge.to_node,
                            path_edges + [edge.edge_id],
                            path_nodes + [edge.to_node],
                        ),
                    )

        logger.warning(
            "[route_planner] No route found from %s to %s", origin, destination
        )
        return None

    def get_hospital(self, hospital_id: str) -> Optional[Hospital]:
        """Look up a hospital from the mock directory."""
        h = MOCK_HOSPITALS.get(hospital_id)
        if h is None:
            logger.warning("[route_planner] Unknown hospital_id: %s", hospital_id)
        return h

    def list_hospitals(self) -> List[Hospital]:
        """Return all hospitals in the mock directory."""
        return list(MOCK_HOSPITALS.values())

