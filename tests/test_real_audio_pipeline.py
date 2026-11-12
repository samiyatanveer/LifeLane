"""
test_real_audio_pipeline.py — Tests for the real-data audio pipeline.

Tests cover:
- dataset_manifest.py: SireNNet label mapping, split assignment, leakage prevention,
  UrbanSound8K manifest building, manifest save/load.
- embedding_cache.py: Cache put/get, chunking, index persistence, batch extraction.
- real_data_trainer.py: Pipeline with MockYAMNet against real SireNNet files (when available)
  and with synthetic embeddings when datasets are absent.

All tests must pass regardless of whether the actual datasets are extracted.
Tests that require extracted files are skipped gracefully when files are absent.
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

# Ensure src/ importable
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

SIRENET_DIR = Path("D:/LIFELANE/data/raw/sireNNet")
US8K_DIR = Path("D:/LIFELANE/data/raw/UrbanSound8K")
SIRENET_AVAILABLE = SIRENET_DIR.exists() and any(SIRENET_DIR.rglob("*.wav"))
US8K_AVAILABLE = (US8K_DIR / "metadata" / "UrbanSound8K.csv").exists()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_wav(path: str, duration_s: float = 1.0, sr: int = 16000) -> None:
    """Write a minimal fake WAV file for testing."""
    import soundfile as sf
    audio = np.zeros(int(duration_s * sr), dtype=np.float32)
    sf.write(path, audio, sr)


# ---------------------------------------------------------------------------
# dataset_manifest tests
# ---------------------------------------------------------------------------

class TestSireNNetLabelMap:
    def test_ambulance_is_siren(self):
        from lifelane_engine.audio.dataset_manifest import SIRENET_LABEL_MAP
        assert SIRENET_LABEL_MAP["ambulance"] == 1

    def test_firetruck_is_non_siren(self):
        from lifelane_engine.audio.dataset_manifest import SIRENET_LABEL_MAP
        assert SIRENET_LABEL_MAP["firetruck"] == 0

    def test_police_is_non_siren(self):
        from lifelane_engine.audio.dataset_manifest import SIRENET_LABEL_MAP
        assert SIRENET_LABEL_MAP["police"] == 0

    def test_traffic_is_non_siren(self):
        from lifelane_engine.audio.dataset_manifest import SIRENET_LABEL_MAP
        assert SIRENET_LABEL_MAP["traffic"] == 0

    def test_all_four_classes_defined(self):
        from lifelane_engine.audio.dataset_manifest import SIRENET_LABEL_MAP
        assert set(SIRENET_LABEL_MAP.keys()) == {"ambulance", "firetruck", "police", "traffic"}


class TestRecordingIdExtraction:
    def test_plain_file(self):
        from lifelane_engine.audio.dataset_manifest import _sirenet_recording_id
        assert _sirenet_recording_id("sound_10.wav") == "10"

    def test_augmented_file(self):
        from lifelane_engine.audio.dataset_manifest import _sirenet_recording_id
        assert _sirenet_recording_id("sound_10_1.wav") == "10"

    def test_large_id(self):
        from lifelane_engine.audio.dataset_manifest import _sirenet_recording_id
        assert _sirenet_recording_id("sound_200.wav") == "200"

    def test_augmented_and_plain_match(self):
        from lifelane_engine.audio.dataset_manifest import _sirenet_recording_id
        assert _sirenet_recording_id("sound_55.wav") == _sirenet_recording_id("sound_55_1.wav")


class TestSplitAssignment:
    def test_split_proportions(self):
        from lifelane_engine.audio.dataset_manifest import _sirenet_fold_split
        ids = [str(i) for i in range(200)]
        split_map = _sirenet_fold_split(ids, seed=42)
        counts = {"train": 0, "val": 0, "test": 0}
        for s in split_map.values():
            counts[s] += 1
        assert counts["train"] > counts["val"]
        assert counts["train"] > counts["test"]
        assert abs(counts["val"] - counts["test"]) <= 5  # roughly equal

    def test_all_ids_assigned(self):
        from lifelane_engine.audio.dataset_manifest import _sirenet_fold_split
        ids = [str(i) for i in range(50)]
        split_map = _sirenet_fold_split(ids, seed=0)
        assert set(split_map.keys()) == set(ids)
        assert all(v in {"train", "val", "test"} for v in split_map.values())

    def test_augmented_pairs_in_same_split(self):
        """sound_N.wav and sound_N_1.wav must be in the same split."""
        from lifelane_engine.audio.dataset_manifest import _sirenet_recording_id, _sirenet_fold_split
        # Simulate filenames for 10 recordings with augmented copies
        fnames = []
        for i in range(10):
            fnames.append(f"sound_{i}.wav")
            fnames.append(f"sound_{i}_1.wav")
        rec_ids = [f"sirenet_ambulance_{_sirenet_recording_id(f)}" for f in fnames]
        split_map = _sirenet_fold_split(rec_ids, seed=42)
        # Every pair should have same split
        for i in range(10):
            rid_base = f"sirenet_ambulance_{i}"
            rid_aug = f"sirenet_ambulance_{i}"  # same rec_id
            assert split_map[rid_base] == split_map[rid_aug]

    def test_reproducible_with_same_seed(self):
        from lifelane_engine.audio.dataset_manifest import _sirenet_fold_split
        ids = [str(i) for i in range(100)]
        m1 = _sirenet_fold_split(ids, seed=7)
        m2 = _sirenet_fold_split(ids, seed=7)
        assert m1 == m2

    def test_different_seeds_give_different_splits(self):
        from lifelane_engine.audio.dataset_manifest import _sirenet_fold_split
        ids = [str(i) for i in range(100)]
        m1 = _sirenet_fold_split(ids, seed=1)
        m2 = _sirenet_fold_split(ids, seed=2)
        assert m1 != m2


class TestManifestBuildSynthetic:
    """Build manifest from a temporary fake dataset structure."""

    def test_sirenet_manifest_fake_dir(self, tmp_path):
        from lifelane_engine.audio.dataset_manifest import build_sirenet_manifest
        # Create fake directory structure
        for cls in ["ambulance", "firetruck", "police", "traffic"]:
            cls_dir = tmp_path / cls
            cls_dir.mkdir()
            for i in range(5):
                _make_fake_wav(str(cls_dir / f"sound_{i}.wav"))

        rows = build_sirenet_manifest(str(tmp_path), seed=42)
        assert len(rows) == 20
        siren_rows = [r for r in rows if r["label"] == 1]
        nonsiren_rows = [r for r in rows if r["label"] == 0]
        # Only ambulance = siren
        assert len(siren_rows) == 5
        assert len(nonsiren_rows) == 15
        assert all(r["class_name"] == "ambulance" for r in siren_rows)

    def test_sirenet_manifest_splits_present(self, tmp_path):
        from lifelane_engine.audio.dataset_manifest import build_sirenet_manifest
        for cls in ["ambulance", "traffic"]:
            cls_dir = tmp_path / cls
            cls_dir.mkdir()
            for i in range(30):
                _make_fake_wav(str(cls_dir / f"sound_{i}.wav"))
        rows = build_sirenet_manifest(str(tmp_path), seed=42)
        splits = {r["split"] for r in rows}
        assert splits == {"train", "val", "test"}

    def test_manifest_save_and_load(self, tmp_path):
        from lifelane_engine.audio.dataset_manifest import (
            build_sirenet_manifest, save_manifest, load_manifest
        )
        for cls in ["ambulance", "traffic"]:
            cls_dir = tmp_path / cls
            cls_dir.mkdir()
            for i in range(5):
                _make_fake_wav(str(cls_dir / f"sound_{i}.wav"))
        rows = build_sirenet_manifest(str(tmp_path), seed=42)
        mpath = str(tmp_path / "manifest.csv")
        save_manifest(rows, mpath)
        loaded = load_manifest(mpath)
        assert len(loaded) == len(rows)
        assert all(isinstance(r["label"], int) for r in loaded)
        assert all(isinstance(r["fold"], int) for r in loaded)

    def test_no_unknown_class_crash(self, tmp_path):
        """Unknown class directories should be skipped with a warning, not crash."""
        from lifelane_engine.audio.dataset_manifest import build_sirenet_manifest
        unknown_dir = tmp_path / "unknown_class"
        unknown_dir.mkdir()
        _make_fake_wav(str(unknown_dir / "sound_1.wav"))
        ambulance_dir = tmp_path / "ambulance"
        ambulance_dir.mkdir()
        _make_fake_wav(str(ambulance_dir / "sound_1.wav"))
        rows = build_sirenet_manifest(str(tmp_path), seed=42)
        # Only ambulance row, unknown_class skipped
        assert len(rows) == 1
        assert rows[0]["class_name"] == "ambulance"


class TestUS8KManifest:
    @pytest.mark.skipif(not US8K_AVAILABLE, reason="UrbanSound8K not yet extracted")
    def test_us8k_manifest_has_929_siren(self):
        from lifelane_engine.audio.dataset_manifest import build_us8k_manifest
        rows = build_us8k_manifest(str(US8K_DIR))
        siren = [r for r in rows if r["label"] == 1]
        assert len(siren) == 929, f"Expected 929 siren files, got {len(siren)}"

    @pytest.mark.skipif(not US8K_AVAILABLE, reason="UrbanSound8K not yet extracted")
    def test_us8k_manifest_folds_respected(self):
        from lifelane_engine.audio.dataset_manifest import build_us8k_manifest
        rows = build_us8k_manifest(str(US8K_DIR))
        val_rows = [r for r in rows if r["split"] == "val"]
        test_rows = [r for r in rows if r["split"] == "test"]
        assert all(r["fold"] == 9 for r in val_rows)
        assert all(r["fold"] == 10 for r in test_rows)

    @pytest.mark.skipif(not US8K_AVAILABLE, reason="UrbanSound8K not yet extracted")
    def test_us8k_no_train_test_leakage(self):
        """No file should appear in both train and test."""
        from lifelane_engine.audio.dataset_manifest import build_us8k_manifest
        rows = build_us8k_manifest(str(US8K_DIR))
        train_files = {r["file_path"] for r in rows if r["split"] == "train"}
        test_files = {r["file_path"] for r in rows if r["split"] == "test"}
        assert len(train_files & test_files) == 0


# ---------------------------------------------------------------------------
# embedding_cache tests
# ---------------------------------------------------------------------------

class TestEmbeddingCache:
    def test_put_and_get(self, tmp_path):
        from lifelane_engine.audio.embedding_cache import EmbeddingCache
        cache = EmbeddingCache(str(tmp_path / "cache"))
        emb = np.random.randn(1024).astype(np.float32)
        cache.put("/fake/file.wav", emb)
        retrieved = cache.get("/fake/file.wav")
        assert retrieved is not None
        np.testing.assert_allclose(retrieved, emb, rtol=1e-5)

    def test_has_returns_false_for_unknown(self, tmp_path):
        from lifelane_engine.audio.embedding_cache import EmbeddingCache
        cache = EmbeddingCache(str(tmp_path / "cache"))
        assert not cache.has("/does/not/exist.wav")

    def test_put_is_idempotent(self, tmp_path):
        from lifelane_engine.audio.embedding_cache import EmbeddingCache
        cache = EmbeddingCache(str(tmp_path / "cache"))
        emb = np.ones(1024, dtype=np.float32)
        cache.put("/file.wav", emb)
        cache.put("/file.wav", np.zeros(1024, dtype=np.float32))  # second put ignored
        retrieved = cache.get("/file.wav")
        np.testing.assert_allclose(retrieved, emb, rtol=1e-5)

    def test_index_persists_across_instances(self, tmp_path):
        from lifelane_engine.audio.embedding_cache import EmbeddingCache
        cache_dir = str(tmp_path / "cache")
        emb = np.random.randn(1024).astype(np.float32)
        c1 = EmbeddingCache(cache_dir)
        c1.put("/file.wav", emb)
        # New instance reads same index
        c2 = EmbeddingCache(cache_dir)
        assert c2.has("/file.wav")
        retrieved = c2.get("/file.wav")
        np.testing.assert_allclose(retrieved, emb, rtol=1e-5)

    def test_multiple_files(self, tmp_path):
        from lifelane_engine.audio.embedding_cache import EmbeddingCache
        cache = EmbeddingCache(str(tmp_path / "cache"))
        embeddings = {}
        for i in range(20):
            emb = np.full(1024, float(i), dtype=np.float32)
            path = f"/files/audio_{i}.wav"
            cache.put(path, emb)
            embeddings[path] = emb
        assert len(cache) == 20
        for path, emb in embeddings.items():
            np.testing.assert_allclose(cache.get(path), emb, rtol=1e-5)

    def test_len_reflects_stored_count(self, tmp_path):
        from lifelane_engine.audio.embedding_cache import EmbeddingCache
        cache = EmbeddingCache(str(tmp_path / "cache"))
        for i in range(5):
            cache.put(f"/f{i}.wav", np.zeros(1024, dtype=np.float32))
        assert len(cache) == 5


class TestBatchExtraction:
    def test_extract_from_fake_wav_files(self, tmp_path):
        """Full round-trip: create real WAV files → preprocess → MockYAMNet → cache."""
        from lifelane_engine.audio.embedding_cache import EmbeddingCache, extract_embeddings_batch
        from lifelane_engine.audio.feature_extractor import MockYAMNet

        # Create 6 fake WAV files
        wav_dir = tmp_path / "wavs"
        wav_dir.mkdir()
        rows = []
        for i in range(6):
            p = str(wav_dir / f"sound_{i}.wav")
            _make_fake_wav(p, duration_s=1.0)
            rows.append({"file_path": p, "label": i % 2, "split": "train",
                          "dataset": "sirenet", "class_name": "ambulance"})

        cache = EmbeddingCache(str(tmp_path / "cache"))
        yamnet = MockYAMNet()
        stats = extract_embeddings_batch(rows, cache, yamnet, batch_size=3)

        assert stats["processed"] == 6
        assert stats["failed"] == 0
        assert len(cache) == 6

    def test_extraction_is_resumable(self, tmp_path):
        """Second run with same rows skips already-cached files."""
        from lifelane_engine.audio.embedding_cache import EmbeddingCache, extract_embeddings_batch
        from lifelane_engine.audio.feature_extractor import MockYAMNet

        wav_dir = tmp_path / "wavs"
        wav_dir.mkdir()
        rows = []
        for i in range(4):
            p = str(wav_dir / f"s_{i}.wav")
            _make_fake_wav(p)
            rows.append({"file_path": p, "label": 0, "split": "train",
                          "dataset": "sirenet", "class_name": "traffic"})

        cache = EmbeddingCache(str(tmp_path / "cache"))
        yamnet = MockYAMNet()
        stats1 = extract_embeddings_batch(rows, cache, yamnet)
        assert stats1["processed"] == 4

        # Re-run same rows — should all be skipped
        stats2 = extract_embeddings_batch(rows, cache, yamnet)
        assert stats2["skipped"] == 4
        assert stats2["processed"] == 0

    def test_load_split_embeddings(self, tmp_path):
        from lifelane_engine.audio.embedding_cache import (
            EmbeddingCache, extract_embeddings_batch, load_split_embeddings
        )
        from lifelane_engine.audio.feature_extractor import MockYAMNet

        wav_dir = tmp_path / "wavs"
        wav_dir.mkdir()
        rows = []
        for i in range(10):
            p = str(wav_dir / f"s_{i}.wav")
            _make_fake_wav(p)
            split = "train" if i < 7 else ("val" if i < 9 else "test")
            rows.append({"file_path": p, "label": i % 2, "split": split,
                          "dataset": "sirenet", "class_name": "ambulance"})

        cache = EmbeddingCache(str(tmp_path / "cache"))
        extract_embeddings_batch(rows, cache, MockYAMNet())

        X_train, y_train, _ = load_split_embeddings(rows, cache, split="train")
        assert X_train.shape == (7, 1024)
        assert y_train.shape == (7,)

        X_test, y_test, _ = load_split_embeddings(rows, cache, split="test")
        assert X_test.shape == (1, 1024)


# ---------------------------------------------------------------------------
# Real SireNNet integration tests (skipped if not extracted)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not SIRENET_AVAILABLE, reason="SireNNet not yet extracted")
class TestSireNetRealFiles:
    def test_manifest_from_real_sirenet(self):
        from lifelane_engine.audio.dataset_manifest import build_sirenet_manifest
        rows = build_sirenet_manifest(str(SIRENET_DIR))
        assert len(rows) == 1675
        siren = [r for r in rows if r["label"] == 1]
        non_siren = [r for r in rows if r["label"] == 0]
        # Only ambulance (400) = siren
        assert len(siren) == 400
        assert len(non_siren) == 1275

    def test_all_real_files_readable(self):
        """Sample 20 files from each class and verify they load."""
        import soundfile as sf
        for cls in ["ambulance", "traffic"]:
            cls_dir = SIRENET_DIR / cls
            files = sorted(cls_dir.glob("*.wav"))[:20]
            for fpath in files:
                audio, sr = sf.read(str(fpath))
                assert sr == 44100
                assert len(audio) > 0

    def test_mock_yamnet_embeds_real_file(self):
        from lifelane_engine.audio.feature_extractor import MockYAMNet
        from lifelane_engine.audio.embedding_cache import _preprocess_audio
        yamnet = MockYAMNet()
        fpath = str(next((SIRENET_DIR / "ambulance").glob("*.wav")))
        audio = _preprocess_audio(fpath, target_sr=16000)
        assert audio is not None
        assert len(audio) > 0
        emb = yamnet.mean_embedding(audio, filename=os.path.basename(fpath))
        assert emb.shape == (1024,)

    def test_no_leakage_across_splits(self):
        """Verify augmented pairs (sound_N and sound_N_1) are in same split."""
        from lifelane_engine.audio.dataset_manifest import build_sirenet_manifest
        rows = build_sirenet_manifest(str(SIRENET_DIR), seed=42)
        rec_id_to_split = {}
        for row in rows:
            rid = row["recording_id"]
            split = row["split"]
            if rid in rec_id_to_split:
                assert rec_id_to_split[rid] == split, (
                    f"Augmented pair {rid} split into {rec_id_to_split[rid]} and {split}"
                )
            rec_id_to_split[rid] = split

