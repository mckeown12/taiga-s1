#!/usr/bin/env bash
# Round 2 (resumable): (1) re-score seed-0 variants on len2 after the MAX_GOAL
# fix; (2) new variants H_inv / J_inv_only; (3) seeds for the top variants.
# Every eval runs all suites incl. len2 (8-10 intents).
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
len2() {
  local d=$1
  [ -f "$d/eval_len2_fixed.json" ] && return
  $PY -m freecad_s1.evaluate --ckpt "$d/last.pt" --episodes 60 --suites len2 --out "$d/eval_len2_fixed.json" > /dev/null 2>&1
  $PY scripts/summarize.py "$d/eval_len2_fixed.json" | sed 's/$/  [len2 fixed]/' | tee -a runs/abl/summary.txt
}
for d in runs/abl/*_s0; do len2 "$d"; done
for spec in "H_inv 0" "J_inv_only 0" "C_rand_ord 1" "H_inv 1" "C_rand_ord 2" "H_inv 2" "B_rand 2" "A_abs 2"; do
  set -- $spec
  d=runs/abl/$1_s$2
  [ -f "$d/eval.json" ] || SEED=$2 VARIANTS=$1 ./scripts/ablate.sh
  len2 "$d"
done
echo ROUND2_DONE | tee -a runs/abl/summary.txt
