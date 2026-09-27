#!/usr/bin/env bash
# Render the model-card images (2x for the charts) into ../release/hf/assets.
set -euo pipefail
cd "$(dirname "$0")"
OUT=../release/hf/assets
npx remotion still src/index.ts Cover "$OUT/cover.png" --scale=1 --log=error
for id in LengthLight:length_light LengthDark:length_dark AblationLight:ablation_light AblationDark:ablation_dark; do
  npx remotion still src/index.ts "${id%%:*}" "$OUT/${id##*:}.png" --scale=2 --log=error
done
echo rendered
