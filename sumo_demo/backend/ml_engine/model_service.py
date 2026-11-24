"""
model_service.py — ModelService adapter for LifeLane SUMO Demo.

Loads the trained ML models (siren classifier + ETA regressor) once at
startup, then exposes a simple call interface for the TraCI controller.

RULES:
- Models are loaded READ-ONLY from backend/ml_engine/models/
- SOURCE (LifeLane/) is never touched
- On any error: log it, return fallback value, set source="FALLBACK"
- Safety signals are NEVER changed by this module
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Feature column order (must match SOURCE dataset_builder.py exactly) ────────
ETA_FEATURE_COLS = [
    "distance_to_junction_m",   # metres remaining to junction
    "current_speed_ms",         # ambulance speed m/s
    "queue_length_vehicles",    # vehicles queued at junction
    "time_since_green_s",       # seconds since junction last turned green
    "demand_level_enc",         # 0=light, 1=medium, 2=heavy
    "is_route_A",               # 1=Route A (J1→J2→hospital), 0=Route B
]

DEMAND_ENCODING = {"light": 0, "medium": 1, "heavy": 2}

# Siren probability threshold for Tier-1 decision (3 consecutive frames ≥ this)
# Source: config/settings.yaml → classifier.selected_threshold (selected on real data 2026-11-11)
SIREN_THRESHOLD = 0.600

# Mock embedding dimension (must match SOURCE backend/services/inference.py FEATURE_DIM)
FEATURE_DIM = 128


def _mock_embed(audio_bytes: bytes) -> np.ndarray:
    """
    Deterministic 128-dim pseudo-embedding from raw audio bytes.
    Exact copy of SOURCE backend/services/inference.py _mock_embed().
    """
    rng = np.random.default_rng(sum(audio_bytes[:64]) % (2**32))
    return rng.random(FEATURE_DIM).astype(np.float32)


class ModelService:
    """
    Adapter that exposes the trained LifeLane ML models to the SUMO TraCI loop.

    Usage:
        svc = ModelService(models_dir)
        result = svc.siren_prob(audio_bytes)   # → {"p": float, "latency_ms": float, "source": str}
        result = svc.predict_eta(features)     # → {"eta_s": float, "latency_ms": float, "source": str}
        info   = svc.info()                    # → {names, versions, source}
    """

    def __init__(self, models_dir: str | Path) -> None:
        self._models_dir = Path(models_dir)
        self._clf: Optional[Any] = None        # LogisticRegression
        self._scaler: Optional[Any] = None     # StandardScaler
        self._eta: Optional[Any] = None        # XGBRegressor
        self._siren_class_idx: int = 0         # index of class "1" (siren) in clf.classes_
        self._loaded: bool = False
        self._load_error: Optional[str] = None

        # Model metadata filled after load
        self._clf_name: str = "not_loaded"
        self._eta_name: str = "not_loaded"
        self._source: str = "FALLBACK"

        self._load_models()

    # ── Loading ──────────────────────────────────────────────────────────────

    def _load_models(self) -> None:
        try:
            import joblib

            clf_path    = self._models_dir / "siren_classifier.joblib"
            scaler_path = self._models_dir / "siren_scaler.joblib"
            eta_path    = self._models_dir / "eta_model.joblib"

            for p in [clf_path, scaler_path, eta_path]:
                if not p.exists():
                    raise FileNotFoundError(f"Model file not found: {p}")

            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")   # suppress XGBoost pickle-version warning
                self._clf    = joblib.load(clf_path)
                self._scaler = joblib.load(scaler_path)
                self._eta    = joblib.load(eta_path)

            # Detect siren class index from clf.classes_ (class 1 = siren)
            classes = list(self._clf.classes_)
            self._siren_class_idx = classes.index(1) if 1 in classes else 0

            self._clf_name = type(self._clf).__name__
            self._eta_name = type(self._eta).__name__
            self._source   = "REAL_MODEL"
            self._loaded   = True

            logger.info(
                "[ModelService] Loaded — clf=%s siren_idx=%d  eta=%s",
                self._clf_name, self._siren_class_idx, self._eta_name,
            )

        except Exception as exc:
            self._load_error = str(exc)
            self._source     = "FALLBACK"
            self._loaded     = False
            logger.error("[ModelService] Load failed: %s — running in FALLBACK mode", exc)

    # ── Public API ───────────────────────────────────────────────────────────

    def siren_prob(self, audio_bytes: bytes) -> Dict[str, Any]:
        """
        Run siren classifier on audio_bytes.

        Pipeline (identical to SOURCE InferenceService.predict):
            1. _mock_embed(audio_bytes)  → 128-dim float32
            2. scaler.transform(emb)
            3. clf.predict_proba[:, siren_idx]

        Returns:
            {"p": float, "latency_ms": float, "source": "REAL_MODEL"|"FALLBACK"}
        """
        t0 = time.perf_counter()
        try:
            if not self._loaded or self._clf is None or self._scaler is None:
                raise RuntimeError("Models not loaded")

            embedding = _mock_embed(audio_bytes)
            scaled    = self._scaler.transform(embedding.reshape(1, -1))
            proba     = self._clf.predict_proba(scaled)[0]
            p_siren   = float(proba[self._siren_class_idx])

            latency_ms = (time.perf_counter() - t0) * 1000
            return {"p": round(p_siren, 6), "latency_ms": round(latency_ms, 2), "source": "REAL_MODEL"}

        except Exception as exc:
            logger.warning("[ModelService] siren_prob error: %s", exc)
            latency_ms = (time.perf_counter() - t0) * 1000
            return {"p": 0.0, "latency_ms": round(latency_ms, 2), "source": "FALLBACK"}

    def predict_eta(self, features: Dict[str, float]) -> Dict[str, Any]:
        """
        Predict ambulance ETA to a junction.

        Args:
            features: dict with keys matching ETA_FEATURE_COLS (in any order).
                      Required: distance_to_junction_m, current_speed_ms,
                                queue_length_vehicles, time_since_green_s,
                                demand_level_enc, is_route_A

        Returns:
            {"eta_s": float, "latency_ms": float, "source": "REAL_MODEL"|"FALLBACK"}
        """
        t0 = time.perf_counter()
        try:
            if not self._loaded or self._eta is None:
                raise RuntimeError("ETA model not loaded")

            x = np.array(
                [[features.get(col, 0.0) for col in ETA_FEATURE_COLS]],
                dtype=np.float32,
            )
            eta_raw = float(self._eta.predict(x)[0])
            eta_s = max(0.0, eta_raw)   # clamp negatives (model artefact)

            latency_ms = (time.perf_counter() - t0) * 1000
            return {"eta_s": eta_s, "eta_raw": eta_raw, "latency_ms": round(latency_ms, 2), "source": "REAL_MODEL"}

        except Exception as exc:
            logger.warning("[ModelService] predict_eta error: %s", exc)
            # Naive fallback: distance / speed
            try:
                d = float(features.get("distance_to_junction_m", 0.0))
                s = float(features.get("current_speed_ms", 1.0)) or 1.0
                eta_s = round(d / s, 2)
            except Exception:
                eta_s = 0.0
            latency_ms = (time.perf_counter() - t0) * 1000
            return {"eta_s": eta_s, "latency_ms": round(latency_ms, 2), "source": "FALLBACK"}

    def info(self) -> Dict[str, Any]:
        """Return model metadata."""
        return {
            "clf_name": self._clf_name,
            "eta_name": self._eta_name,
            "source":   self._source,
            "loaded":   self._loaded,
            "error":    self._load_error,
            "feature_dim": FEATURE_DIM,
            "eta_features": ETA_FEATURE_COLS,
            "siren_threshold": SIREN_THRESHOLD,
        }

    @property
    def is_loaded(self) -> bool:
        return self._loaded


# ── Singleton ─────────────────────────────────────────────────────────────────

_service: Optional[ModelService] = None


def get_model_service(models_dir: str | Path | None = None) -> ModelService:
    """Return singleton ModelService; initialise on first call."""
    global _service
    if _service is None:
        if models_dir is None:
            # Default: same directory as this file, then ../../backend/ml_engine/models
            models_dir = Path(__file__).parent / "models"
        _service = ModelService(models_dir)
    return _service
