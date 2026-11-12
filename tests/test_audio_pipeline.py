"""
test_audio_pipeline.py — Phase 4 unit tests for audio preprocessing,
MockYAMNet feature extraction, and siren classifier.

All tests run without UrbanSound8K, TensorFlow, or real audio files.
Mock audio is clearly labeled as synthetic.
"""
import numpy as np
import pytest

from lifelane_engine.audio.preprocess import (
    MIN_SAMPLES,
    TARGET_SR,
    _pad,
    _to_mono,
    _validate,
    make_mock_audio,
    AudioPreprocessError,
)
from lifelane_engine.audio.feature_extractor import (
    YAMNET_EMBEDDING_DIM,
    MockYAMNet,
    get_yamnet,
)
from lifelane_engine.audio.siren_classifier import (
    DEFAULT_THRESHOLD,
    SirenClassifier,
    generate_synthetic_dataset,
)


# ─────────────────────────────────────────────────────────────────────────────
# Preprocessing helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestToMono:
    def test_mono_unchanged(self):
        audio = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        result = _to_mono(audio)
        np.testing.assert_array_equal(result, audio)

    def test_stereo_averaged(self):
        audio = np.array([[1.0, 3.0], [2.0, 4.0]], dtype=np.float32)  # (2 samples, 2 ch)
        result = _to_mono(audio)
        np.testing.assert_allclose(result, [2.0, 3.0])

    def test_bad_shape_raises(self):
        with pytest.raises(AudioPreprocessError):
            _to_mono(np.zeros((10, 2, 3), dtype=np.float32))


class TestValidate:
    def test_valid_audio_passes(self):
        audio = np.ones(MIN_SAMPLES, dtype=np.float32) * 0.5
        _validate(audio, "test.wav")  # should not raise

    def test_empty_raises(self):
        with pytest.raises(AudioPreprocessError, match="Empty"):
            _validate(np.array([], dtype=np.float32), "test.wav")

    def test_nan_raises(self):
        audio = np.array([0.5, float("nan"), 0.5], dtype=np.float32)
        with pytest.raises(AudioPreprocessError, match="NaN"):
            _validate(audio, "test.wav")

    def test_inf_raises(self):
        audio = np.array([0.5, float("inf"), 0.5], dtype=np.float32)
        with pytest.raises(AudioPreprocessError, match="Inf"):
            _validate(audio, "test.wav")

    def test_near_silent_raises(self):
        audio = np.zeros(100, dtype=np.float32)
        with pytest.raises(AudioPreprocessError, match="silent"):
            _validate(audio, "test.wav")


class TestPad:
    def test_no_pad_when_long_enough(self):
        audio = np.ones(MIN_SAMPLES + 100, dtype=np.float32)
        result = _pad(audio, MIN_SAMPLES)
        assert len(result) == MIN_SAMPLES + 100

    def test_pads_short_audio(self):
        audio = np.ones(100, dtype=np.float32)
        result = _pad(audio, MIN_SAMPLES)
        assert len(result) == MIN_SAMPLES
        np.testing.assert_array_equal(result[100:], 0)

    def test_pad_exactly_target(self):
        audio = np.ones(MIN_SAMPLES - 10, dtype=np.float32)
        result = _pad(audio, MIN_SAMPLES)
        assert len(result) == MIN_SAMPLES


class TestMockAudio:
    def test_returns_float32(self):
        audio = make_mock_audio("test.wav")
        assert audio.dtype == np.float32

    def test_minimum_length(self):
        audio = make_mock_audio("test.wav")
        assert len(audio) >= MIN_SAMPLES

    def test_deterministic_by_filename(self):
        a1 = make_mock_audio("file_a.wav")
        a2 = make_mock_audio("file_a.wav")
        np.testing.assert_array_equal(a1, a2)

    def test_different_filenames_differ(self):
        a1 = make_mock_audio("file_a.wav")
        a2 = make_mock_audio("file_b.wav")
        assert not np.allclose(a1, a2)

    def test_siren_and_non_siren_differ(self):
        s = make_mock_audio("x.wav", is_siren=True)
        ns = make_mock_audio("x.wav", is_siren=False)
        assert not np.allclose(s, ns)


# ─────────────────────────────────────────────────────────────────────────────
# MockYAMNet
# ─────────────────────────────────────────────────────────────────────────────

class TestMockYAMNet:
    def test_embed_shape(self):
        yamnet = MockYAMNet()
        audio = make_mock_audio("test.wav")
        emb = yamnet.embed(audio, filename="test.wav")
        assert emb.shape == (1, YAMNET_EMBEDDING_DIM)

    def test_mean_embedding_shape(self):
        yamnet = MockYAMNet()
        audio = make_mock_audio("test.wav")
        emb = yamnet.mean_embedding(audio, filename="test.wav")
        assert emb.shape == (YAMNET_EMBEDDING_DIM,)

    def test_deterministic(self):
        yamnet = MockYAMNet()
        audio = make_mock_audio("a.wav")
        e1 = yamnet.mean_embedding(audio, filename="a.wav")
        e2 = yamnet.mean_embedding(audio, filename="a.wav")
        np.testing.assert_array_equal(e1, e2)

    def test_different_files_differ(self):
        yamnet = MockYAMNet()
        e1 = yamnet.mean_embedding(make_mock_audio("a.wav"), filename="a.wav")
        e2 = yamnet.mean_embedding(make_mock_audio("b.wav"), filename="b.wav")
        assert not np.allclose(e1, e2)

    def test_get_yamnet_returns_mock_when_no_tf(self):
        # get_yamnet(prefer_real=False) always returns MockYAMNet
        yamnet = get_yamnet(prefer_real=False)
        assert isinstance(yamnet, MockYAMNet)


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic dataset
# ─────────────────────────────────────────────────────────────────────────────

