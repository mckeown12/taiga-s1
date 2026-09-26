#!/usr/bin/env bash
# Final model: variant L (randomized positions + coupled ordinals + length-
# invariant numerics + modular done-head policy), SFT + DAgger, evaluated on
# every suite with and without injected random actions.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
OUT=${OUT:-runs/final_L}
$PY -m freecad_s1.train_sft --data data/gen_train --out "$OUT" --epochs 4 \
  --pos-mode rand --ordinal --invariant-numerics --modular --pointer done --index-eval identity ${EXTRA:-} \
  --dagger-rounds 2 --dagger-episodes 400 --dagger-epochs 2
$PY -m freecad_s1.evaluate --ckpt "$OUT/last.pt" --data data/gen_test --episodes 100 \
  --suites iid comp comp2 len len2 len3 --out "$OUT/eval.json"
$PY -m freecad_s1.evaluate --ckpt "$OUT/last.pt" --episodes 100 --perturb 0.2 \
  --suites iid comp comp2 len len2 len3 --out "$OUT/eval_perturb.json"
$PY scripts/summarize.py "$OUT/eval.json" "$OUT/eval_perturb.json"
