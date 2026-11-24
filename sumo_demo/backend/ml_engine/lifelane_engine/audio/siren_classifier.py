"""
siren_classifier.py — Logistic Regression siren classifier trained on YAMNet embeddings.

Pipeline:
  1. StandardScaler normalises 1024-dim YAMNet embeddings.
  2. LogisticRegression (class_weight="balanced") classifies siren vs non-siren.
  3. Classification threshold is selected on validation fold 9 (never on test fold 10).
  4. Model and scaler are saved/loaded via joblib.

On predict(), returns:
  - raw_score:     probability of siren class (float in [0, 1])
  - is_siren:      True if raw_score >= threshold

When UrbanSound8K is not available, a synthetic dataset generator is included
that clearly labels all generated data as SYNTHETIC.

*** SYNTHETIC DATA IS CLEARLY LABELED — not derived from real audio ***
"""
from __future__ import annotations

import logging
import os
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Try sklearn
try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import (
        classification_report,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
    )
    import joblib
    _SKLEARN_AVAILABLE = True
except ImportError:
    LogisticRegression = None  # type: ignore
    StandardScaler = None       # type: ignore
    joblib = None               # type: ignore
    _SKLEARN_AVAILABLE = False
    logger.warning(
        "[classifier] scikit-learn / joblib not available. "
        "Install with: pip install scikit-learn joblib"
    )

EMBEDDING_DIM = 1024
DEFAULT_THRESHOLD = 0.5


class SirenClassifier:
    """Logistic Regression siren/non-siren binary classifier.

    Args:
        threshold:      Minimum probability to classify as siren.
        max_iter:       LogisticRegression max iterations.
        class_weight:   Passed to LogisticRegression (default "balanced").
    """

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        max_iter: int = 1000,
        class_weight: str = "balanced",
    ) -> None:
        if not _SKLEARN_AVAILABLE:
            raise ImportError(
                "scikit-learn is not installed. "
                "Run: pip install scikit-learn joblib"
            )
        self.threshold = threshold
        self._scaler = StandardScaler()
        self._clf = LogisticRegression(
            class_weight=class_weight,
            max_iter=max_iter,
            solver="lbfgs",
            C=1.0,
        )
        self._fitted = False

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
        """Fit scaler and classifier. Optionally select threshold on val set.

        IMPORTANT: Threshold is selected on X_val/y_val ONLY if provided.
                   X_val/y_val must be from fold 9; NEVER from fold 10 (test).

        Args:
            X_train: (n_train, 1024) training embeddings.
            y_train: (n_train,) binary labels (1=siren, 0=non-siren).
            X_val:   (n_val, 1024) validation embeddings (optional).
            y_val:   (n_val,) binary validation labels (optional).

        Returns:
            Dict with training metrics (val metrics included if X_val provided).
        """
        logger.info(
            "[classifier] Fitting on %d samples (%d siren, %d non-siren)",
            len(y_train), int(y_train.sum()), int((1 - y_train).sum()),
        )
        X_scaled = self._scaler.fit_transform(X_train)
        self._clf.fit(X_scaled, y_train)
        self._fitted = True

        train_preds = self.predict_batch(X_train)
        metrics: Dict[str, float] = {
            "train_f1": f1_score(y_train, train_preds, zero_division=0),
            "train_precision": precision_score(y_train, train_preds, zero_division=0),
            "train_recall": recall_score(y_train, train_preds, zero_division=0),
        }

        if X_val is not None and y_val is not None:
            best_thresh, val_f1 = self._select_threshold(X_val, y_val)
            self.threshold = best_thresh
            val_preds = self.predict_batch(X_val)
            metrics.update({
                "val_f1": val_f1,
                "val_precision": precision_score(y_val, val_preds, zero_division=0),
                "val_recall": recall_score(y_val, val_preds, zero_division=0),
                "selected_threshold": best_thresh,
            })
            logger.info(
                "[classifier] Threshold selected on val set: %.3f (val_f1=%.3f)",
                best_thresh, val_f1,
            )

        logger.info("[classifier] Training complete: %s", metrics)
        return metrics

    def _select_threshold(
        self, X_val: np.ndarray, y_val: np.ndarray
    ) -> Tuple[float, float]:
        """Select threshold maximising F1 on the validation set."""
        X_scaled = self._scaler.transform(X_val)
        scores = self._clf.predict_proba(X_scaled)[:, 1]
        best_thresh, best_f1 = DEFAULT_THRESHOLD, 0.0
        for thresh in np.linspace(0.1, 0.9, 17):
            preds = (scores >= thresh).astype(int)
            f1 = f1_score(y_val, preds, zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_thresh = float(thresh)
        return best_thresh, best_f1

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict_proba(self, embedding: np.ndarray) -> float:
        """Return siren probability for one 1024-dim embedding.

        Args:
            embedding: 1-D or (1, 1024) float32 array.

        Returns:
            Float in [0, 1]; probability of siren class.
        """
        if not self._fitted:
            raise RuntimeError("Classifier not fitted. Call fit() first.")
        emb = embedding.reshape(1, -1)
        emb_scaled = self._scaler.transform(emb)
        return float(self._clf.predict_proba(emb_scaled)[0, 1])

    def predict(self, embedding: np.ndarray) -> Tuple[float, bool]:
        """Classify one embedding.

        Returns:
            (raw_score, is_siren): probability and binary decision.
        """
        score = self.predict_proba(embedding)
        return score, score >= self.threshold

    def predict_batch(self, X: np.ndarray) -> np.ndarray:
        """Classify a batch. Returns binary 0/1 array."""
        if not self._fitted:
            raise RuntimeError("Classifier not fitted.")
        X_scaled = self._scaler.transform(X)
        scores = self._clf.predict_proba(X_scaled)[:, 1]
        return (scores >= self.threshold).astype(int)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self, X_test: np.ndarray, y_test: np.ndarray
    ) -> Dict[str, object]:
        """Evaluate on the test set (fold 10 only).

        IMPORTANT: Call this ONLY on the held-out test fold. Never use
                   test fold data to select the threshold or tune parameters.

        Returns:
            Dict with precision, recall, f1, confusion_matrix, classification_report.
        """
        if not self._fitted:
            raise RuntimeError("Classifier not fitted.")
        preds = self.predict_batch(X_test)
        scores = self._scaler.transform(X_test)
        raw_scores = self._clf.predict_proba(scores)[:, 1]

        # False alarm rate: FP / (FP + TN)
        cm = confusion_matrix(y_test, preds)
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
        false_alarm_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0

        return {
            "precision": precision_score(y_test, preds, zero_division=0),
            "recall": recall_score(y_test, preds, zero_division=0),
            "f1": f1_score(y_test, preds, zero_division=0),
            "confusion_matrix": cm.tolist(),
            "false_alarm_rate": false_alarm_rate,
            "classification_report": classification_report(
                y_test, preds, zero_division=0
            ),
            "n_test": len(y_test),
            "threshold": self.threshold,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, model_path: str, scaler_path: str) -> None:
        """Save classifier, scaler, and threshold to disk."""
        if not _SKLEARN_AVAILABLE:
            raise ImportError("joblib not available")
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(self._clf, model_path)
        joblib.dump(self._scaler, scaler_path)
        # Persist threshold alongside scaler (threshold.txt next to scaler)
        threshold_path = scaler_path.replace(".joblib", "_threshold.txt")
        with open(threshold_path, "w") as f:
            f.write(str(self.threshold))
        logger.info("[classifier] Saved to %s and %s (threshold=%.3f)", model_path, scaler_path, self.threshold)

    @classmethod
    def load(cls, model_path: str, scaler_path: str, threshold: float = DEFAULT_THRESHOLD) -> "SirenClassifier":
        """Load classifier, scaler, and (if saved) threshold from disk."""
        if not _SKLEARN_AVAILABLE:
            raise ImportError("joblib not available")
        obj = cls.__new__(cls)
        obj._clf = joblib.load(model_path)
        obj._scaler = joblib.load(scaler_path)
        obj._fitted = True
        # Try to restore saved threshold
        threshold_path = scaler_path.replace(".joblib", "_threshold.txt")
        if os.path.exists(threshold_path):
            with open(threshold_path) as f:
                obj.threshold = float(f.read().strip())
            logger.info("[classifier] Loaded from %s (threshold=%.3f)", model_path, obj.threshold)
        else:
            obj.threshold = threshold
            logger.info("[classifier] Loaded from %s (threshold=%.3f default)", model_path, obj.threshold)
        return obj


