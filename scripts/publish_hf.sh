#!/usr/bin/env bash
# Publish the exported model to the Hugging Face Hub.
#   ./scripts/publish_hf.sh <user-or-org>/<repo> [--private]
# Requires `hf auth login` first (token with write access).
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=${1:?usage: publish_hf.sh <user>/<repo> [--private]}
VIS=${2:-}
sed -i '' "s|HF_REPO_ID|$REPO|g" release/hf/README.md
.venv/bin/hf repo create "$REPO" --repo-type model $VIS --exist-ok
.venv/bin/hf upload "$REPO" release/hf . --repo-type model --commit-message "Taiga-S1 v0.3.0"
echo "https://huggingface.co/$REPO"
