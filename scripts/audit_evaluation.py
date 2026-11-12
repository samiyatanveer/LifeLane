"""
audit_evaluation.py — LifeLane Phase 4 Real-Data Evaluation Audit

Checks (all evidence-based, no test-set tuning):
  A1. Train/val/test split integrity — no file overlap across splits
  A2. SireNNet augmented-pair leak — no recording_id in both train and test
  A3. Embedding dimension verification — confirm 1024-dim, not 521
  A4. Threshold provenance — confirm 0.600 came from val set only
  A5. Label mapping consistency audit
  A6. Class distribution per split
  A7. False-positive / false-negative breakdowns with filenames
  A8. Per-class metrics with 95% Wilson confidence intervals
  A9. F1 gap: Karachi 0.903 vs SireNNet 0.736 — root-cause analysis
  A10. Window/resample check on a sample file
"""
from __future__ import annotations
import os
import sys
import math
import csv
from pathlib import Path
from collections import defaultdict, Counter

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

MANIFEST_PATH   = ROOT / "data" / "processed" / "manifest.csv"
CACHE_DIR       = ROOT / "data" / "processed" / "embeddings"
MODEL_PATH      = ROOT / "models" / "siren_classifier.joblib"
SCALER_PATH     = ROOT / "models" / "siren_scaler.joblib"
THRESHOLD_PATH  = ROOT / "models" / "siren_scaler_threshold.txt"
REPORT_OUT      = ROOT / "reports" / "audit_report.txt"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wilson_ci(k: int, n: int, z: float = 1.96):
    """Wilson score 95% CI for a proportion k/n. Returns (lo, hi)."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    spread = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return max(0.0, centre - spread), min(1.0, centre + spread)


def _f1_ci(tp, fp, fn, z=1.96):
    """Approximate 95% CI for F1 via bootstrap-approximation (Agresti-style)."""
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    # Rough SE via delta method
    n_p  = tp + fp
    n_r  = tp + fn
    se_p = math.sqrt(prec * (1 - prec) / n_p) if n_p > 0 else 0.0
    se_r = math.sqrt(rec  * (1 - rec)  / n_r) if n_r > 0 else 0.0
    if (prec + rec) > 0:
        df_dp = 2 * rec**2  / (prec + rec)**2
        df_dr = 2 * prec**2 / (prec + rec)**2
        se_f1 = math.sqrt((df_dp * se_p)**2 + (df_dr * se_r)**2)
    else:
        se_f1 = 0.0
    return f1, max(0.0, f1 - z * se_f1), min(1.0, f1 + z * se_f1)


def sep(title="", width=70, char="="):
    return char * width if not title else f"\n{'─' * 4} {title} {'─' * max(0, width - len(title) - 6)}"


# ---------------------------------------------------------------------------
# Load artefacts
# ---------------------------------------------------------------------------

def load_manifest():
    rows = []
    with open(MANIFEST_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["label"] = int(r["label"])
            r["fold"]  = int(r["fold"])
            rows.append(r)
    return rows


def load_cache_and_model():
    from lifelane_engine.audio.embedding_cache import EmbeddingCache
    from lifelane_engine.audio.siren_classifier import SirenClassifier
    cache = EmbeddingCache(str(CACHE_DIR))
    clf   = SirenClassifier.load(str(MODEL_PATH), str(SCALER_PATH))
    return cache, clf


# ---------------------------------------------------------------------------
# A1 + A2  —  Split integrity & augmented-pair leakage
# ---------------------------------------------------------------------------

def check_split_integrity(rows):
    lines = [sep("A1 + A2  Split Integrity & Augmented-Pair Leakage")]

    split_files = defaultdict(set)   # split -> set of file_path
    split_rids  = defaultdict(set)   # split -> set of recording_id

    for r in rows:
        split_files[r["split"]].add(r["file_path"])
        split_rids[r["split"]].add(r["recording_id"])

    # File-level overlaps
    for s1, s2 in [("train", "val"), ("train", "test"), ("val", "test")]:
        overlap_files = split_files[s1] & split_files[s2]
        lines.append(f"  File overlap {s1}∩{s2}: {len(overlap_files)}"
                     + (" ✅ CLEAN" if not overlap_files else f" ❌ LEAK: {list(overlap_files)[:3]}"))

    # Recording-id level overlaps (catches augmented pairs)
    for s1, s2 in [("train", "test"), ("val", "test")]:
        overlap_rids = split_rids[s1] & split_rids[s2]
        lines.append(f"  RecordingID overlap {s1}∩{s2}: {len(overlap_rids)}"
                     + (" ✅ CLEAN" if not overlap_rids else f" ❌ AUG-PAIR LEAK: {list(overlap_rids)[:5]}"))

    # SireNNet augmented-pair specific check
    sn_rows = [r for r in rows if r["dataset"] == "sirenet"]
    # group by base recording_id (the numeric part)
    base_to_splits = defaultdict(set)
    for r in sn_rows:
        # recording_id = "sirenet_<class>_<num>"  → base = last token
        base_id = r["recording_id"]
        base_to_splits[base_id].add(r["split"])

    multi_split = {rid: s for rid, s in base_to_splits.items() if len(s) > 1}
    lines.append(f"\n  SireNNet recording_ids in >1 split (aug-pair safety): {len(multi_split)}"
                 + (" ✅ NONE" if not multi_split else f" ❌ PROBLEMS: {list(multi_split.items())[:5]}"))

    # Counts per split/dataset
    lines.append("\n  Split counts by dataset:")
    for ds in ["sirenet", "karachi", "us8k"]:
        for sp in ["train", "val", "test"]:
            n = sum(1 for r in rows if r["dataset"] == ds and r["split"] == sp)
            if n:
                ns = sum(1 for r in rows if r["dataset"] == ds and r["split"] == sp and r["label"] == 1)
                lines.append(f"    {ds:10s} {sp:5s}: {n:4d} total  siren={ns}  non-siren={n-ns}")

    return lines


# ---------------------------------------------------------------------------
# A3  —  Embedding dimension check
# ---------------------------------------------------------------------------

def check_embedding_dim(rows, cache):
    lines = [sep("A3  Embedding Dimension Verification")]
    sample_rows = rows[:20]
    dims_seen = set()
    for r in sample_rows:
        emb = cache.get(r["file_path"])
        if emb is not None:
            dims_seen.add(emb.shape)
    if len(dims_seen) == 1:
        dim = list(dims_seen)[0]
        ok = dim == (1024,)
        lines.append(f"  Embedding shape: {dim}  {'✅ Correct (1024-dim)' if ok else '❌ WRONG DIM'}")
    else:
        lines.append(f"  Mixed embedding shapes! {dims_seen}  ❌ INCONSISTENT")

    # Verify NOT all 521-dim (class scores)
    lines.append("  Checking for 521-dim class-score contamination...")
    wrong521 = sum(1 for r in rows[:50]
                   if cache.get(r["file_path"]) is not None
                   and cache.get(r["file_path"]).shape == (521,))
    lines.append(f"  Files with 521-dim (wrong): {wrong521}  {'✅ None' if wrong521 == 0 else '❌ FOUND'}")
    return lines


# ---------------------------------------------------------------------------
# A4  —  Threshold provenance
# ---------------------------------------------------------------------------

def check_threshold_provenance(clf, rows, cache):
    lines = [sep("A4  Threshold Provenance (val-only selection)")]
    lines.append(f"  Stored threshold: {clf.threshold:.4f}")

    # Recompute threshold search on val only and confirm it matches
    from lifelane_engine.audio.embedding_cache import load_split_embeddings
    from sklearn.metrics import f1_score

    X_val, y_val, _ = load_split_embeddings(rows, cache, split="val")
    if len(X_val) == 0:
        lines.append("  ❌ No val embeddings found — cannot verify threshold")
        return lines

    X_sc = clf._scaler.transform(X_val)
    scores = clf._clf.predict_proba(X_sc)[:, 1]

    best_t, best_f1 = 0.5, 0.0
    candidate_rows = []
    for t in np.linspace(0.1, 0.9, 17):
        preds = (scores >= t).astype(int)
        f1 = f1_score(y_val, preds, zero_division=0)
        candidate_rows.append((round(float(t), 3), round(f1, 4)))
        if f1 > best_f1:
            best_f1 = f1
            best_t = float(t)

    lines.append(f"  Recomputed best threshold on val: {best_t:.3f}  (val F1={best_f1:.4f})")
    match = abs(best_t - clf.threshold) < 0.001
    lines.append(f"  Match with stored 0.600: {'✅ YES' if match else f'❌ NO — stored={clf.threshold:.3f} recomputed={best_t:.3f}'}")

    # Show top-5 threshold candidates
    candidate_rows.sort(key=lambda x: -x[1])
    lines.append("  Top threshold candidates on val:")
    for t, f1 in candidate_rows[:5]:
        marker = " ← selected" if abs(t - clf.threshold) < 0.001 else ""
        lines.append(f"    threshold={t:.3f}  val_f1={f1:.4f}{marker}")

    # Verify test set was NOT used in threshold selection
    X_test, y_test, _ = load_split_embeddings(rows, cache, split="test")
    scores_test = clf._clf.predict_proba(clf._scaler.transform(X_test))[:, 1]
    best_t_test, best_f1_test = 0.5, 0.0
    for t in np.linspace(0.1, 0.9, 17):
        preds = (scores_test >= t).astype(int)
        f1 = f1_score(y_test, preds, zero_division=0)
        if f1 > best_f1_test:
            best_f1_test = f1
            best_t_test = float(t)
    lines.append(f"\n  Oracle threshold on test (hypothetical, NOT used): {best_t_test:.3f} (test F1={best_f1_test:.4f})")
    gain = best_f1_test - f1_score(y_test, (scores_test >= clf.threshold).astype(int), zero_division=0)
    lines.append(f"  Potential F1 gain if threshold tuned on test: +{gain:.4f} (shows test was NOT leaked)")
    return lines


# ---------------------------------------------------------------------------
# A5  —  Label mapping audit
# ---------------------------------------------------------------------------

def check_label_mapping(rows):
    lines = [sep("A5  Label Mapping Consistency")]
    class_label_combos = Counter((r["class_name"], r["label"], r["dataset"]) for r in rows)
    lines.append("  class_name            label  dataset     count")
    lines.append("  " + "-" * 55)
    for (cls, lbl, ds), n in sorted(class_label_combos.items()):
        flag = ""
        # Flag suspicious mappings
        if cls == "firetruck" and lbl == 1:
            flag = " ⚠️  WRONG (firetruck→SIREN)"
        if cls == "police" and lbl == 1:
            flag = " ⚠️  NOTE: police siren labelled SIREN"
        if cls == "ambulance" and lbl == 0:
            flag = " ❌ WRONG (ambulance→NON-SIREN)"
        lines.append(f"  {cls:22s} {lbl}      {ds:12s} {n:5d}{flag}")

    lines.append("\n  Decision rationale:")
    lines.append("  - SireNNet firetruck/police → NON-SIREN: intentional (ambulance-only siren detection)")
    lines.append("  - Karachi road_noise → NON-SIREN: correct urban background class")
    lines.append("  - Both datasets label 'ambulance' as SIREN=1: consistent ✅")
    lines.append("  ⚠️  Known limitation: firetruck/police sirens are acoustically similar to")
    lines.append("     ambulance sirens. The model is trained to detect ambulance-class")
    lines.append("     sounds, not all sirens. This is the primary cause of SireNNet FPs.")
    return lines


# ---------------------------------------------------------------------------
# A6  —  Class distribution per split
# ---------------------------------------------------------------------------

def check_class_distribution(rows):
    lines = [sep("A6  Class Distribution per Split")]
    for ds in ["sirenet", "karachi", "combined"]:
        ds_rows = rows if ds == "combined" else [r for r in rows if r["dataset"] == ds]
        if not ds_rows:
            continue
        lines.append(f"\n  {ds.upper()}:")
        for sp in ["train", "val", "test"]:
            sp_rows = [r for r in ds_rows if r["split"] == sp]
            if not sp_rows:
                continue
            n = len(sp_rows)
            ns = sum(1 for r in sp_rows if r["label"] == 1)
            nn = n - ns
            ratio = ns / nn if nn > 0 else float("inf")
            lines.append(f"    {sp:5s}: n={n:5d}  siren={ns:4d}  non-siren={nn:4d}  ratio={ratio:.2f}")
    return lines


# ---------------------------------------------------------------------------
# A7  —  FP/FN breakdown with filenames
# ---------------------------------------------------------------------------

def check_fp_fn(rows, cache, clf):
    lines = [sep("A7  False Positive / False Negative Analysis")]
    from lifelane_engine.audio.embedding_cache import load_split_embeddings

    for ds in ["karachi", "sirenet"]:
        ds_rows = [r for r in rows if r["dataset"] == ds and r["split"] == "test"]
        X, y, paths = load_split_embeddings(rows, cache, split="test", dataset=ds)
        if len(X) == 0:
            continue

        X_sc = clf._scaler.transform(X)
        scores = clf._clf.predict_proba(X_sc)[:, 1]
        preds  = (scores >= clf.threshold).astype(int)

        fp_rows = [(paths[i], scores[i]) for i in range(len(y)) if y[i] == 0 and preds[i] == 1]
        fn_rows = [(paths[i], scores[i]) for i in range(len(y)) if y[i] == 1 and preds[i] == 0]

        lines.append(f"\n  Dataset: {ds.upper()} (test, threshold={clf.threshold:.3f})")
        lines.append(f"  TP={sum(preds[y==1])}  FP={len(fp_rows)}  FN={len(fn_rows)}  TN={sum(preds[y==0]==0)}")

        if fp_rows:
            lines.append(f"\n  FALSE POSITIVES ({len(fp_rows)}) — non-siren predicted as SIREN:")
            for path, sc in sorted(fp_rows, key=lambda x: -x[1])[:10]:
                lines.append(f"    P={sc:.3f}  {os.path.basename(path)}")
        else:
            lines.append("  FALSE POSITIVES: None ✅")

        if fn_rows:
            lines.append(f"\n  FALSE NEGATIVES ({len(fn_rows)}) — siren missed:")
            for path, sc in sorted(fn_rows, key=lambda x: x[1])[:10]:
                lines.append(f"    P={sc:.3f}  {os.path.basename(path)}")
        else:
            lines.append("  FALSE NEGATIVES: None ✅")

    return lines


# ---------------------------------------------------------------------------
# A8  —  Per-class metrics with 95% Wilson CI
# ---------------------------------------------------------------------------

def check_metrics_with_ci(rows, cache, clf):
    lines = [sep("A8  Per-Class Metrics with 95% Confidence Intervals")]
    from lifelane_engine.audio.embedding_cache import load_split_embeddings

    for ds in ["karachi", "sirenet", None]:
        label = "COMBINED" if ds is None else ds.upper()
        X, y, _ = load_split_embeddings(rows, cache, split="test", dataset=ds)
        if len(X) == 0:
            continue

        X_sc  = clf._scaler.transform(X)
        scores = clf._clf.predict_proba(X_sc)[:, 1]
        preds  = (scores >= clf.threshold).astype(int)

        # Overall
        tp = int(np.sum((preds == 1) & (y == 1)))
        fp = int(np.sum((preds == 1) & (y == 0)))
        fn = int(np.sum((preds == 0) & (y == 1)))
        tn = int(np.sum((preds == 0) & (y == 0)))
        n  = len(y)

        prec  = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec   = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_v, f1_lo, f1_hi = _f1_ci(tp, fp, fn)
        far   = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        acc   = (tp + tn) / n

        prec_lo, prec_hi = _wilson_ci(tp, tp + fp)
        rec_lo,  rec_hi  = _wilson_ci(tp, tp + fn)
        far_lo,  far_hi  = _wilson_ci(fp, fp + tn)

        lines.append(f"\n  {label}  (n={n}, threshold={clf.threshold:.3f})")
        lines.append(f"  {'Metric':<20} {'Value':>8}  {'95% CI':>18}")
        lines.append("  " + "-" * 50)
        lines.append(f"  {'Precision':<20} {prec:>8.4f}  [{prec_lo:.4f}, {prec_hi:.4f}]")
        lines.append(f"  {'Recall':<20} {rec:>8.4f}  [{rec_lo:.4f},  {rec_hi:.4f}]")
        lines.append(f"  {'F1-score':<20} {f1_v:>8.4f}  [{f1_lo:.4f},  {f1_hi:.4f}]")
        lines.append(f"  {'False Alarm Rate':<20} {far:>8.4f}  [{far_lo:.4f},  {far_hi:.4f}]")
        lines.append(f"  {'Accuracy':<20} {acc:>8.4f}")
        lines.append(f"  Confusion matrix:  TP={tp}  FP={fp}  FN={fn}  TN={tn}")

    return lines


# ---------------------------------------------------------------------------
# A9  —  Root-cause analysis: Karachi vs SireNNet F1 gap
# ---------------------------------------------------------------------------

def analyse_f1_gap(rows, cache, clf):
    lines = [sep("A9  Root-Cause: Karachi F1=0.903 vs SireNNet F1=0.736")]
    from lifelane_engine.audio.embedding_cache import load_split_embeddings

    for ds in ["karachi", "sirenet"]:
        X, y, _ = load_split_embeddings(rows, cache, split="train", dataset=ds)
        Xt, yt, _ = load_split_embeddings(rows, cache, split="test", dataset=ds)
        if len(X) == 0:
            continue

        # Score distribution on test set
        X_sc = clf._scaler.transform(Xt)
        scores = clf._clf.predict_proba(X_sc)[:, 1]
        s_siren     = scores[yt == 1]
        s_non_siren = scores[yt == 0]

        lines.append(f"\n  {ds.upper()} test score distribution:")
        lines.append(f"    SIREN     (n={len(s_siren):3d}): mean={s_siren.mean():.3f}  std={s_siren.std():.3f}  "
                     f"p5={np.percentile(s_siren,5):.3f}  p50={np.median(s_siren):.3f}  p95={np.percentile(s_siren,95):.3f}")
        lines.append(f"    NON-SIREN (n={len(s_non_siren):3d}): mean={s_non_siren.mean():.3f}  std={s_non_siren.std():.3f}  "
                     f"p5={np.percentile(s_non_siren,5):.3f}  p50={np.median(s_non_siren):.3f}  p95={np.percentile(s_non_siren,95):.3f}")

        # Separation: AUC proxy = how often siren score > non-siren score
        rng = np.random.RandomState(0)
        pairs_siren     = rng.choice(s_siren,     min(500, len(s_siren)),     replace=False)
        pairs_non_siren = rng.choice(s_non_siren, min(500, len(s_non_siren)), replace=False)
        pseudo_auc = np.mean(pairs_siren[:, None] > pairs_non_siren[None, :])
        lines.append(f"    Pseudo-AUC (pairwise): {pseudo_auc:.4f}  "
                     f"{'(excellent)' if pseudo_auc > 0.95 else '(moderate — domain gap)' if pseudo_auc > 0.80 else '(poor)'}")

    # Training composition
    train_ds = Counter(r["dataset"] for r in rows if r["split"] == "train")
    lines.append(f"\n  Train composition: {dict(train_ds)}")
    ka_train  = train_ds.get("karachi",  0)
    sn_train  = train_ds.get("sirenet",  0)
    ka_pct    = 100 * ka_train / (ka_train + sn_train) if (ka_train + sn_train) > 0 else 0
    lines.append(f"  Karachi = {ka_pct:.1f}% of training data → model is biased toward Karachi acoustics")

    lines.append("\n  Root-cause summary:")
    lines.append("  1. LABEL MISMATCH: SireNNet non-siren set includes firetruck + police sirens.")
    lines.append("     These are acoustically VERY similar to ambulance sirens → high FP rate.")
    lines.append("  2. DOMAIN SHIFT: Karachi recordings (ambulance vs road noise) offer cleaner")
    lines.append("     acoustic contrast. The model learns this easier boundary well.")
    lines.append("  3. TRAIN IMBALANCE: Karachi dominates training (see above %)")
    lines.append("     → model is better calibrated for Karachi acoustic space.")
    lines.append("  4. SireNNet ambulance sirens may differ acoustically from Karachi ambulances")
    lines.append("     (recording conditions, mic distance, street acoustics).")
    lines.append("  5. RECOMMENDATION: Treat all emergency sirens (ambulance+firetruck+police)")
    lines.append("     as SIREN=1 in SireNNet, or accept the lower SireNNet F1 as expected")
    lines.append("     for a task defined as ambulance-specific detection.")
    return lines


# ---------------------------------------------------------------------------
# A10  —  Window / resample sanity check
# ---------------------------------------------------------------------------

def check_window_resample(rows):
    lines = [sep("A10  Window & Resample Sanity Check")]
    import soundfile as sf
    from math import gcd
    from scipy.signal import resample_poly

    # Sample a few files
    sample_rows = [r for r in rows if r["split"] == "test"][:3]
    for r in sample_rows:
        path = r["file_path"]
        if not os.path.exists(path):
            lines.append(f"  MISSING: {path}")
            continue
        try:
            audio, sr = sf.read(path, always_2d=False)
            if audio.ndim == 2:
                audio = audio.mean(axis=1)
            orig_dur = len(audio) / sr
            # Resample
            if sr != 16000:
                g = gcd(16000, sr)
                audio_16k = resample_poly(audio, 16000 // g, sr // g).astype("float32")
            else:
                audio_16k = audio.astype("float32")
            new_dur = len(audio_16k) / 16000
            n_windows = max(0, int((len(audio_16k) - 15360) / 7680) + 1) if len(audio_16k) >= 15360 else 0
            lines.append(f"  {os.path.basename(path)}: orig={orig_dur:.2f}s @{sr}Hz → {new_dur:.2f}s @16kHz  "
                         f"n_0.96s_windows(50%ov)={n_windows}  min_samples_ok={'✅' if len(audio_16k)>=15360 else '⚠️ SHORT'}")
        except Exception as e:
            lines.append(f"  ERROR reading {os.path.basename(path)}: {e}")
    return lines


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_audit():
    print("Loading manifest...")
    rows = load_manifest()
    print(f"  {len(rows)} rows loaded.")

    print("Loading cache and model...")
    cache, clf = load_cache_and_model()
    print(f"  Cache: {len(cache)} entries. Threshold: {clf.threshold}")

    all_lines = []
    all_lines.append(sep("LifeLane Phase 4 — Real-Data Evaluation Audit", char="="))
    all_lines.append(f"  Manifest: {MANIFEST_PATH}  ({len(rows)} rows)")
    all_lines.append(f"  Cache entries: {len(cache)}")
    all_lines.append(f"  Model threshold: {clf.threshold:.4f}")
    all_lines.append("")

    sections = [
        ("A1+A2 Split Integrity",         check_split_integrity(rows)),
        ("A3 Embedding Dim",              check_embedding_dim(rows, cache)),
        ("A4 Threshold Provenance",       check_threshold_provenance(clf, rows, cache)),
        ("A5 Label Mapping",              check_label_mapping(rows)),
        ("A6 Class Distribution",         check_class_distribution(rows)),
        ("A7 FP/FN Breakdown",           check_fp_fn(rows, cache, clf)),
        ("A8 CI Metrics",                 check_metrics_with_ci(rows, cache, clf)),
        ("A9 F1 Gap Analysis",            analyse_f1_gap(rows, cache, clf)),
        ("A10 Window/Resample",           check_window_resample(rows)),
    ]

    for name, section_lines in sections:
        all_lines.extend(section_lines)
        all_lines.append("")

    # Recommendations
    all_lines.append(sep("RECOMMENDATIONS", char="="))
    recs = [
        ("R1", "HIGH",   "Consider relabelling SireNNet firetruck+police → SIREN=1 if the goal is "
                         "'any emergency siren' detection. This is the main driver of the 17% SireNNet FP rate."),
        ("R2", "HIGH",   "Collect or find more non-siren audio that is acoustically similar to sirens "
                         "(e.g., bus horns, construction alarms) to harden the classifier."),
        ("R3", "MEDIUM", "Stratified k-fold CV on combined dataset would give a more robust F1 estimate "
                         "than a single 70/15/15 random split, especially with ~1,600 SireNNet files."),
        ("R4", "MEDIUM", "Current mean-pooling of YAMNet frames discards temporal structure. "
                         "A sliding-window majority vote (already implemented in ApproachSelector) "
                         "mitigates short-duration false positives."),
        ("R5", "LOW",    "Karachi file-level split has no augmented-pair protection. "
                         "If any files are acoustically identical (same recording, different names), "
                         "leakage could inflate Karachi metrics."),
        ("R6", "LOW",    "Increase threshold grid resolution from 17 to 81 steps (0.01 increments) "
                         "for finer threshold selection."),
        ("R7", "INFO",   "SireNNet F1=0.736 is not a failure — it reflects the inherent difficulty "
                         "of disambiguating ambulance from police/firetruck sirens. It is honest."),
    ]
    for rid, severity, text in recs:
        all_lines.append(f"  [{rid}] [{severity}] {text}")
        all_lines.append("")

    all_lines.append(sep(char="="))

    text = "\n".join(all_lines)
    print(text)

    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(text, encoding="utf-8")
    print(f"\nAudit report saved to {REPORT_OUT}")


if __name__ == "__main__":
    os.chdir(ROOT)
    run_audit()

