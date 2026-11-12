"""
eta_model.py — XGBoost ETA regressor for junction arrival prediction.

Predicts time-to-arrival at the next junction given:
  - Distance to junction (metres)
  - Current ambulance speed (m/s)
  - Queue length at junction
  - Time since last green phase
  - Demand level encoding
  - Route identifier

Falls back to naive distance/speed formula when XGBoost is unavailable
or model is not fitted.

SAFETY RULE: ETA predictions are advisory only. The signal safety controller
             makes all signal decisions independently of ML predictions.

*** SYNTHETIC TRAINING DATA IS CLEARLY LABELED ***
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

from lifelane_engine.prediction.dataset_builder import ETA_FEATURE_COLS

logger = logging.getLogger(__name__)

# Attempt XGBoost import
try:
    import xgboost as xgb
    _XGB_AVAILABLE = True
    logger.info("[eta_model] XGBoost %s available", xgb.__version__)
except ImportError:
    xgb = None  # type: ignore
    _XGB_AVAILABLE = False
    logger.warning(
        "[eta_model] XGBoost not available — using naive formula fallback. "
        "Install with: pip install xgboost"
    )

try:
    import joblib
    _JOBLIB_AVAILABLE = True
except ImportError:
    joblib = None  # type: ignore
    _JOBLIB_AVAILABLE = False


def naive_eta(
    distance_m: float,
    speed_ms: float,
    queue_vehicles: int = 0,
    queue_service_s: float = 3.5,
) -> float:
    """Naive ETA: distance/speed + queue delay.

    Used as fallback when XGBoost is unavailable or model not fitted.
    Also used as a baseline comparison strategy in Phase 6.

    Args:
        distance_m:       Metres to next junction.
        speed_ms:         Current ambulance speed in m/s.
        queue_vehicles:   Number of queued vehicles.
        queue_service_s:  Seconds per vehicle to clear queue.

    Returns:
        Predicted ETA in seconds.
    """
    if speed_ms <= 0:
        speed_ms = 1.0
    travel = distance_m / speed_ms
    queue_delay = queue_vehicles * queue_service_s
    return travel + queue_delay


class ETAModel:
    """XGBoost-based ETA regressor for junction arrival prediction.

    Wraps an XGBRegressor with fit/predict/evaluate/save/load methods.
    Falls back to naive_eta when not fitted or XGBoost unavailable.

    Args:
        n_estimators:   Number of boosting rounds.
        max_depth:      Maximum tree depth.
        learning_rate:  XGBoost eta.
        random_state:   Seed for reproducibility.
    """

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int = 4,
        learning_rate: float = 0.1,
        random_state: int = 42,
    ) -> None:
        self._n_estimators = n_estimators
        self._max_depth = max_depth
        self._learning_rate = learning_rate
        self._random_state = random_state
        self._model: Optional[object] = None
        self._fitted = False
        self._feature_names = ETA_FEATURE_COLS

        if _XGB_AVAILABLE:
            self._model = xgb.XGBRegressor(
                n_estimators=n_estimators,
                max_depth=max_depth,
                learning_rate=learning_rate,
                random_state=random_state,
                objective="reg:squarederror",
                tree_method="hist",
                verbosity=0,
            )

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
    ) -> Dict[str, float]:
        """Fit the XGBoost model.

        Args:
            X_train: (n, n_features) training features.
            y_train: (n,) target ETA values in seconds.
            X_val:   Optional (m, n_features) validation features.
            y_val:   Optional (m,) validation targets.

        Returns:
            Dict with train_mae, val_mae (if val provided).
        """
        if not _XGB_AVAILABLE:
            logger.warning("[eta_model] XGBoost unavailable; skipping fit")
            return {"note": "XGBoost not installed; using naive fallback"}

        eval_set = []
        if X_val is not None and y_val is not None:
            eval_set = [(X_val, y_val)]

        self._model.fit(
            X_train, y_train,
            eval_set=eval_set if eval_set else None,
            verbose=False,
        )
        self._fitted = True

        train_preds = self._model.predict(X_train)
        train_mae = float(np.mean(np.abs(train_preds - y_train)))
        metrics = {"train_mae": train_mae}

        if X_val is not None and y_val is not None:
            val_preds = self._model.predict(X_val)
            val_mae = float(np.mean(np.abs(val_preds - y_val)))
            metrics["val_mae"] = val_mae

        logger.info("[eta_model] Training complete: %s", metrics)
        return metrics

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(
        self,
        distance_m: float,
        speed_ms: float,
        queue_vehicles: int = 0,
        time_since_green_s: float = 0.0,
        demand_level_enc: int = 0,
        is_route_A: int = 1,
    ) -> float:
        """Predict ETA to next junction.

        Falls back to naive_eta if not fitted or XGBoost unavailable.

        Returns:
            Predicted ETA in seconds (always >= 0).
        """
        if not self._fitted or not _XGB_AVAILABLE:
            return naive_eta(distance_m, speed_ms, queue_vehicles)

        features = np.array([[
            distance_m, speed_ms, float(queue_vehicles),
            time_since_green_s, float(demand_level_enc), float(is_route_A),
        ]], dtype=np.float32)
        pred = float(self._model.predict(features)[0])
        return max(0.0, pred)

    def predict_batch(self, X: np.ndarray) -> np.ndarray:
        """Predict ETAs for a batch of feature vectors."""
        if not self._fitted or not _XGB_AVAILABLE:
            # Naive fallback for each row
            return np.array([
                naive_eta(row[0], row[1], int(row[2]))
                for row in X
            ], dtype=np.float32)
        preds = self._model.predict(X)
        return np.maximum(preds, 0.0)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self, X_test: np.ndarray, y_test: np.ndarray
    ) -> Dict[str, float]:
        """Evaluate model on the held-out test set.

        IMPORTANT: Call this ONLY on test seeds (86-100).
                   Never use test data to select hyperparameters.

        Returns:
            Dict with mae, rmse, mape.
        """
        preds = self.predict_batch(X_test)
        mae = float(np.mean(np.abs(preds - y_test)))
        rmse = float(np.sqrt(np.mean((preds - y_test) ** 2)))
        # MAPE — avoid division by zero
        mask = y_test > 0.5
        mape = (
            float(np.mean(np.abs((preds[mask] - y_test[mask]) / y_test[mask])) * 100)
            if mask.sum() > 0 else float("nan")
        )
        baseline_preds = np.array([
            naive_eta(X_test[i, 0], X_test[i, 1], int(X_test[i, 2]))
            for i in range(len(X_test))
        ])
        baseline_mae = float(np.mean(np.abs(baseline_preds - y_test)))

        results = {
            "mae": mae,
            "rmse": rmse,
            "mape_pct": mape,
            "baseline_naive_mae": baseline_mae,
            "n_test": len(y_test),
            "model": "XGBoost" if (self._fitted and _XGB_AVAILABLE) else "NaiveFallback",
        }
        logger.info("[eta_model] Evaluation: %s", results)
        return results

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, model_path: str) -> None:
        """Save the fitted model to disk."""
        if not self._fitted:
            raise RuntimeError("Model not fitted — cannot save")
        if not _JOBLIB_AVAILABLE:
            raise ImportError("joblib not available")
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(self._model, model_path)
        logger.info("[eta_model] Saved to %s", model_path)

    @classmethod
    def load(cls, model_path: str, **kwargs) -> "ETAModel":
        """Load a previously saved model."""
        if not _JOBLIB_AVAILABLE:
            raise ImportError("joblib not available")
        obj = cls(**kwargs)
        obj._model = joblib.load(model_path)
        obj._fitted = True
        logger.info("[eta_model] Loaded from %s", model_path)
        return obj

    @property
    def is_fitted(self) -> bool:
        return self._fitted
