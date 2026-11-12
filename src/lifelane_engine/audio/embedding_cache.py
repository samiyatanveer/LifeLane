"""
embedding_cache.py — Batch YAMNet embedding extraction with resumable caching.

Design:
- Processes files in configurable batch sizes (default 64).
- Each file's mean 1024-dim embedding is stored in a NPZ cache keyed by a hash
  of the absolute file path.
- The manifest tracks which files have been embedded (embedded=1).
- On restart, already-embedded files are skipped instantly.
- Never loads the full dataset into RAM — one file processed at a time.
- CPU-friendly: no GPU assumed; TensorFlow CPU-only mode used if available.

Cache structure:
    data/processed/embeddings/
        cache_0000.npz   # chunk 0 (up to CHUNK_SIZE entries)
        cache_0001.npz   # chunk 1
        …
        index.csv        # file_hash -> chunk_id, chunk_row mapping
"""
from __future__ import annotations

import csv
import hashlib
import io
import logging
import os
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 1024
CHUNK_SIZE = 512  # embeddings per NPZ file


def _file_hash(file_path: str) -> str:
    """Stable 16-char hex hash of the absolute file path."""
    return hashlib.sha256(file_path.encode()).hexdigest()[:16]


class EmbeddingCache:
    """Read/write cache for mean YAMNet embeddings.

    Each entry is a 1024-dim float32 vector keyed by file path hash.
    Chunked NPZ files keep individual files small enough to open quickly.
    """

    def __init__(self, cache_dir: str) -> None:
        self.cache_dir = cache_dir
        self._index_path = os.path.join(cache_dir, "index.csv")
        self._index: Dict[str, Tuple[int, int]] = {}  # hash -> (chunk_id, row)
        os.makedirs(cache_dir, exist_ok=True)
        self._load_index()

    def _load_index(self) -> None:
        if not os.path.exists(self._index_path):
            return
        with open(self._index_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                self._index[row["file_hash"]] = (int(row["chunk_id"]), int(row["chunk_row"]))
        logger.info("[cache] Loaded index with %d entries from %s", len(self._index), self._index_path)

    def _save_index(self) -> None:
        with open(self._index_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["file_hash", "chunk_id", "chunk_row"])
            writer.writeheader()
            for fh, (cid, crow) in self._index.items():
                writer.writerow({"file_hash": fh, "chunk_id": cid, "chunk_row": crow})

    def _chunk_path(self, chunk_id: int) -> str:
        return os.path.join(self.cache_dir, f"cache_{chunk_id:04d}.npz")

    def _load_chunk(self, chunk_id: int) -> np.ndarray:
        path = self._chunk_path(chunk_id)
        if os.path.exists(path):
            return np.load(path)["embeddings"]
        return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)

    def has(self, file_path: str) -> bool:
        return _file_hash(file_path) in self._index

    def get(self, file_path: str) -> Optional[np.ndarray]:
        fh = _file_hash(file_path)
        if fh not in self._index:
            return None
        chunk_id, row = self._index[fh]
        chunk = self._load_chunk(chunk_id)
        if row < len(chunk):
            return chunk[row]
        return None

    def put(self, file_path: str, embedding: np.ndarray) -> None:
        """Store a 1024-dim embedding. Appends to current chunk."""
        fh = _file_hash(file_path)
        if fh in self._index:
            return  # already stored

        # Find next available chunk
        if self._index:
            last_chunk_id = max(v[0] for v in self._index.values())
            chunk = self._load_chunk(last_chunk_id)
            if len(chunk) >= CHUNK_SIZE:
                last_chunk_id += 1
                chunk = np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
        else:
            last_chunk_id = 0
            chunk = np.zeros((0, EMBEDDING_DIM), dtype=np.float32)

        row = len(chunk)
        new_chunk = np.vstack([chunk, embedding.reshape(1, EMBEDDING_DIM)]) if len(chunk) > 0 else embedding.reshape(1, EMBEDDING_DIM)
        np.savez_compressed(self._chunk_path(last_chunk_id), embeddings=new_chunk.astype(np.float32))
        self._index[fh] = (last_chunk_id, row)
        self._save_index()

    def __len__(self) -> int:
        return len(self._index)


def _preprocess_audio(file_path: str, target_sr: int = 16000) -> Optional[np.ndarray]:
    """Load, resample to 16 kHz, convert to mono float32.

    Resampling priority (all CPU-friendly, no numba/JIT):
      1. scipy.signal.resample_poly  — fast, integer-ratio polyphase filter (preferred)
      2. librosa.resample            — fallback if scipy unavailable
      3. numpy linear interpolation  — last resort

    Returns:
        1-D float32 array, or None if loading fails.
    """
    try:
        import soundfile as sf
        audio, sr = sf.read(file_path, always_2d=False)
        # Convert to mono
        if audio.ndim == 2:
            audio = audio.mean(axis=1)
        audio = audio.astype(np.float32)
        # Resample if needed
        if sr != target_sr:
            try:
                from math import gcd
                from scipy.signal import resample_poly
                g = gcd(int(target_sr), int(sr))
                up = int(target_sr) // g
                down = int(sr) // g
                audio = resample_poly(audio, up, down).astype(np.float32)
            except ImportError:
                try:
                    import librosa
                    audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
                except ImportError:
                    # Manual linear interpolation as last resort
                    ratio = target_sr / sr
                    new_len = int(len(audio) * ratio)
                    audio = np.interp(
                        np.linspace(0, len(audio) - 1, new_len),
                        np.arange(len(audio)),
                        audio,
                    ).astype(np.float32)
        return audio
    except Exception as e:
        logger.warning("[preprocess] Failed to load %s: %s", file_path, e)
        return None


