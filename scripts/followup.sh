#!/usr/bin/env bash
# After ablate.sh: (1) every seed-0 variant on the 8-10 intent suite;
# (2) seed robustness for the key variants (length generalization is known
# to be seed-sensitive, Zhou et al. 2024).
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
for d in runs/abl/*_s0; do
  $PY -m freecad_s1.evaluate --ckpt "$d/last.pt" --episodes 60 --suites len2 --out "$d/eval_len2.json" > /dev/null 2>&1
  $PY scripts/summarize.py "$d/eval_len2.json" | sed 's/$/  [len2]/' | tee -a runs/abl/summary.txt
done
for seed in 1 2; do
  SEED=$seed VARIANTS="${SEED_VARIANTS:-A_abs B_rand}" ./scripts/ablate.sh
  for v in ${SEED_VARIANTS:-A_abs B_rand}; do
    d=runs/abl/${v}_s${seed}
    $PY -m freecad_s1.evaluate --ckpt "$d/last.pt" --episodes 60 --suites len2 --out "$d/eval_len2.json" > /dev/null 2>&1
    $PY scripts/summarize.py "$d/eval_len2.json" | sed 's/$/  [len2]/' | tee -a runs/abl/summary.txt
  done
done
