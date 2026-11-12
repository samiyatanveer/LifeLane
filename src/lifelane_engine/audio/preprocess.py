"""
preprocess.py — Audio preprocessing for LifeLane siren detection (Phase 4).

Handles UrbanSound8K audio files:
  1. Load audio via soundfile (or librosa fallback)
  2. Convert stereo to mono (average channels)
  3. Resample to 16 kHz
  4. Validate: non-empty, no NaN/Inf, minimum length (0.96s = 15360 samples)
  5. Pad short files to minimum length with zeros

If soundfile/librosa is not available, MockAudioLoader returns a
deterministic dummy waveform for pipeline testing.

*** MOCK DATA PATHS ARE CLEARLY LABELED — no real audio data required ***
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Minimum 0.96s at 16 kHz (one YAMNet frame)
TARGET_SR = 16_000
MIN_SAMPLES = 15_360   # 0.96 * 16000

# Try loading audio libraries
try:
    import soundfile as sf
    _SOUNDFILE_AVAILABLE = True
except ImportError:
    sf = None  # type: ignore
    _SOUNDFILE_AVAILABLE = False
    logger.warning("[preprocess] soundfile not available — using mock audio loader")

try:
    import librosa
    _LIBROSA_AVAILABLE = True
except ImportError:
    librosa = None  # type: ignore
    _LIBROSA_AVAILABLE = False


class AudioPreprocessError(ValueError):
    """Raised when an audio file cannot be preprocessed."""


def load_and_preprocess(
    file_path: str,
    target_sr: int = TARGET_SR,
    min_samples: int = MIN_SAMPLES,
) -> np.ndarray:
    """Load, validate and preprocess one audio file.

    Args:
        file_path:    Path to .wav / .ogg audio file.
        target_sr:    Target sample rate in Hz (default 16 kHz).
        min_samples:  Minimum number of samples after resampling.

    Returns:
        1-D float32 numpy array at target_sr, length >= min_samples.

    Raises:
        AudioPreprocessError: on any validation failure.
        FileNotFoundError:    if file_path does not exist.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    if _SOUNDFILE_AVAILABLE:
        audio, sr = _load_soundfile(file_path)
    elif _LIBROSA_AVAILABLE:
        audio, sr = _load_librosa(file_path, target_sr)
    else:
        raise AudioPreprocessError(
            "Neither soundfile nor librosa is installed. "
            "Run: pip install soundfile librosa"
        )

    audio = _to_mono(audio)
    audio = _resample(audio, sr, target_sr)
    _validate(audio, file_path)
    audio = _pad(audio, min_samples)
    return audio.astype(np.float32)


def _load_soundfile(file_path: str) -> Tuple[np.ndarray, int]:
    """Load audio using soundfile."""
    audio, sr = sf.read(file_path, dtype="float32", always_2d=True)
    return audio, sr


def _load_librosa(file_path: str, target_sr: int) -> Tuple[np.ndarray, int]:
    """Load audio using librosa (resamples internally)."""
    audio, sr = librosa.load(file_path, sr=target_sr, mono=False)
    if audio.ndim == 1:
        audio = audio[np.newaxis, :]  # Add channel dim
    else:
        audio = audio.T              # (samples, channels)
    return audio, sr


def _to_mono(audio: np.ndarray) -> np.ndarray:
    """Convert multi-channel audio to mono by averaging channels.

    Args:
        audio: Shape (samples, channels) or (samples,).

    Returns:
        1-D numpy array.
    """
    if audio.ndim == 1:
        return audio
    if audio.ndim == 2:
        return audio.mean(axis=1)
    raise AudioPreprocessError(f"Unexpected audio shape: {audio.shape}")


def _resample(audio: np.ndarray, src_sr: int, tgt_sr: int) -> np.ndarray:
    """Resample audio from src_sr to tgt_sr using linear interpolation."""
    if src_sr == tgt_sr:
        return audio
    if _LIBROSA_AVAILABLE:
        return librosa.resample(audio, orig_sr=src_sr, target_sr=tgt_sr)
    # Fallback: numpy linear interpolation
    target_len = int(len(audio) * tgt_sr / src_sr)
    return np.interp(
        np.linspace(0, len(audio) - 1, target_len),
        np.arange(len(audio)),
        audio,
    ).astype(np.float32)


def _validate(audio: np.ndarray, path: str) -> None:
    """Raise AudioPreprocessError if audio fails quality checks."""
    if len(audio) == 0:
        raise AudioPreprocessError(f"Empty audio after loading: {path}")
    if np.any(np.isnan(audio)):
        raise AudioPreprocessError(f"NaN values in audio: {path}")
    if np.any(np.isinf(audio)):
        raise AudioPreprocessError(f"Inf values in audio: {path}")
    if np.max(np.abs(audio)) < 1e-6:
        raise AudioPreprocessError(f"Near-silent audio (all zeros): {path}")


def _pad(audio: np.ndarray, min_samples: int) -> np.ndarray:
    """Zero-pad audio to at least min_samples."""
    if len(audio) >= min_samples:
        return audio
    pad_len = min_samples - len(audio)
    return np.pad(audio, (0, pad_len), mode="constant")


# ---------------------------------------------------------------------------
# Mock audio loader — no files required
# ---------------------------------------------------------------------------

def make_mock_audio(
    filename: str = "mock_audio.wav",
    target_sr: int = TARGET_SR,
    min_samples: int = MIN_SAMPLES,
    is_siren: bool = True,
) -> np.ndarray:
    """Generate a deterministic mock audio waveform for pipeline testing.

    The waveform is seeded by the filename hash so results are reproducible.
    Clearly labeled as MOCK — not real audio data.

    Args:
        filename:    Used to seed the random number generator.
        target_sr:   Output sample rate.
        min_samples: Minimum number of samples to generate.
        is_siren:    If True, add a 440 Hz tone; otherwise pure noise.

    Returns:
        1-D float32 numpy array.
    """
    seed = int(hashlib.md5(filename.encode()).hexdigest()[:8], 16) % (2 ** 31)
    rng = np.random.RandomState(seed)
    n_samples = max(min_samples, target_sr)  # at least 1 second

    noise = rng.randn(n_samples).astype(np.float32) * 0.1
    if is_siren:
        t = np.linspace(0, n_samples / target_sr, n_samples, endpoint=False)
        # Wailing siren: two alternating tones (700 Hz and 1000 Hz)
        tone = (0.5 * np.sin(2 * np.pi * 700 * t)
                + 0.5 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
        audio = (noise + tone).clip(-1.0, 1.0)
    else:
        audio = noise
    return audio
