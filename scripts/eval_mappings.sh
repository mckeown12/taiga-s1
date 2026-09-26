#!/usr/bin/env bash
# Evaluate checkpoints on every suite under both test-time index mappings.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
for d in "$@"; do
  for m in ${MODES:-expected identity}; do
    out="$d/eval_all_$m.json"
    [ -f "$out" ] && continue
    $PY -m freecad_s1.evaluate --ckpt "$d/last.pt" --episodes 60 --suites iid comp len len2 len3 --index-eval $m --out "$out" > /dev/null 2>&1
    $PY scripts/summarize.py "$out" | sed "s/\$/  [all, $m]/" | tee -a runs/abl/summary.txt
  done
done
