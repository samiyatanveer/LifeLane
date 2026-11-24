"""
feature_extractor.py — YAMNet embedding extraction for siren detection.

Two modes:
  1. RealYAMNet (requires tensorflow + tensorflow-hub): extracts genuine
     521-class logits + 1024-dim embeddings from a pretrained YAMNet model.
  2. MockYAMNet (fallback): returns deterministic pseudo-random 1024-dim
     embeddings seeded by file name hash. Clearly labeled as MOCK.

The classifier trains on 1024-dim embeddings regardless of source.

IMPORTANT: MockYAMNet embeddings are NOT real audio features.
           Results trained on MockYAMNet cannot be used as real siren detection.

*** MOCK MODE IS CLEARLY LABELED — real YAMNet requires tensorflow ***
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

YAMNET_EMBEDDING_DIM = 1024
YAMNET_URL = "https://tfhub.dev/google/yamnet/1"

# Attempt TensorFlow + Hub import
try:
    import tensorflow as tf
    import tensorflow_hub as hub
    _TF_AVAILABLE = True
    logger.info("[feature_extractor] TensorFlow %s available", tf.__version__)
except ImportError:
    tf = None   # type: ignore
    hub = None  # type: ignore
    _TF_AVAILABLE = False
    logger.warning(
        "[feature_extractor] TensorFlow not available — using MockYAMNet. "
        "Install with: pip install tensorflow tensorflow-hub"
    )


class RealYAMNet:
    """TensorFlow Hub YAMNet wrapper.

    Requires tensorflow and tensorflow-hub installed.
    Downloads the model on first call (cached locally afterward).

    Usage::

        yamnet = RealYAMNet()
        embedding = yamnet.embed(audio_waveform)  # (n_frames, 1024)
    """

    def __init__(self, model_url: str = YAMNET_URL) -> None:
        if not _TF_AVAILABLE:
            raise ImportError(
                "TensorFlow is not installed. Use MockYAMNet instead or "
                "install via: pip install tensorflow tensorflow-hub"
            )
        logger.info("[feature_extractor] Loading YAMNet from %s", model_url)
        self._model = hub.load(model_url)
        logger.info("[feature_extractor] YAMNet loaded — weights frozen")

    def embed(self, waveform: np.ndarray) -> np.ndarray:
        """Extract YAMNet embeddings.

        Args:
            waveform: 1-D float32 array at 16 kHz. Min 0.96s (15360 samples).

        Returns:
            2-D float32 array of shape (n_frames, 1024).
        """
        waveform_tensor = tf.constant(waveform, dtype=tf.float32)
        _scores, embeddings, _log_mel = self._model(waveform_tensor)
        return embeddings.numpy()  # (n_frames, 1024)

    def mean_embedding(self, waveform: np.ndarray) -> np.ndarray:
        """Return the mean embedding across all frames.

        Returns:
            1-D float32 array of shape (1024,).
        """
        embeddings = self.embed(waveform)
        return embeddings.mean(axis=0)


class MockYAMNet:
    """Deterministic mock YAMNet embeddings for SUMO-free / TF-free testing.

    Returns pseudo-random 1024-dim vectors seeded by filename hash.
    The embedding dimension matches real YAMNet so the downstream classifier
    works identically regardless of whether real or mock embeddings are used.

    *** MOCK EMBEDDINGS — NOT REAL AUDIO FEATURES ***
    Results trained on MockYAMNet have no real-world audio detection validity.
    """

    def __init__(self) -> None:
        logger.warning(
            "[feature_extractor] MockYAMNet active — embeddings are "
            "deterministic pseudo-random values, NOT real audio features"
        )

    def embed(
        self,
        waveform: np.ndarray,
        filename: str = "unknown",
    ) -> np.ndarray:
        """Return a mock (1, 1024) embedding seeded by filename.

        Args:
            waveform: Ignored; embedding depends only on filename.
            filename: Used to seed RNG for reproducibility.

        Returns:
            2-D float32 array of shape (1, 1024).
        """
        seed = int(hashlib.md5(filename.encode()).hexdigest()[:8], 16) % (2 ** 31)
        rng = np.random.RandomState(seed)
        embedding = rng.randn(1, YAMNET_EMBEDDING_DIM).astype(np.float32)
        return embedding

    def mean_embedding(
        self, waveform: np.ndarray, filename: str = "unknown"
    ) -> np.ndarray:
        """Return mean (only 1 frame, so same as embed()[0]).

        Returns:
            1-D float32 array of shape (1024,).
        """
        return self.embed(waveform, filename=filename)[0]


def get_yamnet(prefer_real: bool = True) -> "RealYAMNet | MockYAMNet":
    """Return a YAMNet instance.

    Args:
        prefer_real: If True, try RealYAMNet first; fall back to MockYAMNet.
                     If False, always return MockYAMNet (useful in tests).

    Returns:
        RealYAMNet if TF is available and prefer_real=True, otherwise MockYAMNet.
    """
    if prefer_real and _TF_AVAILABLE:
        return RealYAMNet()
    return MockYAMNet()
