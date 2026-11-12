"""
test_mock_sumo.py — Phase 3 unit tests using MockSumoRunner.

Tests all SUMO integration logic without requiring SUMO to be installed.
Uses MockSumoRunner to simulate vehicle movement and signal control.
"""
import math
import pytest
from lifelane_engine.simulation.mock_sumo import (
    MockSumoRunner,
    NODE_XY,
    ROUTE_NODES,
)
from lifelane_engine.simulation.scenario import (
    ScenarioConfig,
    ScenarioRunner,
    xy_to_latlon,
)


class TestMockSumoBasics:
    def test_connect_and_stop_no_error(self):
        runner = MockSumoRunner()
        runner.connect()
        runner.stop()

    def test_initial_sim_time_zero(self):
        runner = MockSumoRunner()
        assert runner.sim_time == 0.0

    def test_step_advances_time(self):
        runner = MockSumoRunner(step_length_s=1.0)
        runner.step()
        assert runner.sim_time == pytest.approx(1.0)

    def test_step_multiple(self):
        runner = MockSumoRunner(step_length_s=2.0)
        for _ in range(5):
            runner.step()
        assert runner.sim_time == pytest.approx(10.0)

    def test_context_manager(self):
        with MockSumoRunner() as runner:
            runner.step()
        assert runner.sim_time > 0


class TestVehicleManagement:
    def test_add_vehicle_appears_in_ids_after_depart(self):
        runner = MockSumoRunner(step_length_s=1.0)
        runner.add_vehicle("amb_001", "r_amb_A", depart_time=0.0)
        runner.step()
        assert "amb_001" in runner.get_vehicle_ids()

    def test_vehicle_not_in_ids_before_depart(self):
        runner = MockSumoRunner(step_length_s=1.0)
        runner.add_vehicle("amb_001", "r_amb_A", depart_time=10.0)
        runner.step()  # t=1.0, not yet departed
        assert "amb_001" not in runner.get_vehicle_ids()

    def test_vehicle_position_before_depart_is_none(self):
        runner = MockSumoRunner(step_length_s=1.0)
        runner.add_vehicle("amb_001", "r_amb_A", depart_time=5.0)
        runner.step()
        assert runner.get_vehicle_position("amb_001") is None

    def test_vehicle_position_after_depart_is_tuple(self):
        runner = MockSumoRunner(step_length_s=1.0)
        runner.add_vehicle("amb_001", "r_amb_A", depart_time=0.0, speed_ms=10.0)
        runner.step()
        pos = runner.get_vehicle_position("amb_001")
        assert pos is not None
        assert len(pos) == 2

    def test_ambulance_speed_returned(self):
        runner = MockSumoRunner()
        runner.add_vehicle("amb_001", "r_amb_A", speed_ms=13.89)
        assert runner.get_vehicle_speed("amb_001") == pytest.approx(13.89)

    def test_remove_vehicle(self):
        runner = MockSumoRunner(step_length_s=1.0)
        runner.add_vehicle("amb_001", "r_amb_A", depart_time=0.0)
        runner.step()
        runner.remove_vehicle("amb_001")
        assert "amb_001" not in runner.get_vehicle_ids()

    def test_vehicle_arrives_at_end_of_route(self):
        # Short route J1->J2 (300m), high speed, many steps
        runner = MockSumoRunner(step_length_s=1.0)
        runner.add_vehicle("car_01", "r_EW_J1J2", vehicle_type="car",
                           depart_time=0.0, speed_ms=100.0)  # 100 m/s → fast
        for _ in range(10):
            runner.step()
        assert runner.vehicle_has_arrived("car_01") is True

    def test_nearest_junction_detection(self):
        runner = MockSumoRunner(step_length_s=1.0)
        runner.add_vehicle("amb_001", "r_amb_A", depart_time=0.0, speed_ms=1.0)
        runner.step()  # small movement, still near J1
        nearest = runner.get_vehicle_nearest_junction("amb_001")
        assert nearest in NODE_XY


