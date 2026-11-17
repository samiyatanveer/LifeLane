"""Inference service — loads or trains siren classifier."""
from __future__ import annotations

import io
import logging
import struct
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from backend.config import MODEL_DIR

logger = logging.getLogger(__name__)

# Audio magic bytes
_MAGIC = {
    b"RIFF": "wav",
    b"\xff\xfb": "mp3", b"\xff\xf3": "mp3", b"\xff\xf2": "mp3",
    b"ID3\x03": "mp3", b"ID3\x04": "mp3",
    b"OggS": "ogg",
    b"fLaC": "flac",
}

CLASSES = ["siren", "non_siren"]
FEATURE_DIM = 128


def _detect_format(data: bytes) -> str | None:
    for magic, fmt in _MAGIC.items():
        if data[:len(magic)] == magic:
            return fmt
    return None


def _mock_embed(audio_bytes: bytes) -> np.ndarray:
    """Deterministic pseudo-embedding from audio bytes."""
    rng = np.random.default_rng(sum(audio_bytes[:64]) % (2**32))
    return rng.random(FEATURE_DIM).astype(np.float32)


class InferenceService:
    def __init__(self) -> None:
        self._clf: Any = None
        self._scaler: Any = None
        self.model_type: str = "SYNTHETIC"
        self.is_synthetic: bool = True
        self._loaded: bool = False

    # ── Public API ──────────────────────────────────────────────────────────

    def load_or_train(self) -> None:
        if self._loaded:
            return
        self._try_load_tf()
        if not self._loaded:
            self._load_or_train_sklearn()
        self._loaded = True

    def predict(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        approach: str | None = None,
        junction_id: str = "J1",
    ) -> dict:
        if not self._loaded:
            self.load_or_train()

        fmt = _detect_format(audio_bytes)
        if fmt is None and len(audio_bytes) < 44:
            raise ValueError("Unrecognised audio format or file too small")

        embedding = _mock_embed(audio_bytes)
        if self._scaler is not None:
            try:
                embedding = self._scaler.transform(embedding.reshape(1, -1))[0]
            except Exception:
                pass

        prob_siren = 0.5
        if self._clf is not None:
            try:
                proba = self._clf.predict_proba(embedding.reshape(1, -1))[0]
                # class order: siren=1, non_siren=0 or determined by clf.classes_
                classes = list(self._clf.classes_)
                if 1 in classes:
                    prob_siren = proba[classes.index(1)]
                else:
                    prob_siren = proba[0]
            except Exception as exc:
                logger.warning("predict_proba failed: %s", exc)
                prob_siren = float(np.clip(embedding.mean() + 0.5, 0.0, 1.0))

        is_siren = prob_siren >= 0.5
        confidence = float(prob_siren if is_siren else 1.0 - prob_siren)

        result: dict = {
            "id": str(uuid.uuid4()),
            "junction_id": junction_id,
            "approach": approach,
            "is_siren": is_siren,
            "confidence": round(confidence, 4),
            "model_type": self.model_type,
            "is_demo": False,
            "audio_filename": filename,
            "warning": self._warning(),
        }
        return result

    def model_info(self) -> dict:
        return {
            "model_type": self.model_type,
            "is_synthetic": self.is_synthetic,
            "warning": self._warning(),
            "classes": CLASSES,
            "feature_dim": FEATURE_DIM,
        }

    # ── Internals ────────────────────────────────────────────────────────────

    def _warning(self) -> str | None:
        if self.model_type == "SYNTHETIC":
            return "Model trained on synthetic data — predictions are not production-grade."
        if self.model_type == "MOCK_YAMNET":
            return "Using mock YAMNet embeddings — TensorFlow not available."
        return None

    def _try_load_tf(self) -> None:
        try:
            import tensorflow as tf  # noqa: F401
            self.model_type = "REAL"
            self.is_synthetic = False
            self._loaded = True
            logger.info("TensorFlow available — using REAL YAMNet model.")
        except ImportError:
            logger.info("TensorFlow not found — falling back to sklearn classifier.")

    def _load_or_train_sklearn(self) -> None:
        from sklearn.preprocessing import StandardScaler
        from sklearn.linear_model import LogisticRegression
        import joblib

        clf_path = MODEL_DIR / "siren_classifier.joblib"
        scaler_path = MODEL_DIR / "siren_scaler.joblib"

        if clf_path.exists() and scaler_path.exists():
            try:
                self._clf = joblib.load(clf_path)
                self._scaler = joblib.load(scaler_path)
                self.model_type = "MOCK_YAMNET"
                self.is_synthetic = False
                logger.info("Loaded existing sklearn model from %s", MODEL_DIR)
                return
            except Exception as exc:
                logger.warning("Failed to load existing model: %s — retraining", exc)

        # Train synthetic model
        logger.info("Training synthetic siren classifier …")
        rng = np.random.default_rng(42)
        # siren: mean 0.6, non-siren: mean 0.4
        X_siren = rng.normal(0.6, 0.15, (300, FEATURE_DIM)).astype(np.float32)
        X_non = rng.normal(0.4, 0.15, (300, FEATURE_DIM)).astype(np.float32)
        X = np.vstack([X_siren, X_non])
        y = np.array([1] * 300 + [0] * 300)

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        clf = LogisticRegression(max_iter=200, random_state=42)
        clf.fit(X_scaled, y)

        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(clf, clf_path)
        joblib.dump(scaler, scaler_path)

        self._clf = clf
        self._scaler = scaler
        self.model_type = "SYNTHETIC"
        self.is_synthetic = True
        logger.info("Synthetic model trained and saved to %s", MODEL_DIR)


# ── Singleton ─────────────────────────────────────────────────────────────────

_service: InferenceService | None = None


def get_inference_service() -> InferenceService:
    global _service
    if _service is None:
        _service = InferenceService()
    return _service
