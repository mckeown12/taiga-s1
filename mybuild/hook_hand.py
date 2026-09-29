"""Hand-written FreeCAD macro: wall hook for a baby gate (photo-faithful).

Run with FreeCAD's python:
  $FREECAD_PYTHON mybuild/hook_hand.py [outdir]

Design (mm), matched to the photos:
  * 46x46x4 flange with rounded corners, 2x M4 clearance holes on the axis
    perpendicular to the hook's bend plane
  * round boss dia 26 x 20 projecting from the flange
  * J-hook strap: 7 wide x 3.5 thick, 20 arm, 180-deg U-turn (r5.5
    centerline), tip 10, rounded cap; U opens toward the wall so the gate
    latch slides up between arm and tip
Print: flange down; only overhang is the U-interior ceiling (~11x7mm) —
use a small tree support inside the U.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import FreeCAD as App
import Mesh
import MeshPart
import Part
from FreeCAD import Vector

sys.path.insert(0, str(Path(__file__).parent))
from hook_shape import make_hook


def load_params() -> dict:
    return json.loads((Path(__file__).parent / "hook_params.json").read_text())


def build(p: dict) -> Part.Shape:
    w, d, t = p["flange_w"], p["flange_d"], p["flange_t"]
    br, bh = p["boss_r"], p["boss_h"]

    # NOTE: a corner fillet on the flange (before or after the fuse) makes OCC
    # produce invalid/empty booleans in this FreeCAD build, so corners stay
    # sharp (cosmetic only; the mount face is unaffected).
    flange = Part.makeBox(w, d, t, Vector(-w / 2, -d / 2, 0))
    boss = Part.makeCylinder(br, bh, Vector(0, 0, t))
    solid = flange.fuse(boss)

    root = [e for e in solid.Edges if e.Curve.TypeId == "Part::GeomCircle"
            and abs(e.Curve.Center.z - t) < 1e-6 and abs(e.Curve.Radius - br) < 1e-6]
    if p.get("boss_root_fillet"):
        solid = solid.makeFillet(p["boss_root_fillet"], root)

    hook = make_hook(t + bh - 0.5, p["hook_w"], p["hook_t"],
                     p["hook_arm"], p["hook_r"], p["hook_tip"])
    solid = solid.fuse(hook)

    for sx in (-1, 1):
        solid = solid.cut(Part.makeCylinder(p["hole_r"], t + 2, Vector(sx * p["hole_dx"], 0, -1)))
    return solid


def main() -> None:
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "out" / "hook_hand"
    outdir.mkdir(parents=True, exist_ok=True)
    solid = build(load_params())
    print(f"valid: {solid.isValid()}  solids: {len(solid.Solids)}  volume: {solid.Volume:.0f} mm3")
    bb = solid.BoundBox
    print(f"bbox: {bb.XLength:.1f} x {bb.YLength:.1f} x {bb.ZLength:.1f} mm")

    doc = App.newDocument("hook_hand")
    obj = doc.addObject("Part::Feature", "Hook")
    obj.Shape = solid
    fcstd = outdir / "hook.FCStd"
    doc.saveAs(str(fcstd))
    print("fcstd:", fcstd)

    mesh = MeshPart.meshFromShape(Shape=solid, LinearDeflection=0.1, AngularDeflection=0.35, Relative=False)
    stl = outdir / "hook.stl"
    mesh.write(str(stl))
    print(f"stl: {stl}  ({len(mesh.Points)} points)")


if __name__ == "__main__":
    main()
