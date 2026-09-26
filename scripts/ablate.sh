#!/usr/bin/env bash
# Generalization ablation: same data (data/gen_train, held-out compositions
# excluded), same budget (SFT, 3 epochs), one flag set per variant.
# Eval: iid (L1-L3), comp (held-out combinations), len (held-out 6-7 intents).
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
EPOCHS=${EPOCHS:-3}
SEED=${SEED:-0}
declare -a NAMES=(${VARIANTS:-A_abs B_rand C_rand_ord D_progress E_full})
for name in "${NAMES[@]}"; do
  case $name in
    A_abs)       flags="" ;;
    B_rand)      flags="--pos-mode rand" ;;
    C_rand_ord)  flags="--pos-mode rand --ordinal" ;;
    D_progress)  flags="--progress-head" ;;
    E_full)      flags="--pos-mode rand --ordinal --progress-head" ;;
    F_ord)       flags="--ordinal" ;;
    G_ord_prog)  flags="--ordinal --progress-head" ;;
    H_inv)       flags="--pos-mode rand --ordinal --invariant-numerics" ;;
    J_inv_only)  flags="--invariant-numerics" ;;
    *) echo "unknown variant $name"; exit 1 ;;
  esac
  out=runs/abl/${name}_s${SEED}
  echo "=== $name ($flags) -> $out"
  $PY -m freecad_s1.train_sft --data data/gen_train --out "$out" --epochs "$EPOCHS" --seed "$SEED" $flags > "$out.train.log" 2>&1 \
    && $PY -m freecad_s1.evaluate --ckpt "$out/last.pt" --data data/gen_test --episodes 60 --out "$out/eval.json" > "$out.eval.log" 2>&1 \
    && $PY scripts/summarize.py "$out/eval.json" | tee -a runs/abl/summary.txt
done
