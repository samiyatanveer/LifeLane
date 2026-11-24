"""
main.py — LifeLane engine CLI entry point.

Usage:
    python -m lifelane_engine.main --mode <mode>

Modes:
    run-poc          Dataset-free mock POC (Phases 1+2).
    train-audio      Train siren classifier on synthetic data (Phase 4).
    generate-eta-data Generate synthetic ETA training dataset (Phase 5).
    train-eta        Train XGBoost ETA model (Phase 5).
    run-experiment   Run full strategy comparison experiment (Phase 6).
    evaluate         Evaluate trained models and write report (Phase 6).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure the src directory is importable when invoked directly
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


def _configure_logging(level: str = "INFO") -> None:
    """Set up structured console logging."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )


def _run_poc() -> int:
    """Run the dataset-free mock POC (Phases 1+2).

    Demonstrates all 12 required POC scenarios:
      1-6:  Phase 1 signal safety scenarios.
      7-12: Phase 2 dispatch/verification scenarios.
    """
    from lifelane_engine.poc.mock_poc import run_mock_poc
    return run_mock_poc()


def _train_audio_real() -> int:
    """Phase 4 (real data): Build manifest, extract embeddings, train and evaluate.

    Requires extracted datasets in data/raw/sireNNet/ and data/raw/UrbanSound8K/.
    Run scripts/extract_datasets.py first if needed.
    Resumable: already-cached embeddings are skipped on restart.
    """
    from lifelane_engine.audio.real_data_trainer import run_real_data_pipeline
    print("\n[LifeLane] Real-data audio pipeline — SireNNet + UrbanSound8K")
    print("  Label mapping: ambulance+US8K-siren=SIREN=1; all others=NON-SIREN=0")
    print("  class_weight='balanced' | threshold selected on validation set\n")
    results = run_real_data_pipeline()
    return 0


def _train_audio() -> int:
    """Phase 4: Train siren classifier on synthetic (or real) embeddings."""
    from lifelane_engine.audio.siren_classifier import (
        SirenClassifier, generate_synthetic_dataset
    )
    print("\n[LifeLane] Training siren classifier on SYNTHETIC data...")
    print("  (UrbanSound8K not required for this demo run)")
    X, y, folds = generate_synthetic_dataset(n_siren=500, n_non_siren=500, seed=42)
    X_train = X[folds <= 8]
    y_train = y[folds <= 8]
    X_val = X[folds == 9]
    y_val = y[folds == 9]
    X_test = X[folds == 10]
    y_test = y[folds == 10]

    clf = SirenClassifier()
    train_m = clf.fit(X_train, y_train, X_val, y_val)
    test_m = clf.evaluate(X_test, y_test)
    print(f"\n  Training: {train_m}")
    print(f"  Test F1: {test_m['f1']:.4f}  FAR: {test_m['false_alarm_rate']:.4f}")
    print("  *** SYNTHETIC DATA — not real audio performance ***")
    return 0


def _generate_eta_data() -> int:
    """Phase 5: Generate synthetic ETA dataset."""
    from lifelane_engine.prediction.dataset_builder import (
        generate_synthetic_eta_dataset, save_dataset_csv
    )
    import os
    print("\n[LifeLane] Generating SYNTHETIC ETA dataset...")
    ds = generate_synthetic_eta_dataset(n_seeds=100, rows_per_seed=50, seed=42)
    out_path = "data/sumo_logs/eta_dataset_synthetic.csv"
    os.makedirs("data/sumo_logs", exist_ok=True)
    save_dataset_csv(ds, out_path)
    print(f"  Train: {ds['n_train']}  Val: {ds['n_val']}  Test: {ds['n_test']}")
    print(f"  Saved to: {out_path}")
    print(f"  *** {ds['note']} ***")
    return 0


def _train_eta() -> int:
    """Phase 5: Train XGBoost ETA model on synthetic dataset."""
    from lifelane_engine.prediction.dataset_builder import generate_synthetic_eta_dataset
    from lifelane_engine.prediction.eta_model import ETAModel
    import os
    print("\n[LifeLane] Training XGBoost ETA model on SYNTHETIC dataset...")
    ds = generate_synthetic_eta_dataset(n_seeds=100, rows_per_seed=50, seed=42)
    model = ETAModel(n_estimators=200, max_depth=4)
    train_m = model.fit(ds["X_train"], ds["y_train"], ds["X_val"], ds["y_val"])
    test_m = model.evaluate(ds["X_test"], ds["y_test"])
    print(f"  Train MAE: {train_m.get('train_mae', 'N/A'):.2f}s")
    print(f"  Val   MAE: {train_m.get('val_mae', 'N/A'):.2f}s")
    print(f"  Test  MAE: {test_m['mae']:.2f}s  (Naive baseline: {test_m['baseline_naive_mae']:.2f}s)")
    print(f"  Model: {test_m['model']}")
    print("  *** SYNTHETIC DATA — not real SUMO performance ***")
    if model.is_fitted:
        os.makedirs("models", exist_ok=True)
        model.save("models/eta_model.joblib")
        print("  Saved to: models/eta_model.joblib")
    return 0


def _run_experiment() -> int:
    """Phase 6: Run full experiment comparison."""
    # main.py is at src/lifelane_engine/main.py; 3 parents = project root
    project_root = Path(__file__).resolve().parent.parent.parent
    scripts_dir = str(project_root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import importlib.util
    script_path = project_root / "scripts" / "run_experiment.py"
    spec = importlib.util.spec_from_file_location("run_experiment", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    results = mod.run_all_experiments()
    mod.print_summary(results)
    return 0


def _evaluate() -> int:
    """Phase 6: Evaluate all models and write report."""
    import importlib.util
    # main.py is at src/lifelane_engine/main.py; 3 parents = project root
    project_root = Path(__file__).resolve().parent.parent.parent
    script_path = project_root / "scripts" / "evaluate_models.py"
    spec = importlib.util.spec_from_file_location("evaluate_models", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    siren_res = mod.evaluate_siren_classifier()
    eta_res = mod.evaluate_eta_model()
    mod.write_report(siren_res, eta_res)
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code."""
    parser = argparse.ArgumentParser(
        prog="lifelane_engine",
        description="LifeLane: Route-Aware Ambulance Signal Preemption (simulation POC)",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=[
            "run-poc",
            "train-audio",
            "train-audio-real",
            "generate-eta-data",
            "train-eta",
            "run-experiment",
            "evaluate",
        ],
        help="Operating mode",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )

    args = parser.parse_args(argv)
    _configure_logging(args.log_level)

    logger = logging.getLogger(__name__)
    logger.info("LifeLane engine v%s — mode: %s", _get_version(), args.mode)

    dispatch = {
        "run-poc": _run_poc,
        "train-audio": _train_audio,
        "train-audio-real": _train_audio_real,
        "generate-eta-data": _generate_eta_data,
        "train-eta": _train_eta,
        "run-experiment": _run_experiment,
        "evaluate": _evaluate,
    }
    return dispatch[args.mode]()


def _get_version() -> str:
    try:
        from lifelane_engine import __version__
        return __version__
    except Exception:
        return "unknown"


if __name__ == "__main__":
    sys.exit(main())
