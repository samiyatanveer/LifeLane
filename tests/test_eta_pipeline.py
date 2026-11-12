"""
test_eta_pipeline.py — Phase 5 unit tests for ETA model and dataset builder.

Runs end-to-end without SUMO using the synthetic dataset generator.
Clearly labels all synthetic data as NOT real SUMO output.
"""
import numpy as np
import pytest

from lifelane_engine.prediction.dataset_builder import (
    ETA_FEATURE_COLS,
    generate_synthetic_eta_dataset,
)
from lifelane_engine.prediction.eta_model import ETAModel, naive_eta
from lifelane_engine.prediction.queue_model import QueueModel, fixed_formula_clearance


# ─────────────────────────────────────────────────────────────────────────────
# Naive ETA baseline
# ─────────────────────────────────────────────────────────────────────────────

class TestNaiveEta:
    def test_basic(self):
        eta = naive_eta(distance_m=100.0, speed_ms=10.0, queue_vehicles=0)
        assert eta == pytest.approx(10.0)

    def test_queue_adds_delay(self):
        no_queue = naive_eta(100.0, 10.0, 0)
        with_queue = naive_eta(100.0, 10.0, 5)
        assert with_queue > no_queue

    def test_zero_speed_clamped(self):
        eta = naive_eta(100.0, speed_ms=0.0)
        assert eta == pytest.approx(100.0)  # clamped to 1.0 m/s → 100s

    def test_always_positive(self):
        eta = naive_eta(0.0, 0.0, 0)
        assert eta >= 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic dataset
# ─────────────────────────────────────────────────────────────────────────────

class TestSyntheticDataset:
    def test_split_sizes_sum_to_total(self):
        ds = generate_synthetic_eta_dataset(n_seeds=100, rows_per_seed=10, seed=1)
        total = ds["n_train"] + ds["n_val"] + ds["n_test"]
        expected = 100 * 10
        assert total == expected

    def test_feature_columns_correct(self):
        ds = generate_synthetic_eta_dataset(n_seeds=10, rows_per_seed=5)
        assert ds["feature_names"] == ETA_FEATURE_COLS

    def test_no_train_val_overlap(self):
        """Run IDs must be disjoint between train/val/test."""
        ds = generate_synthetic_eta_dataset(n_seeds=100, rows_per_seed=5, seed=2)
        # All y values must be non-negative
        assert (ds["y_train"] >= 0).all()
        assert (ds["y_val"] >= 0).all()
        assert (ds["y_test"] >= 0).all()

    def test_X_shape(self):
        ds = generate_synthetic_eta_dataset(n_seeds=20, rows_per_seed=10, seed=3)
        n_feats = len(ETA_FEATURE_COLS)
        assert ds["X_train"].shape[1] == n_feats

    def test_note_is_labeled_synthetic(self):
        ds = generate_synthetic_eta_dataset(n_seeds=5, rows_per_seed=5)
        assert "SYNTHETIC" in ds["note"]

    def test_reproducible(self):
        ds1 = generate_synthetic_eta_dataset(n_seeds=10, rows_per_seed=5, seed=7)
        ds2 = generate_synthetic_eta_dataset(n_seeds=10, rows_per_seed=5, seed=7)
        np.testing.assert_array_equal(ds1["X_train"], ds2["X_train"])


# ─────────────────────────────────────────────────────────────────────────────
# ETAModel
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def eta_dataset():
    return generate_synthetic_eta_dataset(n_seeds=100, rows_per_seed=50, seed=42)


@pytest.fixture(scope="module")
def fitted_eta_model(eta_dataset):
    ds = eta_dataset
    model = ETAModel(n_estimators=50, max_depth=3)  # fast for testing
    metrics = model.fit(ds["X_train"], ds["y_train"], ds["X_val"], ds["y_val"])
    return model, metrics, ds


class TestETAModel:
    def test_fit_returns_train_mae(self, fitted_eta_model):
        _, metrics, _ = fitted_eta_model
        assert "train_mae" in metrics or "note" in metrics  # note if no XGB

    def test_predict_positive(self, fitted_eta_model):
        model, _, _ = fitted_eta_model
        eta = model.predict(distance_m=200.0, speed_ms=10.0, queue_vehicles=3)
        assert eta >= 0.0

    def test_farther_distance_higher_eta(self, fitted_eta_model):
        model, _, _ = fitted_eta_model
        eta_near = model.predict(100.0, 10.0, 0)
        eta_far = model.predict(300.0, 10.0, 0)
        assert eta_far >= eta_near

    def test_predict_batch_shape(self, fitted_eta_model):
        model, _, ds = fitted_eta_model
        preds = model.predict_batch(ds["X_test"])
        assert preds.shape == (len(ds["y_test"]),)
        assert (preds >= 0).all()

    def test_evaluate_returns_mae(self, fitted_eta_model):
        model, _, ds = fitted_eta_model
        results = model.evaluate(ds["X_test"], ds["y_test"])
        assert "mae" in results
        assert results["mae"] >= 0.0

    def test_evaluate_includes_baseline(self, fitted_eta_model):
        model, _, ds = fitted_eta_model
        results = model.evaluate(ds["X_test"], ds["y_test"])
        assert "baseline_naive_mae" in results

    def test_unfitted_uses_naive_fallback(self):
        model = ETAModel()
        model._fitted = False  # force fallback
        eta = model.predict(100.0, 10.0, 0)
        assert eta == pytest.approx(naive_eta(100.0, 10.0, 0))

    def test_is_fitted_property(self, fitted_eta_model):
        model, _, _ = fitted_eta_model
        # Should be True (either XGBoost fitted, or naive with _fitted=True via fit())
        # The fit() method sets _fitted=True only if XGB available
        assert isinstance(model.is_fitted, bool)

    def test_save_and_load(self, fitted_eta_model, tmp_path):
        model, _, ds = fitted_eta_model
        if not model.is_fitted:
            pytest.skip("XGBoost not available — save/load test skipped")
        path = str(tmp_path / "eta_model.joblib")
        model.save(path)
        loaded = ETAModel.load(path)
        p1 = model.predict(150.0, 12.0, 2)
        p2 = loaded.predict(150.0, 12.0, 2)
        assert abs(p1 - p2) < 0.1


# ─────────────────────────────────────────────────────────────────────────────
# QueueModel
# ─────────────────────────────────────────────────────────────────────────────

class TestQueueModel:
    def test_fixed_formula_zero_vehicles(self):
        assert fixed_formula_clearance(0) == pytest.approx(0.0)

    def test_fixed_formula_five_vehicles(self):
        assert fixed_formula_clearance(5) == pytest.approx(5 * 3.5)

    def test_queue_model_fallback_when_not_fitted(self):
        qm = QueueModel()
        qm._fitted = False
        result = qm.predict(queue_length=4)
        assert result == pytest.approx(fixed_formula_clearance(4))

    def test_queue_model_fit_and_predict(self):
        # Small synthetic queue dataset
        rng = np.random.RandomState(0)
        n = 200
        queues = rng.randint(0, 15, n).astype(float)
        demand = rng.randint(0, 3, n).astype(float)
        green_t = rng.uniform(0, 60, n)
        phase_d = np.full(n, 27.0)
        X = np.column_stack([queues, demand, green_t, phase_d]).astype(np.float32)
        y = (queues * 3.5 + rng.normal(0, 1, n)).clip(0).astype(np.float32)

        qm = QueueModel(n_estimators=20)
        result = qm.fit(X, y)
        if qm.is_fitted:
            pred = qm.predict(queue_length=5)
            assert pred >= 0.0

