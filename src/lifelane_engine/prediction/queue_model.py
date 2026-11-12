"""
queue_model.py — Optional XGBoost queue-clearance time predictor (Phase 5).

Predicts the number of seconds needed to clear a vehicle queue at a junction.
This is an optional model; if data quality does not support it, the system
falls back to a fixed formula: clearance_s = n_vehicles * 3.5s.

SAFETY RULE: Queue-clearance predictions are used for corridor preparation
             timing only. The signal safety controller enforces all hard
             constraints independently.

*** SYNTHETIC TRAINING DATA IS CLEARLY LABELED ***
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Fallback constant: seconds to clear one vehicle from queue
_DEFAULT_CLEARANCE_PER_VEHICLE_S = 3.5

try:
    import xgboost as xgb
    _XGB_AVAILABLE = True
except ImportError:
    xgb = None  # type: ignore
    _XGB_AVAILABLE = False

try:
    import joblib
    _JOBLIB_AVAILABLE = True
except ImportError:
    joblib = None  # type: ignore
    _JOBLIB_AVAILABLE = False

QUEUE_FEATURE_COLS = [
    "queue_length_vehicles",
    "demand_level_enc",
    "time_since_green_s",
    "phase_duration_s",
]


def fixed_formula_clearance(n_vehicles: int, clearance_per_vehicle_s: float = _DEFAULT_CLEARANCE_PER_VEHICLE_S) -> float:
    """Fixed-formula queue clearance time estimate.

    Args:
        n_vehicles:               Queued vehicle count.
        clearance_per_vehicle_s:  Seconds per vehicle (default 3.5).

    Returns:
        Estimated clearance time in seconds.
    """
    return max(0.0, n_vehicles * clearance_per_vehicle_s)


class QueueModel:
    """XGBoost queue-clearance predictor (optional).

    Falls back to fixed_formula_clearance when not fitted or XGBoost unavailable.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 3,
        learning_rate: float = 0.1,
        random_state: int = 42,
    ) -> None:
        self._fitted = False
        self._model: Optional[object] = None
        if _XGB_AVAILABLE:
            self._model = xgb.XGBRegressor(
                n_estimators=n_estimators,
                max_depth=max_depth,
                learning_rate=learning_rate,
                random_state=random_state,
                objective="reg:squarederror",
                verbosity=0,
            )

    def fit(self, X_train: np.ndarray, y_train: np.ndarray) -> Dict[str, float]:
        """Fit the model. Returns dict with train_mae."""
        if not _XGB_AVAILABLE:
            return {"note": "XGBoost not installed; using fixed formula fallback"}
        self._model.fit(X_train, y_train, verbose=False)
        self._fitted = True
        preds = self._model.predict(X_train)
        mae = float(np.mean(np.abs(preds - y_train)))
        logger.info("[queue_model] Fitted: train_mae=%.2f", mae)
        return {"train_mae": mae}

    def predict(
        self,
        queue_length: int,
        demand_level_enc: int = 0,
        time_since_green_s: float = 0.0,
        phase_duration_s: float = 27.0,
    ) -> float:
        """Predict clearance time in seconds."""
        if not self._fitted or not _XGB_AVAILABLE:
            return fixed_formula_clearance(queue_length)
        features = np.array([[
            float(queue_length), float(demand_level_enc),
            time_since_green_s, phase_duration_s,
        ]], dtype=np.float32)
        return max(0.0, float(self._model.predict(features)[0]))

    @property
    def is_fitted(self) -> bool:
        return self._fitted