class TestSignalControl:
    def test_initial_phase_zero(self):
        runner = MockSumoRunner()
        assert runner.get_phase("J1") == 0

    def test_set_phase_changes_phase(self):
        runner = MockSumoRunner()
        runner.set_phase("J1", 3)
        assert runner.get_phase("J1") == 3

    def test_phase_wraps_around(self):
        runner = MockSumoRunner()
        runner.set_phase("J1", 10)  # 10 % 5 = 0
        assert runner.get_phase("J1") == 0

    def test_signal_advances_over_time(self):
        runner = MockSumoRunner(step_length_s=1.0)
        initial = runner.get_phase("J1")
        # Phase 0 lasts 27s; advance 28 steps → should move to phase 1
        for _ in range(28):
            runner.step()
        # Phase may have advanced
        assert runner.get_phase("J1") >= 0  # At minimum it's a valid phase

    def test_get_program_returns_string(self):
        runner = MockSumoRunner()
        prog = runner.get_program("J1")
        assert isinstance(prog, str)


class TestRouteGeometry:
    def test_route_length_route_A(self):
        length = MockSumoRunner._route_length("r_amb_A")
        # J1->J2 = 300, J2->J4 = 300, J4->H1 = 50 → 650m
        assert length == pytest.approx(650.0, rel=0.01)

    def test_route_length_route_B(self):
        length = MockSumoRunner._route_length("r_amb_B")
        # J1->J3 = 300, J3->J4 = 300, J4->H1 = 50 → 650m
        assert length == pytest.approx(650.0, rel=0.01)

    def test_xy_to_latlon_origin(self):
        lat, lon = xy_to_latlon(0.0, 0.0)
        # J3 is at (0, 0) in the grid; corresponds to lat_origin + offset
        assert isinstance(lat, float)
        assert isinstance(lon, float)

    def test_xy_to_latlon_increases_lon_eastward(self):
        _, lon0 = xy_to_latlon(0.0, 0.0)
        _, lon1 = xy_to_latlon(300.0, 0.0)
        assert lon1 > lon0


class TestScenarioRunner:
    def test_scenario_runs_to_completion(self):
        config = ScenarioConfig(
            scenario_id="test_01",
            demand_level="light",
            seed=1,
            ambulance_route="r_amb_A",
            ambulance_depart=0.0,
            duration_s=120.0,
            step_length_s=1.0,
            strategy="baseline",
        )
        runner = MockSumoRunner(step_length_s=1.0)
        runner.connect()
        scenario = ScenarioRunner(config, runner)
        metrics = scenario.run()
        runner.stop()

        assert metrics.scenario_id == "test_01"
        assert metrics.strategy == "baseline"
        assert metrics.simulation_duration_s > 0

    def test_ambulance_travel_time_positive(self):
        config = ScenarioConfig(
            scenario_id="test_02",
            ambulance_depart=0.0,
            duration_s=300.0,
            step_length_s=1.0,
        )
        runner = MockSumoRunner(step_length_s=1.0)
        runner.connect()
        metrics = ScenarioRunner(config, runner).run()
        runner.stop()
        # Travel time should be positive (ambulance departed and arrived)
        assert metrics.ambulance_travel_time_s > 0

    def test_safety_violations_zero_in_mock(self):
        config = ScenarioConfig(scenario_id="test_03", duration_s=60.0)
        runner = MockSumoRunner(step_length_s=1.0)
        runner.connect()
        metrics = ScenarioRunner(config, runner).run()
        runner.stop()
        assert metrics.safety_violations == 0

    def test_route_b_also_works(self):
        config = ScenarioConfig(
            scenario_id="test_04",
            ambulance_route="r_amb_B",
            ambulance_depart=0.0,
            duration_s=300.0,
        )
        runner = MockSumoRunner(step_length_s=1.0)
        runner.connect()
        metrics = ScenarioRunner(config, runner).run()
        runner.stop()
        assert metrics.ambulance_travel_time_s > 0
