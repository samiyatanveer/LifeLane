"""
dataset_manifest.py — Build and manage dataset manifests for SireNNet, UrbanSound8K,
                      and Karachi Emergency Sirens dataset.

Manifest is a CSV at data/processed/manifest.csv with columns:
    file_path, dataset, class_name, label, fold, split, recording_id, embedded

- file_path:    absolute path to extracted WAV file
- dataset:      'sirenet', 'us8k', or 'karachi'
- class_name:   original class label (ambulance, siren, road_noise, etc.)
- label:        1 (SIREN) or 0 (NON-SIREN) — per approved label mapping
- fold:         fold number (1-10 for US8K; assigned for SireNNet/Karachi)
- split:        'train', 'val', or 'test'
- recording_id: grouping key for leak-free splitting
- embedded:     0/1 whether embedding has been extracted and cached

Label mapping:
    SireNNet ambulance -> SIREN=1
    SireNNet firetruck -> NON-SIREN=0
    SireNNet police    -> NON-SIREN=0
    SireNNet traffic   -> NON-SIREN=0
    US8K siren (classID=8) -> SIREN=1
    US8K all others        -> NON-SIREN=0
    Karachi ambulance/  -> SIREN=1
    Karachi road_noise/ -> NON-SIREN=0

Splitting:
    US8K: use official folds (folds 1-8 = train, fold 9 = val, fold 10 = test)
    SireNNet: group by recording_id; 70% train / 15% val / 15% test
    Karachi: random 70% train / 15% val / 15% test (file-level, no augmented pairs)
"""
from __future__ import annotations

import csv
import hashlib
import logging
import os
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Label mapping (approved by user 2026-11-01)
# ---------------------------------------------------------------------------

SIRENET_LABEL_MAP: Dict[str, int] = {
    "ambulance": 1,   # SIREN — ambulance-specific, approved SIREN=1
    "firetruck": 0,   # NON-SIREN per user decision
    "police": 0,      # NON-SIREN per user decision
    "traffic": 0,     # NON-SIREN — background road noise
}

US8K_SIREN_CLASS_ID = 8  # 'siren' class in UrbanSound8K

# Karachi dataset label map (folder name -> binary label)
KARACHI_LABEL_MAP: Dict[str, int] = {
    "ambulance": 1,    # SIREN — ambulance sirens recorded in Karachi
    "road_noise": 0,   # NON-SIREN — urban road background noise
}

MANIFEST_COLUMNS = [
    "file_path", "dataset", "class_name", "label",
    "fold", "split", "recording_id", "embedded",
]


def _sirenet_recording_id(filename: str) -> str:
    """Extract recording ID from SireNNet filename.

    sound_10.wav  -> '10'
    sound_10_1.wav -> '10'  (augmented — same recording as sound_10.wav)
    """
    base = os.path.splitext(filename)[0]  # e.g. 'sound_10_1'
    parts = base.split("_")              # ['sound', '10', '1'] or ['sound', '10']
    # parts[1] is the numeric ID; ignore trailing augmentation index
    return parts[1] if len(parts) >= 2 else base


def _sirenet_fold_split(
    recording_ids: List[str], seed: int = 42
) -> Dict[str, str]:
    """Assign train/val/test splits to SireNNet recording IDs.

    Groups: 70% train, 15% val, 15% test.
    Split is by recording_id to prevent augmented pairs from leaking.

    Returns:
        Dict mapping recording_id -> split name ('train'/'val'/'test')
    """
    unique_ids = sorted(set(recording_ids))
    rng = np.random.RandomState(seed)
    shuffled = rng.permutation(unique_ids).tolist()
    n = len(shuffled)
    n_train = int(n * 0.70)
    n_val = int(n * 0.15)
    train_ids = set(shuffled[:n_train])
    val_ids = set(shuffled[n_train: n_train + n_val])
    test_ids = set(shuffled[n_train + n_val:])
    result = {}
    for rid in unique_ids:
        if rid in train_ids:
            result[rid] = "train"
        elif rid in val_ids:
            result[rid] = "val"
        else:
            result[rid] = "test"
    return result