def extract_embeddings_batch(
    manifest_rows: List[Dict],
    cache: "EmbeddingCache",
    yamnet,
    batch_size: int = 64,
    failures_path: Optional[str] = None,
) -> Dict[str, int]:
    """Extract and cache mean YAMNet embeddings for all unprocessed files.

    Resumable: skips files already in cache.
    Processes one file at a time (memory-efficient).

    Args:
        manifest_rows: List of manifest row dicts (from dataset_manifest).
        cache:         EmbeddingCache instance.
        yamnet:        RealYAMNet or MockYAMNet instance.
        batch_size:    Progress logging interval.
        failures_path: CSV to append failed files (appended, not overwritten).

    Returns:
        Dict with 'processed', 'skipped', 'failed' counts.
    """
    total = len(manifest_rows)
    processed = skipped = failed = 0
    t0 = time.time()

    failure_rows = []

    for i, row in enumerate(manifest_rows):
        fpath = row["file_path"]

        if cache.has(fpath):
            skipped += 1
            if (i + 1) % batch_size == 0:
                elapsed = time.time() - t0
                pct = (i + 1) / total * 100
                logger.info(
                    "[embed] %d/%d (%.1f%%) | processed=%d skipped=%d failed=%d | %.0fs",
                    i + 1, total, pct, processed, skipped, failed, elapsed,
                )
            continue

        audio = _preprocess_audio(fpath)
        if audio is None or len(audio) < 960:  # min 0.06s at 16kHz
            logger.warning("[embed] Skipping too-short or unreadable: %s", fpath)
            failed += 1
            failure_rows.append({"file_path": fpath, "reason": "load_failed_or_too_short"})
            continue

        try:
            # Use filename for MockYAMNet reproducibility; ignored by RealYAMNet
            fname = os.path.basename(fpath)
            if hasattr(yamnet, "mean_embedding"):
                if "filename" in yamnet.mean_embedding.__code__.co_varnames:
                    embedding = yamnet.mean_embedding(audio, filename=fname)
                else:
                    embedding = yamnet.mean_embedding(audio)
            else:
                embedding = yamnet.embed(audio).mean(axis=0)

            cache.put(fpath, embedding.astype(np.float32))
            processed += 1
        except Exception as e:
            logger.warning("[embed] Embedding failed for %s: %s", fpath, e)
            failed += 1
            failure_rows.append({"file_path": fpath, "reason": str(e)})

        if (i + 1) % batch_size == 0 or (i + 1) == total:
            elapsed = time.time() - t0
            pct = (i + 1) / total * 100
            eta = elapsed / (i + 1) * (total - i - 1) if i > 0 else 0
            logger.info(
                "[embed] %d/%d (%.1f%%) | new=%d skipped=%d failed=%d | elapsed=%.0fs ETA~%.0fs",
                i + 1, total, pct, processed, skipped, failed, elapsed, eta,
            )

    # Write failures
    if failures_path and failure_rows:
        os.makedirs(os.path.dirname(failures_path), exist_ok=True)
        write_header = not os.path.exists(failures_path)
        with open(failures_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["file_path", "reason"])
            if write_header:
                writer.writeheader()
            writer.writerows(failure_rows)

    logger.info(
        "[embed] Extraction complete: processed=%d skipped=%d failed=%d total=%d",
        processed, skipped, failed, total,
    )
    return {"processed": processed, "skipped": skipped, "failed": failed}


def load_split_embeddings(
    manifest_rows: List[Dict],
    cache: "EmbeddingCache",
    split: Optional[str] = None,
    dataset: Optional[str] = None,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Load embeddings for a split/dataset from cache.

    Args:
        manifest_rows: All manifest rows.
        cache:         EmbeddingCache instance.
        split:         'train', 'val', 'test', or None for all.
        dataset:       'sirenet', 'us8k', or None for combined.

    Returns:
        (X, y, file_paths) where X.shape = (n, 1024), y.shape = (n,).
    """
    X_list, y_list, paths = [], [], []

    for row in manifest_rows:
        if split and row["split"] != split:
            continue
        if dataset and row["dataset"] != dataset:
            continue
        emb = cache.get(row["file_path"])
        if emb is None:
            logger.debug("[load] No embedding for %s — skipping", row["file_path"])
            continue
        X_list.append(emb)
        y_list.append(row["label"])
        paths.append(row["file_path"])

    if not X_list:
        logger.warning("[load] No embeddings found for split=%s dataset=%s", split, dataset)
        return np.zeros((0, EMBEDDING_DIM), dtype=np.float32), np.zeros(0, dtype=np.int32), []

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int32)
    logger.info(
        "[load] split=%s dataset=%s: %d samples (siren=%d, non-siren=%d)",
        split, dataset, len(y), int(y.sum()), int((1 - y).sum()),
    )
    return X, y, paths

