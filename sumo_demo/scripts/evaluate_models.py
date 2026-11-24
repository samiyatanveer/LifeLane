"""
evaluate_models.py — Phase 6 model evaluation and report generation.

Evaluates:
  1. SirenClassifier (synthetic embeddings) — precision, recall, F1, FAR
  2. ETAModel (synthetic dataset) — MAE, RMSE, MAPE vs naive baseline
  3. QueueModel (optional) — MAE vs fixed-formula baseline

Exports results to reports/model_evaluation.txt.

*** ALL RESULTS USE SYNTHETIC/MOCK DATA — clearly labeled ***
"""
from __future__ import annotations

import logging
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.join(_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "src"))

from lifelane_engine.audio.siren_classifier import (
    SirenClassifier,
    generate_synthetic_dataset,
)
from lifelane_engine.prediction.dataset_builder import generate_synthetic_eta_dataset
from lifelane_engine.prediction.eta_model import ETAModel
from lifelane_engine.prediction.queue_model import QueueModel

import numpy as np

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(_ROOT, "reports")
REPORT_PATH = os.path.join(OUTPUT_DIR, "model_evaluation.txt")

NOTE = (
    "ALL EVALUATIONS USE SYNTHETIC / MOCK DATA.\n"
    "  - Siren classifier: trained on Gaussian synthetic embeddings (not real audio).\n"
    "  - ETA model: trained on synthetic simulation-like dataset (not real SUMO runs).\n"
    "  Metrics demonstrate the pipeline works end-to-end; they do NOT reflect\n"
    "  real-world detection accuracy or ETA prediction quality."
)


def evaluate_siren_classifier() -> dict:
    """Train and evaluate the siren classifier on synthetic embeddings."""
    logger.info("[evaluate] Running siren classifier evaluation...")
    X, y, folds = generate_synthetic_dataset(n_siren=500, n_non_siren=500, seed=42)
    X_train = X[folds <= 8]
    y_train = y[folds <= 8]
    X_val = X[folds == 9]
    y_val = y[folds == 9]
    X_test = X[folds == 10]
    y_test = y[folds == 10]

    clf = SirenClassifier()
    train_metrics = clf.fit(X_train, y_train, X_val, y_val)
    test_metrics = clf.evaluate(X_test, y_test)
    return {
        "train": train_metrics,
        "test": test_metrics,
        "n_train": len(y_train),
        "n_val": len(y_val),
        "n_test": len(y_test),
    }


def evaluate_eta_model() -> dict:
    """Train and evaluate the ETA model on synthetic dataset."""
    logger.info("[evaluate] Running ETA model evaluation...")
    ds = generate_synthetic_eta_dataset(n_seeds=100, rows_per_seed=50, seed=42)
    model = ETAModel(n_estimators=200, max_depth=4)
    train_metrics = model.fit(ds["X_train"], ds["y_train"], ds["X_val"], ds["y_val"])
    test_metrics = model.evaluate(ds["X_test"], ds["y_test"])
    return {
        "train": train_metrics,
        "test": test_metrics,
        "n_train": ds["n_train"],
        "n_val": ds["n_val"],
        "n_test": ds["n_test"],
        "note": ds["note"],
    }


def write_report(siren_results: dict, eta_results: dict, path: str = REPORT_PATH) -> None:
    """Write formatted evaluation report."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "=" * 70,
        "  LifeLane Phase 6 — Model Evaluation Report",
        "=" * 70,
        "",
        "  IMPORTANT: " + NOTE.replace("\n", "\n  "),
        "",
        "─" * 70,
        "  1. Siren Classifier (SirenClassifier + MockYAMNet + Synthetic Data)",
        "─" * 70,
        f"  Training samples : {siren_results['n_train']}",
        f"  Validation samples: {siren_results['n_val']}",
        f"  Test samples     : {siren_results['n_test']}",
        "",
        "  Training metrics:",
    ]
    for k, v in siren_results["train"].items():
        if isinstance(v, float):
            lines.append(f"    {k:<25}: {v:.4f}")
        else:
            lines.append(f"    {k:<25}: {v}")

    lines += ["", "  Test metrics:"]
    for k, v in siren_results["test"].items():
        if k == "classification_report":
            lines.append(f"\n  Classification Report:\n{v}")
        elif isinstance(v, float):
            lines.append(f"    {k:<25}: {v:.4f}")
        elif isinstance(v, list):
            lines.append(f"    {k:<25}: {v}")
        else:
            lines.append(f"    {k:<25}: {v}")

    lines += [
        "",
        "─" * 70,
        "  2. ETA Model (XGBoost / Naive Fallback on Synthetic Dataset)",
        "─" * 70,
        f"  Training samples : {eta_results['n_train']}",
        f"  Validation samples: {eta_results['n_val']}",
        f"  Test samples     : {eta_results['n_test']}",
        "",
        "  Training metrics:",
    ]
    for k, v in eta_results["train"].items():
        if isinstance(v, float):
            lines.append(f"    {k:<25}: {v:.4f}")
        else:
            lines.append(f"    {k:<25}: {v}")

    lines += ["", "  Test metrics:"]
    for k, v in eta_results["test"].items():
        if isinstance(v, float):
            lines.append(f"    {k:<25}: {v:.4f}")
        else:
            lines.append(f"    {k:<25}: {v}")

    lines += ["", "=" * 70, ""]
    report = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    logger.info("[evaluate] Report written to %s", path)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    siren_res = evaluate_siren_classifier()
    eta_res = evaluate_eta_model()
    write_report(siren_res, eta_res)