def build_sirenet_manifest(sirenet_dir: str, seed: int = 42) -> List[Dict]:
    """Scan extracted SireNNet directory and build manifest rows.

    Args:
        sirenet_dir: Path to extracted sireNNet/ directory.
        seed:        Random seed for reproducible train/val/test split.

    Returns:
        List of manifest row dicts.
    """
    rows = []
    for class_name in sorted(os.listdir(sirenet_dir)):
        class_dir = os.path.join(sirenet_dir, class_name)
        if not os.path.isdir(class_dir):
            continue
        label = SIRENET_LABEL_MAP.get(class_name)
        if label is None:
            logger.warning("[manifest] Unknown SireNNet class '%s' — skipping", class_name)
            continue
        for fname in sorted(os.listdir(class_dir)):
            if not fname.lower().endswith(".wav"):
                continue
            rec_id = _sirenet_recording_id(fname)
            rows.append({
                "file_path": os.path.join(class_dir, fname),
                "dataset": "sirenet",
                "class_name": class_name,
                "label": label,
                "fold": -1,       # placeholder; replaced after split assignment
                "split": "",      # placeholder
                "recording_id": f"sirenet_{class_name}_{rec_id}",
                "embedded": 0,
            })

    # Assign splits by recording_id
    all_rec_ids = [r["recording_id"] for r in rows]
    split_map = _sirenet_fold_split(all_rec_ids, seed=seed)
    split_to_fold = {"train": 1, "val": 9, "test": 10}
    for row in rows:
        split = split_map[row["recording_id"]]
        row["split"] = split
        row["fold"] = split_to_fold[split]

    logger.info(
        "[manifest] SireNNet: %d rows — train=%d val=%d test=%d (siren=%d, non-siren=%d)",
        len(rows),
        sum(1 for r in rows if r["split"] == "train"),
        sum(1 for r in rows if r["split"] == "val"),
        sum(1 for r in rows if r["split"] == "test"),
        sum(1 for r in rows if r["label"] == 1),
        sum(1 for r in rows if r["label"] == 0),
    )
    return rows


