"""Hybrid part: Taiga-S1-built base (flange + holes + boss) + macro hook strap.

The hook strap is a sweep, outside Taiga-S1's current vocabulary, so the
model builds everything it can and this script fuses the sweep on. After the
vocabulary extension + fine-tune, the model is expected to do this step
itself.

Usage (FreeCAD python):
  $FREECAD_PYTHON mybuild/hook_fuse.py [taiga_base.FCStd] [outdir]
"""
from __future__ import annotations

import sys
from pathlib import Path

import FreeCAD as App
import Mesh
import MeshPart

sys.path.insert(0, str(Path(__file__).parent))
import json
from hook_shape import make_hook

params = json.loads((Path(__file__).parent / "hook_params.json").read_text())


def main() -> None:
    basepath = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "out" / "hook_taiga" / "hook_taiga.FCStd"
    outdir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent / "out" / "hook_hybrid"
    outdir.mkdir(parents=True, exist_ok=True)

    doc = App.openDocument(str(basepath))
    src = next(o for o in doc.Objects if o.TypeId == "PartDesign::Body")
    base = src.Shape.copy()
    # boss top = flange_t(5) + boss_h  (Taiga base uses 5mm flange)
    z0 = 5.0 + params["boss_h"] - 0.5  # sink the strap 0.5mm into the boss
    hook = make_hook(z0, params["hook_w"], params["hook_t"],
                     params["hook_arm"], params["hook_r"], params["hook_tip"])
    solid = base.fuse(hook)
    print(f"hybrid: valid {solid.isValid()}  solids {len(solid.Solids)}  volume {solid.Volume:.0f} mm3")

    out = App.newDocument("hook_hybrid")
    obj = out.addObject("Part::Feature", "Hook")
    obj.Shape = solid
    fcstd = outdir / "hook.FCStd"
    out.saveAs(str(fcstd))
    print("fcstd:", fcstd)
    mesh = MeshPart.meshFromShape(Shape=solid, LinearDeflection=0.1, AngularDeflection=0.35, Relative=False)
    stl = outdir / "hook.stl"
    mesh.write(str(stl))
    print(f"stl: {stl}  ({len(mesh.Points)} points)")


if __name__ == "__main__":
    main()
