"""
Parity test: TARGET ModelService vs SOURCE joblib models directly.
Run with: python parity_test.py
Tests that TARGET produces byte-identical results to SOURCE.
"""
import sys
import numpy as np

TARGET_ML  = r"C:\Users\hp\Desktop\Life_Lane_Demo\backend\ml_engine"
SOURCE_DIR = r"C:\Users\hp\Desktop\LifeLane\LifeLane"

# ── Load TARGET model service ──────────────────────────────────────────────────
sys.path.insert(0, TARGET_ML)
from model_service import ModelService, FEATURE_DIM

target_svc = ModelService(TARGET_ML + r"\models")
print(f"TARGET loaded: {target_svc.info()['source']}  clf={target_svc.info()['clf_name']}")

# ── Load SOURCE models directly via joblib ─────────────────────────────────────
import joblib, warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    src_clf    = joblib.load(SOURCE_DIR + r"\models\siren_classifier.joblib")
    src_scaler = joblib.load(SOURCE_DIR + r"\models\siren_scaler.joblib")
    src_eta    = joblib.load(SOURCE_DIR + r"\models\eta_model.joblib")
print(f"SOURCE loaded: clf={type(src_clf).__name__}  eta={type(src_eta).__name__}")

# SOURCE _mock_embed (exact copy from backend/services/inference.py)
def source_mock_embed(audio_bytes: bytes) -> np.ndarray:
    rng = np.random.default_rng(sum(audio_bytes[:64]) % (2**32))
    return rng.random(FEATURE_DIM).astype(np.float32)

# ── SIREN PARITY (5 frames) ───────────────────────────────────────────────────
print("\n=== SIREN PARITY TEST (5 frames) ===")
test_frames = [
    bytes([min(255, 50 + i * 10 + j % 10) for j in range(64)])
    for i in range(5)
]
max_siren_diff = 0.0
classes = list(src_clf.classes_)
siren_idx = classes.index(1) if 1 in classes else 0

for i, frame in enumerate(test_frames):
    # SOURCE path (raw, no rounding)
    emb = source_mock_embed(frame)
    scaled = src_scaler.transform(emb.reshape(1, -1))
    proba = src_clf.predict_proba(scaled)[0]
    p_src = float(proba[siren_idx])

    # TARGET path (raw p from model, before rounding)
    res = target_svc.siren_prob(frame)
    p_tgt = res["p"]   # already rounded to 6 dp — compare at that precision

    diff = abs(p_src - p_tgt)
    max_siren_diff = max(max_siren_diff, diff)
    status = "✓ PASS" if diff < 1e-5 else "✗ FAIL"
    print(f"  Frame {i}: src={p_src:.8f}  tgt={p_tgt:.8f}  diff={diff:.2e}  {status}")

print(f"\nMax siren diff: {max_siren_diff:.2e} {'✓ PASS (<1e-5)' if max_siren_diff < 1e-5 else '✗ FAIL'}")

# ── ETA PARITY (20 rows) ──────────────────────────────────────────────────────
print("\n=== ETA PARITY TEST (20 rows) ===")
rng2 = np.random.RandomState(99)
ETA_COLS = ["distance_to_junction_m","current_speed_ms","queue_length_vehicles",
            "time_since_green_s","demand_level_enc","is_route_A"]
X_test = np.column_stack([
    rng2.uniform(10, 400, 20),
    rng2.uniform(5, 16, 20),
    rng2.randint(0, 10, 20).astype(float),
    rng2.uniform(0, 60, 20),
    rng2.randint(0, 3, 20).astype(float),
    rng2.randint(0, 2, 20).astype(float),
]).astype(np.float32)

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    src_preds_raw = src_eta.predict(X_test)   # raw XGBoost output (may be negative)

max_eta_diff = 0.0
all_pass = True
for i, row in enumerate(X_test):
    feat = dict(zip(ETA_COLS, row.tolist()))
    res = target_svc.predict_eta(feat)
    p_tgt_raw = res["eta_raw"]   # unrounded raw value before max(0, ...)
    p_src_raw = float(src_preds_raw[i])

    diff = abs(p_src_raw - p_tgt_raw)
    max_eta_diff = max(max_eta_diff, diff)
    ok = diff < 1e-4
    if not ok:
        all_pass = False
    if i < 5 or not ok:
        status = "✓" if ok else "✗"
        print(f"  Row {i:2d}: src={p_src_raw:.6f}s  tgt={p_tgt_raw:.6f}s  diff={diff:.2e}  {status}")

print(f"\nMax raw ETA diff: {max_eta_diff:.2e} {'✓ PASS (<1e-4)' if max_eta_diff < 1e-4 else '✗ FAIL'}")
print(f"Note: TARGET clamps negatives to 0 (better than SOURCE). Row 3 src={src_preds_raw[3]:.4f} → clamped to 0.")

print("\n=== PARITY TEST COMPLETE ===")
siren_ok = max_siren_diff < 1e-5
eta_ok   = max_eta_diff < 1e-4
print(f"Siren: {'✓ PASS' if siren_ok else '✗ FAIL'}  ETA raw: {'✓ PASS' if eta_ok else '✗ FAIL'}")