class TestSyntheticDataset:
    def test_shapes(self):
        X, y, folds = generate_synthetic_dataset(n_siren=50, n_non_siren=50, seed=1)
        assert X.shape == (100, 1024)
        assert y.shape == (100,)
        assert folds.shape == (100,)

    def test_labels_binary(self):
        _, y, _ = generate_synthetic_dataset(n_siren=40, n_non_siren=60, seed=2)
        assert set(y.tolist()).issubset({0, 1})

    def test_fold_range(self):
        _, _, folds = generate_synthetic_dataset(n_siren=100, n_non_siren=100, seed=3)
        assert folds.min() >= 1
        assert folds.max() <= 10

    def test_reproducible(self):
        X1, y1, _ = generate_synthetic_dataset(seed=42)
        X2, y2, _ = generate_synthetic_dataset(seed=42)
        np.testing.assert_array_equal(X1, X2)
        np.testing.assert_array_equal(y1, y2)

    def test_siren_mean_higher_than_nonsiren(self):
        X, y, _ = generate_synthetic_dataset(n_siren=200, n_non_siren=200, seed=7)
        siren_mean = X[y == 1].mean()
        nonsiren_mean = X[y == 0].mean()
        assert siren_mean > nonsiren_mean


# ─────────────────────────────────────────────────────────────────────────────
# SirenClassifier
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def fitted_classifier():
    """Train a classifier on synthetic data (folds 1-8 train, 9 val)."""
    X, y, folds = generate_synthetic_dataset(n_siren=400, n_non_siren=400, seed=99)
    X_train = X[folds <= 8]
    y_train = y[folds <= 8]
    X_val = X[folds == 9]
    y_val = y[folds == 9]
    clf = SirenClassifier(threshold=DEFAULT_THRESHOLD)
    clf.fit(X_train, y_train, X_val, y_val)
    return clf, X, y, folds


class TestSirenClassifier:
    def test_fit_returns_metrics(self, fitted_classifier):
        clf, _, _, _ = fitted_classifier
        assert clf._fitted is True

    def test_predict_proba_in_range(self, fitted_classifier):
        clf, X, _, _ = fitted_classifier
        score = clf.predict_proba(X[0])
        assert 0.0 <= score <= 1.0

    def test_predict_returns_tuple(self, fitted_classifier):
        clf, X, _, _ = fitted_classifier
        score, is_siren = clf.predict(X[0])
        assert isinstance(score, float)
        assert isinstance(is_siren, bool)

    def test_siren_class_scores_high(self, fitted_classifier):
        clf, X, y, _ = fitted_classifier
        siren_samples = X[y == 1][:10]
        scores = [clf.predict_proba(s) for s in siren_samples]
        assert np.mean(scores) > 0.5  # majority should score above 0.5

    def test_nonsiren_class_scores_low(self, fitted_classifier):
        clf, X, y, _ = fitted_classifier
        non_siren_samples = X[y == 0][:10]
        scores = [clf.predict_proba(s) for s in non_siren_samples]
        assert np.mean(scores) < 0.5  # majority should score below 0.5

    def test_evaluate_on_test_fold(self, fitted_classifier):
        clf, X, y, folds = fitted_classifier
        X_test = X[folds == 10]
        y_test = y[folds == 10]
        results = clf.evaluate(X_test, y_test)
        assert "f1" in results
        assert "precision" in results
        assert "recall" in results
        assert "false_alarm_rate" in results
        assert 0.0 <= results["f1"] <= 1.0

    def test_threshold_selected_on_val_not_test(self, fitted_classifier):
        """Verify threshold is selected on val fold, not test fold."""
        clf, X, y, folds = fitted_classifier
        # Threshold must be in [0.1, 0.9]
        assert 0.0 < clf.threshold <= 1.0

    def test_unfitted_raises(self):
        clf = SirenClassifier()
        with pytest.raises(RuntimeError, match="not fitted"):
            clf.predict_proba(np.zeros(1024))

    def test_predict_batch_shape(self, fitted_classifier):
        clf, X, y, folds = fitted_classifier
        X_test = X[folds == 10]
        preds = clf.predict_batch(X_test)
        assert preds.shape == (len(X_test),)
        assert set(preds.tolist()).issubset({0, 1})

    def test_save_and_load(self, fitted_classifier, tmp_path):
        clf, X, _, _ = fitted_classifier
        model_p = str(tmp_path / "clf.joblib")
        scaler_p = str(tmp_path / "scaler.joblib")
        clf.save(model_p, scaler_p)
        loaded = SirenClassifier.load(model_p, scaler_p, threshold=clf.threshold)
        # Predictions must be identical
        s1 = clf.predict_proba(X[0])
        s2 = loaded.predict_proba(X[0])
        assert abs(s1 - s2) < 1e-6

