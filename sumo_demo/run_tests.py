#!/usr/bin/env python3
"""
LifeLane headless test runner.
Runs traci_controller.py 5 times with seeds 1, 7, 21, 99, 123.
Since SUMO random seed is set via --seed CLI arg, we patch the controller
to pass --seed to SUMO for each run.
Captures stdout and parses the safety report.
"""
import subprocess, sys, re, os
from pathlib import Path

SUMO_DIR   = Path(__file__).parent / "sumo"
CONTROLLER = SUMO_DIR / "traci_controller.py"
SEEDS      = [1, 7, 21, 99, 123]

results = []

for seed in SEEDS:
    print(f"\n{'='*50}")
    print(f"  RUN  seed={seed}")
    print(f"{'='*50}")

    # Patch env to pass seed — we inject SUMO_SEED env var and read it in controller
    env = os.environ.copy()
    env["LIFELANE_SEED"] = str(seed)

    proc = subprocess.run(
        [sys.executable, str(CONTROLLER)],
        capture_output=True, text=True,
        cwd=str(SUMO_DIR),
        env=env,
        timeout=300,
    )
    out = proc.stdout + proc.stderr

    # Parse safety report
    violations = re.search(r"Signal violations.*?:\s+(\d+)", out)
    collisions  = re.search(r"Collisions detected.*?:\s+(\d+)", out)
    min_spd     = re.search(r"min speed.*?:\s+([\d.]+)%", out)

    lead_times = re.findall(r"(J\d):\s+([\d.]+)s lead", out)

    r = {
        "seed": seed,
        "violations": int(violations.group(1)) if violations else "?",
        "collisions":  int(collisions.group(1))  if collisions  else "?",
        "min_spd_pct": float(min_spd.group(1))   if min_spd     else "?",
        "lead_times":  {j: float(t) for j,t in lead_times},
    }
    results.append(r)
    print(out[-3000:])   # tail of output

# ── Summary table ─────────────────────────────────────────────────────────────
print("\n\n" + "="*70)
print("  COMBINED TEST REPORT")
print("="*70)
hdr = f"{'Seed':>6}  {'Violations':>10}  {'Collisions':>10}  {'MinSpd%':>8}  Lead J1/J2/J3"
print(hdr)
print("-"*70)
all_pass = True
for r in results:
    lt = r["lead_times"]
    lead_str = "  ".join(f"{j}={lt.get(j,'?')}s" for j in ["J1","J2","J3"])
    v_ok = r["violations"] == 0
    c_ok = r["collisions"] == 0
    s_ok = isinstance(r["min_spd_pct"], float) and r["min_spd_pct"] >= 70
    l_ok = all(isinstance(lt.get(j), float) and lt[j] >= 3.0 for j in ["J1","J2","J3"] if j in lt)
    ok   = v_ok and c_ok
    if not ok: all_pass = False
    flag = "✓" if ok else "✗"
    print(f"{r['seed']:>6}  {str(r['violations']):>10}  {str(r['collisions']):>10}  "
          f"{str(r['min_spd_pct']):>8}  {lead_str}  {flag}")

print("-"*70)
print(f"  Overall: {'✓ ALL PASS' if all_pass else '✗ SOME FAILURES'}")
print("="*70 + "\n")
