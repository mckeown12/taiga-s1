"""Strap profile polyline for the OnShape J-hook (XZ plane), from hook_shape.make_hook.
Defaults: z0=23, w=7, t=3.5, arm=20, r=5.5, tip=10.
All three semicircular arcs are replaced by 8-segment polygon chains.
Returns closed list of (x, z) points (mm), first == last.
"""
import math


def arc_chain(p0, p1, center, segs, ccw):
    """Polygon points of the arc from p0 to p1 about `center` (excl. p0)."""
    a0 = math.atan2(p0[1] - center[1], p0[0] - center[0])
    a1 = math.atan2(p1[1] - center[1], p1[0] - center[0])
    if ccw:
        d = (a1 - a0) % (2 * math.pi)
    else:
        d = (a0 - a1) % (2 * math.pi)
    if d < 1e-9:
        d = 2 * math.pi
    R = math.hypot(p0[0] - center[0], p0[1] - center[1])
    out = []
    for i in range(1, segs + 1):
        a = a0 + (d if ccw else -d) * i / segs
        out.append((center[0] + R * math.cos(a), center[1] + R * math.sin(a)))
    return out


def strap_profile(z0=23.0, t=3.5, arm=20.0, r=5.5, tip=10.0):
    ht = t / 2
    ri = r - ht
    ro = r + ht
    xt = 2 * r
    A = (-ht, z0)
    B = (-ht, z0 + arm)
    F = (xt + ht, z0 + arm)
    E = (xt + ht, z0 + arm - tip)
    D = (xt - ht, z0 + arm - tip)
    C = (xt - ht, z0 + arm)
    Bp = (ht, z0 + arm)
    Ap = (ht, z0)
    c_u = (r, z0 + arm)            # center of both U arcs
    c_cap = (xt, z0 + arm - tip)   # center of bottom cap
    pts = [A, B]
    pts += arc_chain(B, F, c_u, 8, ccw=False)      # over the top: 180->90->0
    pts += [E]
    pts += arc_chain(E, D, c_cap, 8, ccw=False)    # around the bottom: 0->-90->180
    pts += [C]
    pts += arc_chain(C, Bp, c_u, 8, ccw=True)      # inner U: 0->90->180
    pts += [Ap, A]
    return pts


if __name__ == "__main__":
    pts = strap_profile()
    xs = [p[0] for p in pts]
    zs = [p[1] for p in pts]
    print(f"n={len(pts)}  x[{min(xs):.2f},{max(xs):.2f}]  z[{min(zs):.2f},{max(zs):.2f}]")
    print("expect x[-1.75, 12.75]  z[23, 50.25]")
