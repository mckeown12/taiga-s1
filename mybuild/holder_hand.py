"""Hand-written FreeCAD macro: photo-faithful wall-mount holder.

Run with FreeCAD's python:
  $FREECAD_PYTHON mybuild/holder_hand.py [outdir]

Design (mm), matched to the photo of the original bracket:
  * thin square flange 46x48x4, 4x M4 clearance holes (dia 4.3)
  * round cup dia 26, 28 tall (deep, like the photo)
  * round cavity dia 20, 24 deep -> 3mm walls, 4mm floor
  * r1 fillet on the cavity lip and the outer cup rim
  * 5mm chamfer on one flange corner (the clipped corner in the photo)
Print: flange down, no overhangs, no supports.
"""
from __future__ import annotations

import sys
from pathlib import Path

import FreeCAD as App
import Mesh
import MeshPart
import Part
from FreeCAD import Vector

# ---------------------------------------------------------------- parameters
PLATE_W, PLATE_D, PLATE_T = 46.0, 48.0, 4.0
HOLE_R, HOLE_DX, HOLE_DY = 2.15, 15.5, 15.5
CUP_R, CUP_H = 13.0, 28.0
CAV_R, CAV_FLOOR = 10.0, 4.0
RIM_R = 1.0
CORNER_CHAMFER = 5.0          # on the (-W/2, +D/2) vertical corner
CORNER = (-PLATE_W / 2, PLATE_D / 2)


def build() -> Part.Shape:
    top = PLATE_T + CUP_H
    plate = Part.makeBox(PLATE_W, PLATE_D, PLATE_T, Vector(-PLATE_W / 2, -PLATE_D / 2, 0))
    cup = Part.makeCylinder(CUP_R, CUP_H, Vector(0, 0, PLATE_T))
    solid = plate.fuse(cup)

    # round cavity, 4mm floor (cut 0.5 past the top for a clean rim)
    cav = Part.makeCylinder(CAV_R, CUP_H - CAV_FLOOR + 0.5, Vector(0, 0, top - (CUP_H - CAV_FLOOR)))
    solid = solid.cut(cav)

    # 4x M4 clearance holes through the flange
    for sx in (-1, 1):
        for sy in (-1, 1):
            h = Part.makeCylinder(HOLE_R, PLATE_T + 2, Vector(sx * HOLE_DX, sy * HOLE_DY, -1))
            solid = solid.cut(h)

    # dressup: corner chamfer + rim fillets
    edges = []
    for e in solid.Edges:
        c = e.Curve
        if isinstance(c, Part.Circle):
            z = c.Center.z
            if abs(z - top) < 1e-6 and (abs(c.Radius - CAV_R) < 1e-6 or abs(c.Radius - CUP_R) < 1e-6):
                edges.append(e)
    solid = solid.makeFillet(RIM_R, edges)

    chamfer_edges = [e for e in solid.Edges
                     if isinstance(e.Curve, Part.Line)
                     and all(abs(v.Point.x - CORNER[0]) < 1e-6 and abs(v.Point.y - CORNER[1]) < 1e-6
                             for v in e.Vertexes)]
    solid = solid.makeChamfer(CORNER_CHAMFER, chamfer_edges)
    return solid


def main() -> None:
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "out" / "hand"
    outdir.mkdir(parents=True, exist_ok=True)
    solid = build()
    print(f"valid: {solid.isValid()}  solids: {len(solid.Solids)}  volume: {solid.Volume:.0f} mm3")
    bb = solid.BoundBox
    print(f"bbox: {bb.XLength:.1f} x {bb.YLength:.1f} x {bb.ZLength:.1f} mm")

    doc = App.newDocument("holder_hand")
    obj = doc.addObject("Part::Feature", "Holder")
    obj.Shape = solid
    fcstd = outdir / "holder.FCStd"
    doc.saveAs(str(fcstd))
    print("fcstd:", fcstd)

    mesh = MeshPart.meshFromShape(Shape=solid, LinearDeflection=0.1, AngularDeflection=0.35, Relative=False)
    stl = outdir / "holder.stl"
    mesh.write(str(stl))
    print(f"stl: {stl}  ({len(mesh.Points)} points)")


if __name__ == "__main__":
    main()