def build_us8k_manifest(us8k_dir: str) -> List[Dict]:
    """Scan extracted UrbanSound8K directory and build manifest rows.

    Uses official metadata CSV for fold and class assignments.
    Folds 1-8 = train, fold 9 = val, fold 10 = test.

    Args:
        us8k_dir: Path to extracted UrbanSound8K/ directory.

    Returns:
        List of manifest row dicts.
    """
    meta_path = os.path.join(us8k_dir, "metadata", "UrbanSound8K.csv")
    if not os.path.exists(meta_path):
        raise FileNotFoundError(
            f"UrbanSound8K metadata not found at {meta_path}. "
            "Has the archive been extracted?"
        )

    fold_to_split = {**{str(i): "train" for i in range(1, 9)}, "9": "val", "10": "test"}
    rows = []
    missing_files = []

    with open(meta_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fname = row["slice_file_name"]
            fold = row["fold"]
            class_id = int(row["classID"])
            class_name = row["class"]
            label = 1 if class_id == US8K_SIREN_CLASS_ID else 0
            split = fold_to_split.get(fold, "train")

            # File lives in audio/fold{N}/ subdirectory
            wav_path = os.path.join(us8k_dir, "audio", f"fold{fold}", fname)
            if not os.path.exists(wav_path):
                missing_files.append(wav_path)
                continue

            # recording_id: fsID (Freesound source recording)
            rec_id = f"us8k_{row['fsID']}"

            rows.append({
                "file_path": wav_path,
                "dataset": "us8k",
                "class_name": class_name,
                "label": label,
                "fold": int(fold),
                "split": split,
                "recording_id": rec_id,
                "embedded": 0,
            })

    if missing_files:
        logger.warning(
            "[manifest] US8K: %d files in metadata but missing on disk "
            "(extraction may be incomplete): %s ...",
            len(missing_files), missing_files[:3],
        )

    logger.info(
        "[manifest] US8K: %d rows — train=%d val=%d test=%d (siren=%d, non-siren=%d)",
        len(rows),
        sum(1 for r in rows if r["split"] == "train"),
        sum(1 for r in rows if r["split"] == "val"),
        sum(1 for r in rows if r["split"] == "test"),
        sum(1 for r in rows if r["label"] == 1),
        sum(1 for r in rows if r["label"] == 0),
    )
    return rows


def build_karachi_manifest(karachi_dir: str, seed: int = 42) -> List[Dict]:
    """Scan extracted Karachi dataset and build manifest rows.

    Expected directory structure:
        karachi_dir/
            ambulance/      <- SIREN=1  (ambulance sirens recorded in Karachi)
            road_noise/     <- NON-SIREN=0

    Split: random 70% train / 15% val / 15% test at file level.
    No augmented pairs to group, so splitting is file-level.

    Args:
        karachi_dir: Path to extracted karachi/ directory.
        seed:        Random seed for reproducible split.

    Returns:
        List of manifest row dicts.
    """
    rows = []
    for class_name, label in KARACHI_LABEL_MAP.items():
        class_dir = os.path.join(karachi_dir, class_name)
        if not os.path.isdir(class_dir):
            logger.warning(
                "[manifest] Karachi class dir not found: %s — skipping", class_dir
            )
            continue
        wav_files = sorted(
            f for f in os.listdir(class_dir) if f.lower().endswith(".wav")
        )
        for fname in wav_files:
            rows.append({
                "file_path": os.path.join(class_dir, fname),
                "dataset": "karachi",
                "class_name": class_name,
                "label": label,
                "fold": -1,   # assigned after split
                "split": "",
                "recording_id": f"karachi_{class_name}_{os.path.splitext(fname)[0]}",
                "embedded": 0,
            })

    # Assign splits randomly at file level (no augmented pairs)
    all_rec_ids = [r["recording_id"] for r in rows]
    split_map = _sirenet_fold_split(all_rec_ids, seed=seed)  # reuse same 70/15/15 logic
    split_to_fold = {"train": 1, "val": 9, "test": 10}
    for row in rows:
        split = split_map[row["recording_id"]]
        row["split"] = split
        row["fold"] = split_to_fold[split]

    logger.info(
        "[manifest] Karachi: %d rows — train=%d val=%d test=%d (siren=%d, non-siren=%d)",
        len(rows),
        sum(1 for r in rows if r["split"] == "train"),
        sum(1 for r in rows if r["split"] == "val"),
        sum(1 for r in rows if r["split"] == "test"),
        sum(1 for r in rows if r["label"] == 1),
        sum(1 for r in rows if r["label"] == 0),
    )
    return rows


def save_manifest(rows: List[Dict], manifest_path: str) -> None:
    """Write manifest CSV. Creates parent directories."""
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    logger.info("[manifest] Saved %d rows to %s", len(rows), manifest_path)


def load_manifest(manifest_path: str) -> List[Dict]:
    """Load manifest CSV. Returns list of row dicts."""
    rows = []
    with open(manifest_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["label"] = int(row["label"])
            row["fold"] = int(row["fold"])
            row["embedded"] = int(row["embedded"])
            rows.append(row)
    return rows


def mark_embedded(manifest_path: str, file_path: str) -> None:
    """Mark a single file as embedded in the manifest (in-place update)."""
    rows = load_manifest(manifest_path)
    for row in rows:
        if row["file_path"] == file_path:
            row["embedded"] = 1
            break
    save_manifest(rows, manifest_path)


def build_full_manifest(
    sirenet_dir: str,
    us8k_dir: str,
    manifest_path: str,
    seed: int = 42,
    us8k_available: bool = True,
    karachi_dir: Optional[str] = None,
) -> List[Dict]:
    """Build or refresh the combined manifest for all datasets.

    Karachi dataset replaces UrbanSound8K when karachi_dir is provided.
    Skips datasets whose directories do not exist.
    Idempotent: existing 'embedded' flags are preserved if manifest exists.

    Returns:
        Combined list of manifest rows.
    """
    # Load existing embedded flags if manifest exists
    existing_embedded: Dict[str, int] = {}
    if os.path.exists(manifest_path):
        existing = load_manifest(manifest_path)
        existing_embedded = {r["file_path"]: r["embedded"] for r in existing}
        logger.info(
            "[manifest] Found existing manifest (%d rows, %d embedded)",
            len(existing), sum(existing_embedded.values()),
        )

    all_rows: List[Dict] = []

    if os.path.isdir(sirenet_dir):
        sn_rows = build_sirenet_manifest(sirenet_dir, seed=seed)
        all_rows.extend(sn_rows)
    else:
        logger.warning("[manifest] SireNNet dir not found: %s — skipping", sirenet_dir)

    # Karachi takes priority over US8K when provided
    if karachi_dir and os.path.isdir(karachi_dir):
        ka_rows = build_karachi_manifest(karachi_dir, seed=seed)
        all_rows.extend(ka_rows)
        logger.info("[manifest] Using Karachi dataset instead of UrbanSound8K")
    elif us8k_available and os.path.isdir(us8k_dir):
        try:
            us_rows = build_us8k_manifest(us8k_dir)
            all_rows.extend(us_rows)
        except FileNotFoundError as e:
            logger.warning("[manifest] US8K metadata error: %s — skipping", e)
    elif not us8k_available:
        logger.info("[manifest] US8K skipped (us8k_available=False)")
    else:
        logger.warning("[manifest] US8K dir not found: %s — skipping", us8k_dir)

    # Restore embedded flags from previous run
    for row in all_rows:
        row["embedded"] = existing_embedded.get(row["file_path"], 0)

    save_manifest(all_rows, manifest_path)
    return all_rows

