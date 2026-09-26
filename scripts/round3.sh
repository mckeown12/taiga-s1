#!/usr/bin/env bash
# Round 3 (resumable): modular variant K first, then remaining seeds.
# Each run: SFT 3 epochs on data/gen_train, eval iid/comp/len + len2.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
flags_for() {
  case $1 in
    A_abs)      echo "" ;;
    B_rand)     echo "--pos-mode rand" ;;
    C_rand_ord) echo "--pos-mode rand --ordinal" ;;
    H_inv)      echo "--pos-mode rand --ordinal --invariant-numerics" ;;
    K_modular)  echo "--pos-mode rand --ordinal --invariant-numerics --modular" ;;
  esac
}
run() {
  local name=$1 seed=$2 d=runs/abl/$1_s$2
  if [ ! -f "$d/eval.json" ]; then
    echo "=== $name seed $seed ($(flags_for $name))"
    $PY -m freecad_s1.train_sft --data data/gen_train --out "$d" --epochs 3 --seed "$seed" $(flags_for $name) > "$d.train.log" 2>&1 || return
    $PY -m freecad_s1.evaluate --ckpt "$d/last.pt" --data data/gen_test --episodes 60 --out "$d/eval.json" > "$d.eval.log" 2>&1 || return
    $PY scripts/summarize.py "$d/eval.json" | tee -a runs/abl/summary.txt
  fi
  if [ ! -f "$d/eval_len2_fixed.json" ]; then
    $PY -m freecad_s1.evaluate --ckpt "$d/last.pt" --episodes 60 --suites len2 --out "$d/eval_len2_fixed.json" > /dev/null 2>&1
    $PY scripts/summarize.py "$d/eval_len2_fixed.json" | sed 's/$/  [len2 fixed]/' | tee -a runs/abl/summary.txt
  fi
}
for spec in "K_modular 0" "K_modular 1" "C_rand_ord 1" "H_inv 1" "K_modular 2" "C_rand_ord 2" "H_inv 2" "B_rand 2" "A_abs 2"; do
  run $spec
done
echo ROUND3_DONE | tee -a runs/abl/summary.txt
