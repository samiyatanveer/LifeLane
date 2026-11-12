"""
demo_siren_detect.py — Live siren detection demo using the trained LifeLane model.

Runs the full inference pipeline on audio files:
  WAV file -> scipy resample to 16kHz -> YAMNet 1024-dim embedding -> classifier -> SIREN / NOT SIREN

Usage:
    # Test on a specific file:
    python scripts/demo_siren_detect.py --file data/raw/karachi/ambulance/ambulance1.wav

    # Test on a whole folder (up to --limit files):
    python scripts/demo_siren_detect.py --folder data/raw/karachi/ambulance --limit 5
    python scripts/demo_siren_detect.py --folder data/raw/karachi/road_noise --limit 5
    python scripts/demo_siren_detect.py --folder data/raw/sireNNet/ambulance --limit 5
    python scripts/demo_siren_detect.py --folder data/raw/sireNNet/traffic   --limit 5

    # Quick smoke test (no args — picks 3 files automatically):
    python scripts/demo_siren_detect.py
"""
import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np

# Ensure src/ is on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

MODEL_PATH  = ROOT / "models" / "siren_classifier.joblib"
SCALER_PATH = ROOT / "models" / "siren_scaler.joblib"


def load_model():
    """Load via SirenClassifier wrapper which knows the trained threshold."""
    from lifelane_engine.audio.siren_classifier import SirenClassifier
    if not MODEL_PATH.exists():
        print(f"[ERROR] Model not found at {MODEL_PATH}")
        print("        Run:  python -m lifelane_engine.main --mode train-audio-real")
        sys.exit(1)
    clf = SirenClassifier.load(str(MODEL_PATH), str(SCALER_PATH))
    print(f"[OK] Model loaded  — threshold={clf.threshold:.3f}")
    return clf


def load_yamnet():
    """Load real YAMNet or fall back to MockYAMNet with a warning."""
    try:
        from lifelane_engine.audio.feature_extractor import RealYAMNet
        print("[OK] Loading YAMNet (TF Hub) — first call uses local cache...")
        yn = RealYAMNet()
        print("[OK] YAMNet ready (1024-dim frozen embeddings)")
        return yn, True
    except Exception as e:
        print(f"[WARN] RealYAMNet failed ({e})")
        print("       Falling back to MockYAMNet — results are RANDOM, not real inference!")
        from lifelane_engine.audio.feature_extractor import MockYAMNet
        return MockYAMNet(), False


def preprocess(file_path: str, target_sr: int = 16000):
    """Load WAV, convert to 16 kHz mono float32."""
    import soundfile as sf
    from math import gcd
    from scipy.signal import resample_poly

    audio, sr = sf.read(file_path, always_2d=False)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    audio = audio.astype(np.float32)
    if sr != target_sr:
        g    = gcd(int(target_sr), int(sr))
        up   = int(target_sr) // g
        down = int(sr) // g
        audio = resample_poly(audio, up, down).astype(np.float32)
    return audio, sr


def predict_file(file_path: str, clf, yamnet, real_yamnet: bool) -> dict:
    t0 = time.time()
    fname = os.path.basename(file_path)

    # 1. Preprocess
    try:
        audio, orig_sr = preprocess(file_path)
    except Exception as e:
        return {"file": fname, "error": str(e)}

    duration_s = len(audio) / 16000

    # 2. Embed
    if real_yamnet:
        emb = yamnet.mean_embedding(audio)
    else:
        emb = yamnet.mean_embedding(audio, filename=fname)

    # 3. Classify using SirenClassifier (uses its stored threshold)
    prob, is_siren = clf.predict(emb)   # returns (raw_score, is_siren)
    latency_ms = (time.time() - t0) * 1000

    return {
        "file":       fname,
        "duration_s": round(duration_s, 2),
        "p_siren":    round(float(prob), 4),
        "threshold":  clf.threshold,
        "prediction": "🚨 SIREN" if is_siren else "✅ NOT SIREN",
        "latency_ms": round(latency_ms, 1),
    }


def run_demo(files: list, clf, yamnet, real_yamnet: bool):
    print()
    print("=" * 65)
    print("  LifeLane Siren Detection Demo")
    if not real_yamnet:
        print("  ⚠️  MOCK MODE — predictions are random (no TF available)")
    print("=" * 65)
    print(f"  {'File':<30} {'P(siren)':>8}  {'Result':<14}  {'ms':>6}")
    print("-" * 65)

    total = 0
    for fpath in files:
        result = predict_file(fpath, clf, yamnet, real_yamnet)
        if "error" in result:
            print(f"  {'ERROR: ' + result['file']:<48}  {result['error']}")
            continue
        print(
            f"  {result['file']:<30}  {result['p_siren']:>6.3f}  "
            f"{result['prediction']:<14}  {result['latency_ms']:>5.0f}ms"
        )
        total += 1

    print("=" * 65)
    print(f"  Threshold used: {clf.threshold:.3f}")
    print(f"  Files tested:   {total}")
    print()


def auto_pick_files(limit_per_class: int = 3) -> list:
    """Auto-pick a few ambulance + road/traffic files for a quick sanity check."""
    files = []
    candidates = [
        (ROOT / "data" / "raw" / "karachi" / "ambulance",    "ambulance"),
        (ROOT / "data" / "raw" / "karachi" / "road_noise",   "road_noise"),
        (ROOT / "data" / "raw" / "sireNNet" / "ambulance",   "ambulance"),
        (ROOT / "data" / "raw" / "sireNNet" / "traffic",     "traffic"),
    ]
    for folder, label in candidates:
        if folder.exists():
            wavs = sorted(folder.glob("*.wav"))[:limit_per_class]
            files.extend(str(w) for w in wavs)
    return files


def main():
    parser = argparse.ArgumentParser(description="LifeLane siren detection demo")
    parser.add_argument("--file",   help="Single WAV file to test")
    parser.add_argument("--folder", help="Folder of WAV files to test")
    parser.add_argument("--limit",  type=int, default=10, help="Max files from folder (default 10)")
    args = parser.parse_args()

    clf = load_model()
    yamnet, real_yamnet = load_yamnet()

    if args.file:
        files = [args.file]
    elif args.folder:
        folder = Path(args.folder)
        files  = [str(f) for f in sorted(folder.glob("*.wav"))[:args.limit]]
        if not files:
            print(f"[ERROR] No WAV files found in {folder}")
            sys.exit(1)
    else:
        print("[INFO] No --file or --folder specified — running auto demo...")
        files = auto_pick_files(limit_per_class=3)
        if not files:
            print("[ERROR] No dataset files found. Extract datasets first.")
            sys.exit(1)

    run_demo(files, clf, yamnet, real_yamnet)


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
