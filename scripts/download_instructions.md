# UrbanSound8K Download Instructions

## IMPORTANT

UrbanSound8K is NOT downloaded automatically. You must download it manually and place it
in the correct directory before running Phase 4 (audio ML) components.

## Download

1. Visit: https://zenodo.org/records/1203745
2. Download: `UrbanSound8K.tar.gz` (≈ 6 GB)
3. Accept the dataset license terms.

## Placement

Extract the archive so the directory structure is:

```
data/
└── raw/
    └── UrbanSound8K/
        ├── metadata/
        │   └── UrbanSound8K.csv
        └── audio/
            ├── fold1/
            ├── fold2/
            ...
            └── fold10/
```

The project root `config/settings.yaml` points to:
- `data/raw/UrbanSound8K/metadata/UrbanSound8K.csv`
- `data/raw/UrbanSound8K/audio/`

## Dataset Citation

J. Salamon, C. Jacoby and J. P. Bello, "A Dataset and Taxonomy for Urban Sound Research",
22nd ACM international conference on Multimedia, Orlando USA, Nov. 2014.

## Important Notes

- UrbanSound8K contains a `siren` class (label 8) among 10 urban sound classes.
- LifeLane uses this class to detect siren-type sounds.
- **UrbanSound8K does NOT identify the emergency-vehicle type.**
  LifeLane treats siren detection as supporting evidence only —
  a separate authorized ambulance request is always required before signal priority.
- The official fold IDs must be preserved; do not shuffle across folds.
- This dataset is for educational/research use only.

## Phase 1 Note

Phase 1 (current) does NOT require UrbanSound8K.
The mock POC runs entirely with synthetic/mock audio scores.
Download only when you are ready to start Phase 4.

