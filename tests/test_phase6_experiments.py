"""
test_phase6_experiments.py — Phase 6 integration tests.

Verifies that experiments run end-to-end, metrics are exported,
and safety violations stay at zero in mock simulation.
"""
import os
import pytest
from lifelane_engine.simulation.mock_sumo import MockSumoRunner
from lifelane_engine.simulation.scenario import ScenarioConfig, ScenarioRunner
from lifelane_engine.simulation.metrics import ExperimentMetrics


class TestExperimentMetrics:
    def test_namedtuple_fields(self):
        m = ExperimentMetrics(
            scenario_id="t1",
            strategy="baseline",
            demand_level="light",
            seed=1,
            ambulance_travel_time_s=65.0,
            average_queue_length=1.2,
            safety_violations=0,
            simulation_duration_s=300.0,
        )
        assert m.scenario_id == "t1"
        assert m.safety_violations == 0


class TestExperimentRunner:
    def _run_scenario(self, strategy, demand, seed, route="r_amb_A"):
        config = ScenarioConfig(
            scenario_id=f"{strategy}_{demand}_{seed}",
            strategy=strategy,
            demand_level=demand,
            seed=seed,
            ambulance_route=route,
            ambulance_depart=0.0,
            duration_s=200.0,
            step_length_s=1.0,
        )
        runner = MockSumoRunner(step_length_s=1.0, seed=seed)
        runner.connect()
        metrics = ScenarioRunner(config, runner).run()
        runner.stop()
        return metrics

    def test_baseline_runs(self):
        m = self._run_scenario("baseline", "light", 1)
        assert m.strategy == "baseline"
        assert m.ambulance_travel_time_s > 0

    def test_naive_eta_runs(self):
        m = self._run_scenario("naive_eta", "medium", 2)
        assert m.strategy == "naive_eta"

    def test_fixed_formula_runs(self):
        m = self._run_scenario("fixed_formula", "heavy", 3)
        assert m.strategy == "fixed_formula"

    def test_no_safety_violations_in_mock(self):
        for seed in [1, 2, 3]:
            m = self._run_scenario("naive_eta", "light", seed)
            assert m.safety_violations == 0, f"seed={seed} had violations"

    def test_route_b_runs(self):
        m = self._run_scenario("naive_eta", "light", 1, route="r_amb_B")
        assert m.ambulance_travel_time_s > 0

    def test_heavy_demand_runs(self):
        m = self._run_scenario("baseline", "heavy", 5)
        assert m.demand_level == "heavy"

    def test_multiple_seeds_all_complete(self):
        for seed in [1, 2, 3, 4, 5]:
            m = self._run_scenario("naive_eta", "medium", seed)
            assert m.ambulance_travel_time_s > 0, f"seed={seed} gave nan travel time"


class TestRunExperimentScript:
    def test_run_subset_experiments(self, tmp_path):
        """Run a minimal set of experiments and verify CSV output."""
        import sys
        import os
        src = os.path.join(os.path.dirname(__file__), "..", "scripts")
        sys.path.insert(0, os.path.abspath(src))
        from run_experiment import run_all_experiments
        out_csv = str(tmp_path / "results.csv")
        results = run_all_experiments(
            strategies=["baseline", "naive_eta"],
            demand_levels=["light"],
            seeds=[1, 2],
            output_csv=out_csv,
        )
        assert len(results) == 4  # 2 strategies * 1 demand * 2 seeds
        assert os.path.exists(out_csv)
        for m in results:
            assert m.safety_violations == 0

    def test_learned_eta_strategy_in_subset(self, tmp_path):
        """learned_eta strategy trains and runs without error."""
        import sys
        import os
        src = os.path.join(os.path.dirname(__file__), "..", "scripts")
        sys.path.insert(0, os.path.abspath(src))
        from run_experiment import run_all_experiments
        out_csv = str(tmp_path / "results_eta.csv")
        results = run_all_experiments(
            strategies=["learned_eta"],
            demand_levels=["light"],
            seeds=[1],
            output_csv=out_csv,
        )
        assert len(results) == 1
        assert results[0].strategy == "learned_eta"


class TestEvaluateModelsScript:
    def test_siren_evaluation_runs(self):
        import sys
        import os
        src = os.path.join(os.path.dirname(__file__), "..", "scripts")
        sys.path.insert(0, os.path.abspath(src))
        from evaluate_models import evaluate_siren_classifier
        result = evaluate_siren_classifier()
        assert "test" in result
        assert result["test"]["f1"] >= 0.0

    def test_eta_evaluation_runs(self):
        import sys
        import os
        src = os.path.join(os.path.dirname(__file__), "..", "scripts")
        sys.path.insert(0, os.path.abspath(src))
        from evaluate_models import evaluate_eta_model
        result = evaluate_eta_model()
        assert "test" in result
        assert result["test"]["mae"] >= 0.0
        assert "baseline_naive_mae" in result["test"]

