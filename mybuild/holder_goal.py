"""Parametric goal for a 3D-printed wall-mount holder (Taiga-S1 vocabulary).

Design v2 — matched to the photo of the original bracket:
  * square flange, 4x M4 clearance holes in a square pattern (photo has 4 screws)
  * round cup (boss_cyl) projecting perpendicular to the wall — the photo's
    cup is cylindrical
  * deep square cavity (pocket_rect) — the model vocabulary has no blind
    circular pocket (hole/hole_std are always ThroughAll), so the interior
    is the largest square that keeps >= 1.2mm walls inside the round cup
  * r1 rim fillet on the cup top

Print design rules (0.4mm nozzle, flange-down on the bed):
  - all walls >= 1.2mm (2 perimeters)
  - M4 clearance holes (dia 4.3mm)
  - cavity floor >= 4mm
  - rim fillet >= 1mm
  - no overhangs: flange flat, cup is a vertical prism

Model constraints that shape the design (freecad_s1.runtime pick_face picks
the LARGEST +Z face for sketch support):
  - cup top face area must exceed the flange annulus  -> cavity lands on cup
  - after the cavity, the cup rim annulus must still exceed the flange
    annulus -> fillet_top lands on the cup rim, not the flange
"""
from __future__ import annotations

import json
import math
from pathlib import Path

DEFAULTS = {
    # flange (built on the XY plane; lies flat on the print bed / against the wall)
    "flange_w": 46.0,   # X
    "flange_d": 46.0,   # Y
    "flange_t": 5.0,    # Z (3.0 was OOD for the model and triggered undo loops)
    # 4x screw holes in a square pattern (before the cup exists, so Face+Z
    # is unambiguous: only the flange top face exists)
    "hole_r": 2.15,     # M4 clearance dia 4.3
    "hole_dx": 17.0,    # +/-X from center
    "hole_dy": 17.0,    # +/-Y from center
    # cup (cylindrical, like the photo)
    "cup_r": 20.0,
    "cup_h": 30.0,
    "cup_dx": 0.0,
    "cup_dy": 0.0,
    # cavity (square pocket on the cup top, 4mm floor)
    "cav_w": 18.0,
    "cav_d": 18.0,
    "cav_depth": 26.0,
    # rim dressup
    "rim_fillet_r": 1.0,
}


def load_params(path: str | Path | None = None) -> dict:
    p = dict(DEFAULTS)
    jpath = Path(__file__).parent / "holder_params.json"
    src = Path(path) if path else (jpath if jpath.exists() else None)
    if src is not None:
        p.update(json.loads(src.read_text()))
    return p


def check_printability(p: dict) -> list[str]:
    """Sanity checks: print rules + the model's face-picking assumptions."""
    w, d, t = p["flange_w"], p["flange_d"], p["flange_t"]
    r = p["cup_r"]
    cup_area = math.pi * r * r
    plate_area = w * d
    annulus = plate_area - cup_area
    cav_area = p["cav_w"] * p["cav_d"]
    rim = cup_area - cav_area
    warnings = []
    if cup_area <= annulus:
        warnings.append(
            f"cup top face ({cup_area:.0f} mm2) <= flange annulus ({annulus:.0f} mm2): "
            "Face+Z would pick the flange for the cavity, not the cup")
    if rim <= annulus:
        warnings.append(
            f"cup rim ({rim:.0f} mm2) <= flange annulus ({annulus:.0f} mm2): "
            "fillet_top would land on the flange, not the cup rim")
    # cavity corners must fit inside the cup with wall margin
    if math.hypot(p["cav_w"], p["cav_d"]) / 2 > r - 1.2:
        warnings.append("cavity corners break through the cup wall (< 1.2mm)")
    if p["cup_h"] - p["cav_depth"] < 4.0:
        warnings.append("cavity floor < 4mm")
    if t < 1.2 or p["cav_depth"] < 1.2:
        warnings.append("flange or cavity depth < 1.2mm")
    # holes: clear the cup, stay on the flange
    for sx in (-1, 1):
        for sy in (-1, 1):
            hx, hy = sx * p["hole_dx"], sy * p["hole_dy"]
            hx += p["cup_dx"] * 0  # holes are placed relative to plate center
            dist_cup = math.hypot(hx - p["cup_dx"], hy - p["cup_dy"])
            if dist_cup - p["hole_r"] < r + 1.2:
                warnings.append(f"hole at ({hx:+.0f},{hy:+.0f}) too close to cup (ligament < 1.2mm)")
            if abs(hx) + p["hole_r"] > w / 2 - 1.2 or abs(hy) + p["hole_r"] > d / 2 - 1.2:
                warnings.append(f"hole at ({hx:+.0f},{hy:+.0f}) too close to flange edge")
    return warnings


def build_goal(p: dict | None = None) -> dict:
    """Return the goal dict accepted by the worker's `reset` op."""
    p = p or load_params()
    features = [
        {"kind": "base_box", "params": {"w": p["flange_w"], "d": p["flange_d"], "h": p["flange_t"]}},
        # 4 holes, square pattern, all before the cup so Face+Z = flange top
        {"kind": "hole", "params": {"r": p["hole_r"], "x": -p["hole_dx"], "y": p["hole_dy"]}},
        {"kind": "hole", "params": {"r": p["hole_r"], "x": p["hole_dx"], "y": p["hole_dy"]}},
        {"kind": "hole", "params": {"r": p["hole_r"], "x": -p["hole_dx"], "y": -p["hole_dy"]}},
        {"kind": "hole", "params": {"r": p["hole_r"], "x": p["hole_dx"], "y": -p["hole_dy"]}},
        {"kind": "boss_cyl", "params": {"r": p["cup_r"], "x": p["cup_dx"], "y": p["cup_dy"], "h": p["cup_h"]}},
        {"kind": "pocket_rect", "params": {"w": p["cav_w"], "d": p["cav_d"],
                                           "x": p["cup_dx"], "y": p["cup_dy"], "depth": p["cav_depth"]}},
        {"kind": "fillet_top", "params": {"r": p["rim_fillet_r"]}},
    ]
    scale = max(p["flange_w"], p["flange_d"], p["flange_t"] + p["cup_h"])
    return {"features": features, "level": 4, "scale": float(scale)}


if __name__ == "__main__":
    p = load_params()
    print(json.dumps(build_goal(p), indent=2))
    print("\nwarnings:", check_printability(p) or "none")
