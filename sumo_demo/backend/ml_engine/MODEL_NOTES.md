# MODEL_NOTES.md — LifeLane ML Engine (SUMO Demo Integration)

Generated during Step 1 analysis. Source: `C:\Users\hp\Desktop\LifeLane` (read-only).

---

## 1. Siren Classifier

| Field | Value |
|---|---|
| File | `backend/ml_engine/models/siren_classifier.joblib` |
| Type | `sklearn.linear_model.LogisticRegression` |
| Input dim | 128 |
| Classes | `[0, 1]` → 0=non_siren, 1=siren |
| Siren class index | `1` (index of `1` in `clf.classes_`) |
| C | 1.0 |
| solver | lbfgs |
| max_iter | 200 |
| random_state | 42 |

### Audio Preprocessing

**Mock embedding (128-dim)** — no real audio feature extraction:
```python
def _mock_embed(audio_bytes: bytes) -> np.ndarray:
    rng = np.random.default_rng(sum(audio_bytes[:64]) % (2**32))
    return rng.random(128).astype(np.float32)
```

The classifier was trained on **128-dim mock embeddings** (not real YAMNet/MFCC features).
Real YAMNet (1024-dim, requires TensorFlow) exists in SOURCE but was **not** used for training.

**Scaler is applied before classifier** (`StandardScaler` with_mean=True, with_std=True).

**Siren threshold:** `p >= 0.5` → `is_siren = True`

**Tier 1:** 3 consecutive frames with `p >= 0.5`

---

## 2. ETA Regressor

| Field | Value |
|---|---|
| File | `backend/ml_engine/models/eta_model.joblib` |
| Type | `xgboost.XGBRegressor` |
| Input features | 6 (see below) |
| n_estimators | 200 |
| max_depth | 4 |
| learning_rate | 0.1 |
| tree_method | hist |
| random_state | 42 |
| objective | reg:squarederror |

### ETA Feature Order (exact, must not be reordered)

| # | Column | Units | Notes |
|---|---|---|---|
| 0 | `distance_to_junction_m` | metres | SUMO driving distance |
| 1 | `current_speed_ms` | m/s | ambulance speed |
| 2 | `queue_length_vehicles` | vehicles | halted at approach |
| 3 | `time_since_green_s` | seconds | from FSM spent duration |
| 4 | `demand_level_enc` | 0/1/2 | 0=light, 1=medium, 2=heavy |
| 5 | `is_route_A` | 0.0 or 1.0 | 1.0=Route A (J1→J2→hospital) |

---

## 3. Package Versions (trained with)

| Package | Version |
|---|---|
| scikit-learn | 1.9.1 |
| xgboost | 3.4.1 |
| numpy | 2.5.4 |
| joblib | 1.6.0 |
| tensorflow | not used for saved models |

---

## 4. Reported Metrics (from SOURCE reports/)

| Metric | Value | Data Type |
|---|---|---|
| Siren F1 | 1.0 | Synthetic |
| Siren Precision | 1.0 | Synthetic |
| Siren Recall | 1.0 | Synthetic |
| Siren FAR | 0.0 | Synthetic |
| ETA MAE | 5.41 s | Synthetic |
| ETA RMSE | 7.0 s | Synthetic |
| ETA MAPE | 15.98 % | Synthetic |
| ETA Naive baseline MAE | 4.98 s | Synthetic |

> **WARNING:** All metrics are on synthetic (randomly generated) data, not real audio or real SUMO runs.
> The siren classifier is overfit to synthetic Gaussian noise clusters.
> Model outputs in the demo are labelled `REAL_MODEL` (correct code path) but are **not production-grade**.

---

## 5. What the SUMO Demo Does

1. Each simulation step, for corridor junctions J1 and J2:
   - Builds ETA feature dict from live TraCI data
   - Calls `ModelService.predict_eta()` → stores `ml_eta_s` in junction state
   - Generates synthetic audio frame bytes (siren energy ∝ ambulance proximity)
   - Calls `ModelService.siren_prob()` → accumulates 3-frame window for Tier-1
   - Stores `siren_p`, `t1_active`, `ml_eta_s`, `ml_latency_ms` in `sim_state.json`
2. On model failure → `source="FALLBACK"`, existing TraCI ETA/distance values unchanged, signals unaffected.
3. Frontend reads new keys from the existing WebSocket stream.
