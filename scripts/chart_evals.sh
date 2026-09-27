#!/usr/bin/env bash
# Evaluations behind the model-card charts (results/charts/*.json).
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
ev() {  # name ckpt episodes suites... (extra flags via EXTRA)
  local name=$1 ckpt=$2 n=$3; shift 3
  [ -f "results/charts/$name.json" ] && return
  $PY -m freecad_s1.evaluate --ckpt "$ckpt" --episodes "$n" --suites "$@" ${EXTRA:-} --out "results/charts/$name.json" > /dev/null 2>&1
  $PY scripts/summarize.py "results/charts/$name.json" | sed "s/^[^ ]*/$name/"
}
# Length curve: Taiga-S1 beyond 11 intents, and the v2 model on the lengths it was not yet run on.
ev taiga_stress release/hf 60 len4 len5 len6
ev v2_len2_len4 checkpoints/v2_indist/last.pt 60 len2 len4
# Ablation on 11-intent goals, same test-time mapping (identity) for every variant.
for d in A_abs_s0 A_abs_s1 B_rand_s0 B_rand_s1 C_rand_ord_s0 C_rand_ord_s1 C_rand_ord_s2 L_done_s0 L_done_s1 L_done_s2; do
  EXTRA="--index-eval identity" ev "abl_$d" "runs/abl/$d/last.pt" 60 len3
done
echo CHART_EVALS_DONE