# ---------------------------------------------------------------------------
# Synthetic dataset generator
# ---------------------------------------------------------------------------

def generate_synthetic_dataset(
    n_siren: int = 500,
    n_non_siren: int = 500,
    embedding_dim: int = EMBEDDING_DIM,
    seed: int = 42,
    fold_assignments: Optional[Dict[int, int]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate a clearly-labeled synthetic embedding dataset.

    *** SYNTHETIC DATA — NOT DERIVED FROM REAL AUDIO ***
    Siren class: Gaussian embeddings centered at +0.5 per dimension.
    Non-siren:   Gaussian embeddings centered at -0.5 per dimension.

    This is only used to demonstrate the training pipeline when
    UrbanSound8K is not available.

    Args:
        n_siren:       Number of synthetic siren samples.
        n_non_siren:   Number of synthetic non-siren samples.
        embedding_dim: Feature dimensionality (1024 for YAMNet).
        seed:          Random seed for reproducibility.
        fold_assignments: Optional dict of sample_index -> fold_number (1-10).
                          If None, folds are assigned round-robin.

    Returns:
        (X, y, folds): arrays of shape (n_total, 1024), (n_total,), (n_total,).
    """
    rng = np.random.RandomState(seed)
    X_siren = rng.randn(n_siren, embedding_dim).astype(np.float32) + 0.5
    X_non_siren = rng.randn(n_non_siren, embedding_dim).astype(np.float32) - 0.5
    X = np.vstack([X_siren, X_non_siren])
    y = np.array([1] * n_siren + [0] * n_non_siren, dtype=np.int32)

    # Assign folds 1-10 round-robin
    n_total = len(y)
    folds = np.array([(i % 10) + 1 for i in range(n_total)], dtype=np.int32)

    # Shuffle
    idx = rng.permutation(n_total)
    X, y, folds = X[idx], y[idx], folds[idx]

    logger.info(
        "[classifier] Generated SYNTHETIC dataset: %d siren, %d non-siren "
        "(NOT REAL AUDIO DATA)",
        n_siren, n_non_siren,
    )
    return X, y, folds
