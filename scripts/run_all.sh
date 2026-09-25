#!/usr/bin/env bash
# Full pipeline: Phase 1 data -> Phase 2 SFT + DAgger -> evaluation.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
OUT=${OUT:-runs/sft}
$PY -m freecad_s1.datagen --out data/train --episodes 8000 16000 24000 --workers 8 --seed 0
$PY -m freecad_s1.datagen --out data/test --episodes 500 1000 1500 --workers 8 --seed 1
$PY -m freecad_s1.train_sft --data data/train --out "$OUT" --epochs 4 --dagger-rounds 2 --dagger-episodes 400 --dagger-epochs 2
$PY -m freecad_s1.evaluate --ckpt "$OUT/last.pt" --data data/test --episodes 100 --out "$OUT/eval.json"
$PY -m freecad_s1.evaluate --ckpt "$OUT/last.pt" --episodes 100 --perturb 0.2 --out "$OUT/eval_perturb.json"
