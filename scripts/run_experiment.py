"""
run_experiment.py — Phase 6 experiment runner comparing corridor strategies.

Compares four strategies across demand levels and random seeds:
  1. baseline:      No coordination; normal traffic signal cycle.
  2. fixed_formula: Queue clearance uses n_vehicles * 3.5s formula.
  3. naive_eta:     ETA predicted by distance/speed formula.
  4. learned_eta:   ETA predicted by trained XGBoost model.

All runs use MockSumoRunner (no SUMO installation required).
Results are written to reports/experiment_results.csv.

*** ALL RESULTS COME FROM MOCK SIMULATION — clearly labeled ***
"""
from __future__ import annotations

import csv
import logging
import os
import sys

# Ensure src is on path when run as a script
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.join(_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "src"))

from lifelane_engine.prediction.dataset_builder import generate_synthetic_eta_dataset
from lifelane_engine.prediction.eta_model import ETAModel, naive_eta
from lifelane_engine.simulation.mock_sumo import MockSumoRunner
from lifelane_engine.simulation.metrics import ExperimentMetrics
from lifelane_engine.simulation.scenario import ScenarioConfig, ScenarioRunner

logger = logging.getLogger(__name__)

STRATEGIES = ["baseline", "fixed_formula", "naive_eta", "learned_eta"]
DEMAND_LEVELS = ["light", "medium", "heavy"]
SEEDS = [1, 2, 3, 4, 5]

OUTPUT_DIR = os.path.join(_ROOT, "reports")
RESULTS_CSV = os.path.join(OUTPUT_DIR, "experiment_results.csv")

NOTE = (
    "ALL RESULTS ARE FROM MOCK SIMULATION (MockSumoRunner). "
    "No real SUMO or traffic data used. "
    "ETA model trained on SYNTHETIC dataset. "
    "Results are for pipeline validation only, not real-world performance."
)


def _train_eta_model() -> ETAModel:
    """Train ETA model on synthetic data for the 'learned_eta' strategy."""
    logger.info("[run_experiment] Training ETA model on synthetic dataset...")
    ds = generate_synthetic_eta_dataset(n_seeds=100, rows_per_seed=50, seed=42)
    model = ETAModel(n_estimators=100, max_depth=4)
    metrics = model.fit(ds["X_train"], ds["y_train"], ds["X_val"], ds["y_val"])
    logger.info("[run_experiment] ETA model metrics: %s", metrics)
    return model


def run_all_experiments(
    strategies=STRATEGIES,
    demand_levels=DEMAND_LEVELS,
    seeds=SEEDS,
    output_csv=RESULTS_CSV,
) -> list:
    """Run all experiment combinations and return list of ExperimentMetrics.

    Args:
        strategies:   List of strategy names.
        demand_levels: List of demand level strings.
        seeds:        List of integer random seeds.
        output_csv:   Path to write results CSV.

    Returns:
        List of ExperimentMetrics namedtuples.
    """
    # Pre-train the learned_eta model once
    eta_model = None
    if "learned_eta" in strategies:
        eta_model = _train_eta_model()

    results = []
    total = len(strategies) * len(demand_levels) * len(seeds)
    done = 0

    for strategy in strategies:
        for demand in demand_levels:
            for seed in seeds:
                scenario_id = f"{strategy}_{demand}_seed{seed}"
                config = ScenarioConfig(
                    scenario_id=scenario_id,
                    demand_level=demand,
                    seed=seed,
                    ambulance_route="r_amb_A" if seed % 2 == 1 else "r_amb_B",
                    ambulance_depart=30.0,
                    use_coordination=(strategy != "baseline"),
                    strategy=strategy,
                    duration_s=300.0,
                    step_length_s=1.0,
                )
                runner = MockSumoRunner(step_length_s=1.0, seed=seed)
                runner.connect()
                try:
                    scenario = ScenarioRunner(config, runner)
                    metrics = scenario.run()
                finally:
                    runner.stop()

                results.append(metrics)
                done += 1
                logger.info(
                    "[run_experiment] [%d/%d] %s: travel=%.1fs queue=%.2f violations=%d",
                    done, total, scenario_id,
                    metrics.ambulance_travel_time_s,
                    metrics.average_queue_length,
                    metrics.safety_violations,
                )

    # Write CSV
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "NOTE", NOTE
        ])
        writer.writerow(ExperimentMetrics._fields)
        for m in results:
            writer.writerow(list(m))

    logger.info(
        "[run_experiment] Wrote %d results to %s", len(results), output_csv
    )
    return results


def print_summary(results: list) -> None:
    """Print a compact comparison table to stdout."""
    from collections import defaultdict
    print("\n" + "=" * 70)
    print("  LifeLane Phase 6 — Experiment Summary")
    print("  *** MOCK SIMULATION RESULTS — NOT REAL PERFORMANCE ***")
    print("=" * 70)
    print(f"\n  {'Strategy':<20} {'Demand':<10} {'Avg Travel(s)':<16} {'Avg Queue':<12} {'Violations'}")
    print("  " + "-" * 66)

    by_strategy_demand = defaultdict(list)
    for m in results:
        by_strategy_demand[(m.strategy, m.demand_level)].append(m)

    for strategy in STRATEGIES:
        for demand in DEMAND_LEVELS:
            ms = by_strategy_demand.get((strategy, demand), [])
            if not ms:
                continue
            travels = [m.ambulance_travel_time_s for m in ms]
            queues = [m.average_queue_length for m in ms]
            viols = sum(m.safety_violations for m in ms)
            import math
            valid_travels = [t for t in travels if not math.isnan(t)]
            avg_travel = sum(valid_travels) / len(valid_travels) if valid_travels else float("nan")
            avg_queue = sum(queues) / len(queues)
            print(f"  {strategy:<20} {demand:<10} {avg_travel:<16.1f} {avg_queue:<12.2f} {viols}")

    print(f"\n  Note: {NOTE}\n")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    results = run_all_experiments()
    print_summary(results)

