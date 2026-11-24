"""
real_data_trainer.py — End-to-end pipeline: manifest → embed → train → evaluate.

Usage (via main.py --mode train-audio-real):
    1. Build manifest from extracted datasets.
    2. Extract YAMNet embeddings (resumable; skips already-cached).
    3. Train SirenClassifier on real embeddings.
    4. Evaluate separately on UrbanSound8K test fold and SireNNet test set.
    5. Write evaluation report.

All results clearly labelled by dataset source.
Does NOT train on synthetic data.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_SIRENET_DIR = os.path.join("data", "raw", "sireNNet")
DEFAULT_US8K_DIR = os.path.join("data", "raw", "UrbanSound8K")
DEFAULT_KARACHI_DIR = os.path.join("data", "raw", "karachi")
DEFAULT_MANIFEST_PATH = os.path.join("data", "processed", "manifest.csv")
DEFAULT_CACHE_DIR = os.path.join("data", "processed", "embeddings")
DEFAULT_FAILURES_PATH = os.path.join("data", "processed", "preprocessing_failures.csv")
DEFAULT_MODEL_PATH = os.path.join("models", "siren_classifier.joblib")
DEFAULT_SCALER_PATH = os.path.join("models", "siren_scaler.joblib")
DEFAULT_REPORT_PATH = os.path.join("reports", "audio_evaluation_real.txt")


def run_real_data_pipeline(
    sirenet_dir: str = DEFAULT_SIRENET_DIR,
    us8k_dir: str = DEFAULT_US8K_DIR,
    karachi_dir: str = DEFAULT_KARACHI_DIR,
    manifest_path: str = DEFAULT_MANIFEST_PATH,
    cache_dir: str = DEFAULT_CACHE_DIR,
    failures_path: str = DEFAULT_FAILURES_PATH,
    model_path: str = DEFAULT_MODEL_PATH,
    scaler_path: str = DEFAULT_SCALER_PATH,
    report_path: str = DEFAULT_REPORT_PATH,
    prefer_real_yamnet: bool = True,
    batch_log_interval: int = 200,
    us8k_available: Optional[bool] = None,
) -> Dict:
    """Run the full real-data audio pipeline.

    Returns:
        Dict with train_metrics, us8k_test_metrics, sirenet_test_metrics, combined_test_metrics.
    """
    from lifelane_engine.audio.dataset_manifest import build_full_manifest, load_manifest
    from lifelane_engine.audio.embedding_cache import EmbeddingCache, extract_embeddings_batch, load_split_embeddings
    from lifelane_engine.audio.feature_extractor import get_yamnet
    from lifelane_engine.audio.siren_classifier import SirenClassifier

    # --- Determine dataset availability ---
    sirenet_exists = os.path.isdir(sirenet_dir)
    us8k_exists = os.path.isdir(us8k_dir)
    karachi_exists = os.path.isdir(karachi_dir)
    if us8k_available is None:
        us8k_available = us8k_exists and not karachi_exists  # Karachi takes priority

    if not sirenet_exists and not us8k_available and not karachi_exists:
        raise RuntimeError(
            "No dataset directories found. "
            f"Expected SireNNet at {sirenet_dir} and/or Karachi at {karachi_dir}\n"
            "Run: python scripts/extract_datasets.py"
        )

    logger.info("[trainer] SireNNet dir: %s (exists=%s)", sirenet_dir, sirenet_exists)
    logger.info("[trainer] Karachi dir: %s (exists=%s)", karachi_dir, karachi_exists)
    if not karachi_exists:
        logger.info("[trainer] US8K dir: %s (available=%s)", us8k_dir, us8k_available)

    # --- Step 1: Build manifest ---
    logger.info("[trainer] Step 1/4: Building dataset manifest...")
    rows = build_full_manifest(
        sirenet_dir=sirenet_dir,
        us8k_dir=us8k_dir,
        karachi_dir=karachi_dir if karachi_exists else None,
        manifest_path=manifest_path,
        us8k_available=us8k_available,
    )
    _print_manifest_summary(rows)

    # --- Step 2: Extract embeddings ---
    logger.info("[trainer] Step 2/4: Extracting YAMNet embeddings (resumable)...")
    yamnet = get_yamnet(prefer_real=prefer_real_yamnet)
    cache = EmbeddingCache(cache_dir)

    unembedded = [r for r in rows if not cache.has(r["file_path"])]
    already_done = len(rows) - len(unembedded)
    logger.info(
        "[trainer] %d files total: %d already cached, %d to process",
        len(rows), already_done, len(unembedded),
    )

    extract_embeddings_batch(
        manifest_rows=rows,
        cache=cache,
        yamnet=yamnet,
        batch_size=batch_log_interval,
        failures_path=failures_path,
    )

    # --- Step 3: Load splits and train ---
    logger.info("[trainer] Step 3/4: Loading embeddings and training classifier...")

    X_train, y_train, _ = load_split_embeddings(rows, cache, split="train")
    X_val, y_val, _ = load_split_embeddings(rows, cache, split="val")

    if len(X_train) == 0:
        raise RuntimeError(
            "No training embeddings found. "
            "Check that datasets were extracted and embeddings were computed."
        )

    clf = SirenClassifier(class_weight="balanced")
    train_metrics = clf.fit(X_train, y_train, X_val if len(X_val) > 0 else None, y_val if len(y_val) > 0 else None)
    logger.info("[trainer] Training complete: %s", train_metrics)

    # Save model
    clf.save(model_path, scaler_path)

    # --- Step 4: Evaluate ---
    logger.info("[trainer] Step 4/4: Evaluating on test sets...")
    results: Dict = {
        "train_metrics": train_metrics,
        "us8k_test_metrics": None,
        "karachi_test_metrics": None,
        "sirenet_test_metrics": None,
        "combined_test_metrics": None,
    }

    # UrbanSound8K test fold (fold 10) — only if used
    if us8k_available and not karachi_exists:
        X_us8k_test, y_us8k_test, _ = load_split_embeddings(rows, cache, split="test", dataset="us8k")
        if len(X_us8k_test) > 0:
            results["us8k_test_metrics"] = clf.evaluate(X_us8k_test, y_us8k_test)
            logger.info("[trainer] US8K test: %s", {k: v for k, v in results["us8k_test_metrics"].items() if k != "classification_report"})

    # Karachi test set
    if karachi_exists:
        X_ka_test, y_ka_test, _ = load_split_embeddings(rows, cache, split="test", dataset="karachi")
        if len(X_ka_test) > 0:
            results["karachi_test_metrics"] = clf.evaluate(X_ka_test, y_ka_test)
            logger.info("[trainer] Karachi test: %s", {k: v for k, v in results["karachi_test_metrics"].items() if k != "classification_report"})

    # SireNNet test set
    if sirenet_exists:
        X_sn_test, y_sn_test, _ = load_split_embeddings(rows, cache, split="test", dataset="sirenet")
        if len(X_sn_test) > 0:
            results["sirenet_test_metrics"] = clf.evaluate(X_sn_test, y_sn_test)
            logger.info("[trainer] SireNNet test: %s", {k: v for k, v in results["sirenet_test_metrics"].items() if k != "classification_report"})

    # Combined test
    X_combined_test, y_combined_test, _ = load_split_embeddings(rows, cache, split="test")
    if len(X_combined_test) > 0:
        results["combined_test_metrics"] = clf.evaluate(X_combined_test, y_combined_test)

    # Write report
    _write_report(results, report_path, sirenet_exists, us8k_available, karachi_exists)

    return results


def _print_manifest_summary(rows) -> None:
    from collections import Counter
    ds_split = Counter((r["dataset"], r["split"]) for r in rows)
    logger.info("[trainer] Manifest summary:")
    for ds in ["sirenet", "karachi", "us8k"]:
        t = sum(1 for r in rows if r["dataset"] == ds and r["split"] == "train")
        v = sum(1 for r in rows if r["dataset"] == ds and r["split"] == "val")
        te = sum(1 for r in rows if r["dataset"] == ds and r["split"] == "test")
        s = sum(1 for r in rows if r["dataset"] == ds and r["label"] == 1)
        n = sum(1 for r in rows if r["dataset"] == ds and r["label"] == 0)
        if t + v + te > 0:
            logger.info("  %s: train=%d val=%d test=%d | siren=%d non-siren=%d", ds, t, v, te, s, n)


def _write_report(results: Dict, report_path: str, sirenet_exists: bool, us8k_available: bool, karachi_exists: bool = False) -> None:
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    second_dataset = "Karachi Emergency Sirens" if karachi_exists else "UrbanSound8K"
    lines = [
        "=" * 70,
        "  LifeLane Phase 4 — Real-Data Audio Model Evaluation",
        "=" * 70,
        "",
        "  REAL DATA RESULTS — embeddings extracted from actual audio recordings.",
        "",
        "  Label mapping:",
        "    SireNNet: ambulance -> SIREN=1",
        "    SireNNet: firetruck, police, traffic -> NON-SIREN=0",
    ]
    if karachi_exists:
        lines += [
            "    Karachi: ambulance/ -> SIREN=1",
            "    Karachi: road_noise/ -> NON-SIREN=0",
        ]
    else:
        lines += [
            "    US8K:     siren (classID=8) -> SIREN=1",
            "    US8K:     all other 9 classes -> NON-SIREN=0",
        ]
    lines.append("")

    def _fmt_metrics(name: str, m: Optional[Dict]) -> list:
        if m is None:
            return [f"  {name}: Not available (dataset not found or no test data)"]
        out = [f"  {name}:"]
        out.append(f"    Test samples : {m['n_test']}")
        out.append(f"    Threshold    : {m['threshold']:.3f}")
        out.append(f"    Precision    : {m['precision']:.4f}")
        out.append(f"    Recall       : {m['recall']:.4f}")
        out.append(f"    F1-score     : {m['f1']:.4f}")
        out.append(f"    False alarm  : {m['false_alarm_rate']:.4f}")
        out.append(f"    Confusion matrix: {m['confusion_matrix']}")
        if "classification_report" in m:
            out.append("")
            out.append("    Classification report:")
            for line in m["classification_report"].split("\n"):
                out.append(f"      {line}")
        return out

    if karachi_exists:
        lines += _fmt_metrics("Karachi Emergency Sirens Test", results.get("karachi_test_metrics"))
        lines += [""]
    else:
        lines += _fmt_metrics("UrbanSound8K Test (fold 10)", results.get("us8k_test_metrics"))
        lines += [""]
    lines += _fmt_metrics("SireNNet Test Set (ambulance-specific)", results.get("sirenet_test_metrics"))
    lines += [""]
    lines += _fmt_metrics("Combined Test Set", results.get("combined_test_metrics"))
    lines += ["", "=" * 70]
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    logger.info("[trainer] Evaluation report written to %s", report_path)
    print("\n".join(lines))

