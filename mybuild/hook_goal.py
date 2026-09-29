"""Parametric goal for the baby-gate wall hook (full part).

  * 46x46x5 flange (5mm: the model rejects base pads whose volume is < ~39%
    of the target; 5mm keeps margin B/(B+C-H) ~ 0.50)
  * 2x M4 clearance holes on X (perpendicular to the hook bend plane)
  * round boss dia 26 x 20
  * J-hook strap: flat flange section, rounded bend, tip curving back toward
    the wall — expressed as the forked 'hook_sweep' goal kind (one atomic
    PartDesign_Sweep action that sweeps the strap profile and fuses it in).
"""
from __future__ import annotations

import json
from pathlib import Path


def load_params(path: str | Path | None = None) -> dict:
    jpath = Path(__file__).parent / "hook_params.json"
    src = Path(path) if path else (jpath if jpath.exists() else None)
    p = json.loads(src.read_text()) if src else {}
    return p


def check_printability(p: dict) -> list[str]:
    w, d = p["flange_w"], p["flange_d"]
    warns = []
    hx, r, br = p["hole_dx"], p["hole_r"], p["boss_r"]
    if hx - r < br + 1.2:
        warns.append(f"hole at ({hx:+.0f},0) too close to boss (ligament < 1.2mm)")
    if hx + r > w / 2 - 1.2 or hx + r > d / 2 - 1.2:
        warns.append("hole too close to flange edge")
    if p["hook_t"] < 1.2:
        warns.append("hook wall thinner than one 0.4mm nozzle layer")
    return warns


def build_goal(p: dict | None = None) -> dict:
    p = p or load_params()
    flange_h = 5.0
    z0 = flange_h + p["boss_h"] - 0.5  # strap sinks 0.5mm into the boss
    features = [
        {"kind": "base_box", "params": {"w": p["flange_w"], "d": p["flange_d"], "h": flange_h}},
        {"kind": "hole", "params": {"r": p["hole_r"], "x": -p["hole_dx"], "y": 0.0}},
        {"kind": "hole", "params": {"r": p["hole_r"], "x": p["hole_dx"], "y": 0.0}},
        {"kind": "boss_cyl", "params": {"r": p["boss_r"], "x": 0.0, "y": 0.0, "h": p["boss_h"]}},
        {"kind": "hook_sweep", "params": {"y": z0, "h": p["hook_arm"], "r": p["hook_r"],
                                          "t": p["hook_t"], "w": p["hook_w"],
                                          "d": p["hook_tip"], "x": 0.0}},
    ]
    scale = max(p["flange_w"], p["flange_d"], z0 + p["hook_arm"])
    return {"features": features, "level": 3, "scale": float(scale)}


if __name__ == "__main__":
    p = load_params()
    print(json.dumps(build_goal(p), indent=2))
    print("\nwarnings:", check_printability(p) or "none")
