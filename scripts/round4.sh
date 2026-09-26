#!/usr/bin/env bash
# Round 4 (resumable): done-head modular variant L first, then seeds.
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
    L_done)     echo "--pos-mode rand --ordinal --invariant-numerics --modular --pointer done" ;;
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
for spec in "L_done 0" "C_rand_ord 1" "L_done 1" "C_rand_ord 2" "L_done 2" "H_inv 1" "H_inv 2" "B_rand 2" "A_abs 2" "K_modular 1"; do
  run $spec
done
echo ROUND4_DONE | tee -a runs/abl/summary.txt
