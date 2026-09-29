"""J-hook strap solid (shared by the hand macro and the hybrid fuse).

Geometry: flat strap in the XZ plane, extruded along Y (width `w`), centered
on the boss axis. The arm starts at z0 (the boss top face, sunk slightly so
the fuse is robust) and runs up `arm`; a 180-degree U-turn (centerline
radius `r`) at the top brings the tip down `tip`, ending in a rounded cap.

The hook's U opens toward the wall (down, -Z): the gate latch slides up
between arm and tip and rests inside the U.
"""
from __future__ import annotations

import FreeCAD
import Part
from FreeCAD import Vector


def make_hook(z0: float, w: float = 7.0, t: float = 3.5, arm: float = 20.0,
              r: float = 5.5, tip: float = 10.0) -> Part.Shape:
    y0 = -w / 2
    ht = t / 2                       # strap half-thickness (X)
    ri = r - ht                      # inner (U) arc radius
    ro = r + ht                      # outer arc radius
    xt = 2 * r                       # tip centerline X offset
    V = Vector
    A = V(-ht, y0, z0)               # arm outer bottom
    B = V(-ht, y0, z0 + arm)         # arm outer top
    F = V(xt + ht, y0, z0 + arm)     # tip outer top
    E = V(xt + ht, y0, z0 + arm - tip)  # tip outer bottom
    D = V(xt - ht, y0, z0 + arm - tip)  # tip inner bottom
    C = V(xt - ht, y0, z0 + arm)     # tip inner top
    Bp = V(ht, y0, z0 + arm)         # arm inner top
    Ap = V(ht, y0, z0)               # arm inner bottom
    mid_out = V(r, y0, z0 + arm + ro)
    mid_cap = V(xt, y0, z0 + arm - tip - ht)
    mid_in = V(r, y0, z0 + arm + ri)
    wire = Part.Wire([
        Part.makeLine(A, B),
        Part.Arc(B, mid_out, F).toShape(),
        Part.makeLine(F, E),
        Part.Arc(E, mid_cap, D).toShape(),
        Part.makeLine(D, C),
        Part.Arc(C, mid_in, Bp).toShape(),
        Part.makeLine(Bp, Ap),
        Part.makeLine(Ap, A),
    ])
    face = Part.Face(wire)
    return face.extrude(V(0, w, 0))


if __name__ == "__main__":
    s = make_hook(0.0)
    bb = s.BoundBox
    print(f"valid: {s.isValid()} vol: {s.Volume:.0f} mm3  bbox: {bb.XLength:.2f} x {bb.YLength:.2f} x {bb.ZLength:.2f} mm")
