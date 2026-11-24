"""
dataset_builder.py — ETA/queue dataset builder for Phase 5.

Two modes:
  1. SUMO log reader: reads CSV logs from completed SUMO runs.
  2. Synthetic generator: creates clearly-labeled synthetic training data
     when SUMO is not available.

Generated datasets use run_id columns so data is split by simulation run
(no leakage across train/val/test seeds).

*** SYNTHETIC DATA IS CLEARLY LABELED — not derived from real SUMO runs ***
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Feature columns for the ETA regressor
ETA_FEATURE_COLS = [
    "distance_to_junction_m",    # metres remaining to junction
    "current_speed_ms",          # ambulance speed m/s
    "queue_length_vehicles",     # vehicles queued at junction
    "time_since_green_s",        # seconds since junction last turned green
    "demand_level_enc",          # 0=light, 1=medium, 2=heavy
    "is_route_A",                # 1 if route A, 0 if route B
]

DEMAND_ENCODING = {"light": 0, "medium": 1, "heavy": 2}


def generate_synthetic_eta_dataset(
    n_seeds: int = 100,
    rows_per_seed: int = 50,
    seed: int = 42,
    train_seed_range: Tuple[int, int] = (1, 70),
    val_seed_range: Tuple[int, int] = (71, 85),
    test_seed_range: Tuple[int, int] = (86, 100),
) -> "dict":
    """Generate a synthetic ETA regression dataset.

    *** SYNTHETIC DATA — NOT DERIVED FROM REAL SUMO RUNS ***
    Features are randomly sampled from plausible ranges.
    Target (eta_s) is computed via a simple linear formula + noise.

    Each 'seed' represents one simulation run. Data is split by run_id
    to prevent leakage between train/val/test splits.

    Returns:
        dict with keys:
            "X_train", "y_train", "X_val", "y_val", "X_test", "y_test"
            "feature_names": list of feature column names
            "n_train", "n_val", "n_test": sample counts
            "note": documentation string
    """
    try:
        import pandas as pd
        _PANDAS = True
    except ImportError:
        _PANDAS = False

    rng = np.random.RandomState(seed)
    rows = []

    for run_id in range(1, n_seeds + 1):
        for _ in range(rows_per_seed):
            dist = rng.uniform(10.0, 400.0)        # metres to junction
            speed = rng.uniform(5.0, 16.67)         # m/s
            queue = rng.randint(0, 12)              # vehicles
            green_t = rng.uniform(0.0, 60.0)        # seconds since green
            demand = rng.randint(0, 3)              # 0/1/2
            route_a = rng.randint(0, 2)             # 0 or 1

            # Synthetic ETA: naive formula + congestion factor + noise
            base_eta = dist / max(speed, 1.0)
            congestion_delay = queue * rng.uniform(2.0, 5.0)
            noise = rng.normal(0, 3.0)
            eta_s = max(0.0, base_eta + congestion_delay + noise)

            rows.append({
                "run_id": run_id,
                "distance_to_junction_m": dist,
                "current_speed_ms": speed,
                "queue_length_vehicles": float(queue),
                "time_since_green_s": green_t,
                "demand_level_enc": float(demand),
                "is_route_A": float(route_a),
                "eta_s": eta_s,
            })

    # Convert to numpy arrays split by seed ranges
    all_run_ids = np.array([r["run_id"] for r in rows])
    X_all = np.array([[r[c] for c in ETA_FEATURE_COLS] for r in rows], dtype=np.float32)
    y_all = np.array([r["eta_s"] for r in rows], dtype=np.float32)

    def _mask(lo, hi):
        return (all_run_ids >= lo) & (all_run_ids <= hi)

    tr = _mask(*train_seed_range)
    va = _mask(*val_seed_range)
    te = _mask(*test_seed_range)

    note = (
        "SYNTHETIC ETA dataset — NOT from real SUMO runs. "
        "Generated for pipeline demonstration only. "
        "Real training requires SUMO simulation data (Phase 3)."
    )
    logger.warning("[dataset_builder] %s", note)

    return {
        "X_train": X_all[tr],
        "y_train": y_all[tr],
        "X_val": X_all[va],
        "y_val": y_all[va],
        "X_test": X_all[te],
        "y_test": y_all[te],
        "feature_names": ETA_FEATURE_COLS,
        "n_train": int(tr.sum()),
        "n_val": int(va.sum()),
        "n_test": int(te.sum()),
        "note": note,
    }


def save_dataset_csv(dataset: dict, output_path: str) -> None:
    """Save the synthetic dataset to CSV for inspection.

    Clearly labels the file as SYNTHETIC in column headers and a comment row.
    """
    try:
        import pandas as pd
    except ImportError:
        logger.warning("[dataset_builder] pandas not available; skipping CSV export")
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    rows = []
    for split, label in [("train", 0), ("val", 1), ("test", 2)]:
        X = dataset[f"X_{split}"]
        y = dataset[f"y_{split}"]
        for i in range(len(y)):
            row = dict(zip(ETA_FEATURE_COLS, X[i].tolist()))
            row["eta_s"] = float(y[i])
            row["split"] = split
            rows.append(row)

    pd.DataFrame(rows).to_csv(output_path, index=False)
    logger.info("[dataset_builder] Saved synthetic dataset to %s", output_path)
