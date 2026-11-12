"""
extract_datasets.py — Extract SireNNet and UrbanSound8K to data/raw/.
Resumable: skips files that already exist. Never modifies originals.
"""
import zipfile, tarfile, io, os, sys, time

PROJECT_ROOT = r"D:\LIFELANE"
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")

def extract_sirenet():
    outer_zip = os.path.join(PROJECT_ROOT, "sireNNet-Emergency Vehicle Siren Classification Dataset For Urban Applications.zip")
    out_dir = os.path.join(RAW_DIR, "sireNNet")
    os.makedirs(out_dir, exist_ok=True)

    print("[SireNNet] Opening outer zip...")
    outer = zipfile.ZipFile(outer_zip)
    inner_bytes = outer.read("sireNNet-Emergency Vehicle Siren Classification Dataset For Urban Applications/sireNNet.zip")
    inner = zipfile.ZipFile(io.BytesIO(inner_bytes))

    members = [n for n in inner.namelist() if n.endswith(".wav")]
    print(f"[SireNNet] {len(members)} WAV files to extract to {out_dir}")

    skipped = 0
    extracted = 0
    for i, name in enumerate(members):
        # Strip leading "sireNNet/" prefix
        rel = "/".join(name.split("/")[1:])  # e.g. "ambulance/sound_1.wav"
        dest = os.path.join(out_dir, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            skipped += 1
            continue
        with open(dest, "wb") as f:
            f.write(inner.read(name))
        extracted += 1
        if (extracted + skipped) % 200 == 0:
            print(f"  {extracted + skipped}/{len(members)} done ({extracted} new, {skipped} skipped)...")

    inner.close()
    outer.close()
    print(f"[SireNNet] Done. Extracted={extracted}, Skipped(already existed)={skipped}")


def extract_urbansound8k():
    tar_path = os.path.join(PROJECT_ROOT, "UrbanSound8K.tar.gz")
    out_dir = os.path.join(RAW_DIR, "UrbanSound8K")
    os.makedirs(out_dir, exist_ok=True)

    print("[US8K] Opening archive (streaming — may take a few minutes for 7 GB)...")
    t0 = time.time()
    tf = tarfile.open(tar_path, "r:gz")

    members = tf.getmembers()
    wav_members = [m for m in members if m.name.endswith(".wav")]
    small_members = [m for m in members if not m.isdir() and not m.name.endswith(".wav")]
    print(f"[US8K] {len(wav_members)} WAV files + {len(small_members)} metadata files")

    # Extract metadata files first (small)
    for m in small_members:
        rel = "/".join(m.name.split("/")[1:])
        if not rel:
            continue
        dest = os.path.join(out_dir, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if not os.path.exists(dest):
            f = tf.extractfile(m)
            if f:
                with open(dest, "wb") as out:
                    out.write(f.read())
    print("[US8K] Metadata extracted.")

    skipped = 0
    extracted = 0
    for i, m in enumerate(wav_members):
        rel = "/".join(m.name.split("/")[1:])  # strip "UrbanSound8K/"
        dest = os.path.join(out_dir, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            skipped += 1
        else:
            f = tf.extractfile(m)
            if f:
                with open(dest, "wb") as out:
                    out.write(f.read())
                extracted += 1
        if (i + 1) % 500 == 0:
            elapsed = time.time() - t0
            pct = (i + 1) / len(wav_members) * 100
            eta = elapsed / (i + 1) * (len(wav_members) - i - 1)
            print(f"  {i+1}/{len(wav_members)} ({pct:.1f}%) — elapsed {elapsed:.0f}s, ETA ~{eta:.0f}s | new={extracted}, skipped={skipped}")

    tf.close()
    print(f"[US8K] Done. Extracted={extracted}, Skipped={skipped}. Total time: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    print("=== LifeLane Dataset Extraction ===")
    print(f"Output directory: {RAW_DIR}\n")

    if "--sirenet" in sys.argv or len(sys.argv) == 1:
        extract_sirenet()

    if "--us8k" in sys.argv or len(sys.argv) == 1:
        extract_urbansound8k()

    print("\n=== Extraction complete ===")
    # Verify counts
    for ds in ["sireNNet", "UrbanSound8K"]:
        d = os.path.join(RAW_DIR, ds)
        count = sum(1 for root, _, files in os.walk(d) for f in files if f.endswith(".wav"))
        print(f"  {ds}: {count} WAV files in {d}")

