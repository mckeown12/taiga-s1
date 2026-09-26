"""One-line summary of evaluate.py reports: per-step acc + episode success per suite."""
import json
import sys

for path in sys.argv[1:]:
    r = json.load(open(path))
    parts = [path.split("/")[-2]]
    if "per_step" in r:
        parts.append(f"step_acc={r['per_step']['acc']:.4f}")
    eps = r.get("episodes", {})
    for key in sorted(k for k in eps if isinstance(eps[k], dict)):
        parts.append(f"{key}={eps[key]['success']:.2f}")
    print("  ".join(parts))
