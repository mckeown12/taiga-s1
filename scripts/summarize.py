"""One-line summary of evaluate.py reports: per-step acc + episode success per suite."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root
import json
import sys

for path in sys.argv[1:]:
    r = json.load(open(path))
    parts = [path.split("/")[-2]]
    if "per_step" in r:
        parts.append(f"step_acc={r['per_step']['acc']:.4f}")
    eps = r.get("episodes", {})
    for key in sorted(k for k in eps if isinstance(eps[k], dict)):
        e = eps[key]
        clean = e.get("clean_success")
        parts.append(f"{key}={e['success']:.2f}" + (f"/clean {clean:.2f}/zero-dev {e['zero_deviation_success']:.2f}"
                                                    if "zero_deviation_success" in e else ""))
    print("  ".join(parts))
