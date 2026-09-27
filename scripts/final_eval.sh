#!/usr/bin/env bash
# Final evaluation of the release model with strict metrics (clean success,
# zero-deviation success, per-rule breakdown), clean and with 20% injected
# random actions, plus recalibration. Writes results/.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
SUITES="iid comp comp2 comp3 len len2 len3"
$PY -m freecad_s1.evaluate --ckpt release/hf --data data/gen_test --episodes 100 --suites $SUITES --out results/eval.json
$PY -m freecad_s1.evaluate --ckpt release/hf --episodes 100 --perturb 0.2 --suites $SUITES --out results/eval_perturb.json
$PY scripts/calibrate.py --model release/hf > results/calibration.json
$PY scripts/summarize.py results/eval.json results/eval_perturb.json
