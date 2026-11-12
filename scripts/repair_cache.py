"""
repair_cache.py — Validate embedding cache chunks and remove corrupted ones.

A chunk can be corrupted if the pipeline was killed mid-write.
This script:
  1. Reads every NPZ chunk file
  2. Removes from the index any entries pointing to unreadable chunks
  3. Deletes corrupted chunk files
  4. Saves a repaired index — next pipeline run will re-extract missing files

Usage:
    python scripts/repair_cache.py
"""
import csv
import os
import sys
from pathlib import Path

import numpy as np

CACHE_DIR = Path("data/processed/embeddings")
INDEX_PATH = CACHE_DIR / "index.csv"


def main():
    if not INDEX_PATH.exists():
        print("No cache index found — nothing to repair.")
        return

    # Load index
    with open(INDEX_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"Index: {len(rows)} entries")

    # Find all chunk IDs referenced
    chunk_ids = sorted({int(r["chunk_id"]) for r in rows})
    print(f"Chunks referenced: {chunk_ids}")

    # Validate each chunk
    bad_chunks = set()
    for cid in chunk_ids:
        path = CACHE_DIR / f"cache_{cid:04d}.npz"
        if not path.exists():
            print(f"  MISSING: {path.name}")
            bad_chunks.add(cid)
            continue
        try:
            data = np.load(str(path))
            arr = data["embeddings"]
            assert arr.ndim == 2 and arr.shape[1] == 1024, f"Bad shape: {arr.shape}"
            print(f"  OK: {path.name}  shape={arr.shape}")
        except Exception as e:
            print(f"  CORRUPTED: {path.name}  error={e}")
            bad_chunks.add(cid)

    if not bad_chunks:
        print("\nAll chunks are valid — cache is healthy.")
        return

    print(f"\nRemoving {len(bad_chunks)} corrupted chunk(s): {bad_chunks}")

    # Remove entries pointing to bad chunks
    good_rows = [r for r in rows if int(r["chunk_id"]) not in bad_chunks]
    removed = len(rows) - len(good_rows)
    print(f"Removing {removed} index entries referencing corrupted chunks")

    # Delete corrupted chunk files
    for cid in bad_chunks:
        path = CACHE_DIR / f"cache_{cid:04d}.npz"
        if path.exists():
            path.unlink()
            print(f"  Deleted: {path.name}")

    # Save repaired index
    with open(INDEX_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file_hash", "chunk_id", "chunk_row"])
        writer.writeheader()
        writer.writerows(good_rows)

    print(f"\nRepaired index saved: {len(good_rows)} entries remain")
    print("Re-run the pipeline — missing embeddings will be re-extracted.")


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent.parent)
    main()

