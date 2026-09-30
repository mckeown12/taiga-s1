"""Probe which curve geometry the OnShape sketch kernel accepts for arcs.

T1: BTCurveGeometryArc-119 (center pnt + radius + start/end directions)
T2: InterpolatedSpline-116 with dense on-arc points + endpoint tangents
T3: Circle-115 sanity (rectangle with a circular hole -> exact volume)

Each test: sketch on Top (JDC) + blind extrude + massproperties vs exact.
"""
import json, math, os
import osapi as o
from os_arc_test import (DOC, WS, b62, eid, conf, mk_feature, delete_feature,
                         status_of, sketch_body, line_entity, extrude_body, mass)

R = 10.0  # test radius (mm, sketch units)

def arc_t1():
    """BTCurveGeometryArc-119: center (0,0), r=10, start (10,0) dir (0,1), end (0,10) dir (-1,0)."""
    e = {"btType": "BTMSketchCurveSegment-155",
         "startPointId": eid(), "endPointId": eid(),
         "startParam": 0.0, "endParam": 1.0,
         "geometry": {"btType": "BTCurveGeometryArc-119",
                      "pntX": 0.0, "pntY": 0.0,
                      "radius": R,
                      "xDir": 0.0, "yDir": 1.0,
                      "xDir2": -1.0, "yDir2": 0.0,
                      "clockwise": False},
         "centerId": "", "internalIds": [], "curvedTextIds": [],
         "isConstruction": False, "parameters": [], "isFromSplineHandle": False,
         "isFromEndpointSplineHandle": False, "isFromSplineControlPolygon": False,
         "entityId": eid(), "namespace": "", "index": 0,
         "name": "", "hasUserCode": False}
    return [e,
            line_entity((0.0, R), (0.0, -1.0)),
            line_entity((0.0, 0.0), (1.0, 0.0))]

def circle_ent(cx, cy, r):
    return {"btType": "BTMSketchCurveSegment-155",
            "startPointId": eid(), "endPointId": eid(),
            "startParam": 0.0, "endParam": 1.0,
            "geometry": {"btType": "BTCurveGeometryCircle-115",
                         "radius": r, "xCenter": cx, "yCenter": cy,
                         "xDir": 0.0, "yDir": 0.0, "clockwise": False},
            "centerId": "", "internalIds": [], "curvedTextIds": [],
            "isConstruction": False, "parameters": [], "isFromSplineHandle": False,
            "isFromEndpointSplineHandle": False, "isFromSplineControlPolygon": False,
            "entityId": eid(), "namespace": "", "index": 0,
            "name": "", "hasUserCode": False}

def arc_t2():
    """InterpolatedSpline-116: 9 points on the quarter arc + endpoint tangents."""
    pts = []
    for i in range(10):
        a = math.radians(90 * i / 9)
        pts.append([R * math.cos(a), R * math.sin(a)])
    e = {"btType": "BTMSketchCurveSegment-155",
         "startPointId": eid(), "endPointId": eid(),
         "startParam": 0.0, "endParam": 1.0,
         "geometry": {"btType": "BTCurveGeometryInterpolatedSpline-116",
                      "interpolationPoints": pts,
                      "isPeriodic": False,
                      "startDerivativeX": 0.0, "startDerivativeY": 1.0,
                      "endDerivativeX": -1.0, "endDerivativeY": 0.0,
                      "startHandleX": 0.0, "startHandleY": 0.0,
                      "endHandleX": 0.0, "endHandleY": 0.0,
                      "derivatives": {}},
         "centerId": "", "internalIds": [], "curvedTextIds": [],
         "isConstruction": False, "parameters": [], "isFromSplineHandle": False,
         "isFromEndpointSplineHandle": False, "isFromSplineControlPolygon": False,
         "entityId": eid(), "namespace": "", "index": 0,
         "name": "", "hasUserCode": False}
    return [e,
            line_entity((0.0, R), (0.0, -1.0)),
            line_entity((0.0, 0.0), (1.0, 0.0))]

def arc_t3():
    """Rectangle 20x10 with a hole r=3 at (10,5): circle as inner boundary."""
    h, w = 10.0, 20.0
    ents = [
        line_entity((0.0, 0.0), (1.0, 0.0)),          # bottom
        line_entity((w, 0.0), (0.0, 1.0)),            # right
        line_entity((w, h), (-1.0, 0.0)),             # top
        line_entity((0.0, h), (0.0, -1.0)),           # left
        circle_ent(10.0, 5.0, 3.0),
    ]
    return ents

def run_test(ps, label, ents, depth=5.0, expected_mm3=None):
    print(f"\n=== {label} ===")
    s, b2 = mk_feature(ps, sketch_body(label, "JDC", ents))
    fid, st = status_of(b2)
    print(f"sketch: {s} status={st} fid={fid}")
    if s != 200 or st != "OK":
        print("RAW:", json.dumps(b2)[:400])
        return None
    # what did the kernel make of the first entity?
    s3, _, b3 = o.get(f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/sketches")
    if isinstance(b3, str):
        b3 = json.loads(b3)
    sks = b3 if isinstance(b3, list) else b3.get("sketches", [])
    sk = next((x for x in sks if x.get("featureId") == fid), None)
    if sk:
        types = [(g.get("id"), g.get("entityType")) for g in sk.get("geomEntities", [])
                 if "internal" not in str(g.get("id", "")) and not str(g.get("id", "")).endswith(".start") and not str(g.get("id", "")).endswith(".end")]
        print("entity types:", types)
    s, b4 = mk_feature(ps, extrude_body(label + "X", fid, depth, "NEW"))
    fid2, st2 = status_of(b4)
    print(f"extrude: {s} status={st2} fid={fid2}")
    if st2 != "OK":
        print("RAW:", json.dumps(b4)[:400])
        return None
    mp = mass(ps)
    total = sum(p.get("volume") or 0.0 for p in mp.values())
    got = total * 1e9
    if expected_mm3 is not None:
        print(f"volume: {got:.4f} mm^3 vs expected {expected_mm3:.4f} mm^3")
        print(f"{label}:", "PASS" if abs(got - expected_mm3) / expected_mm3 < 2e-3 else "MISMATCH")
    else:
        print(f"volume: {got:.4f} mm^3")
    return {"sketch": fid, "extrude": fid2, "volume_mm3": got}

def main():
    state = json.load(open("out/ons/state.json"))
    ps = state["hook_ps"]
    # clean slate
    s, _, b = o.post(f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/features/rollback",
                     {"btType": "BTSetFeatureRollbackCall-1899", "rollbackIndex": 0})
    print("rollback:", s)
    q4 = math.pi * R * R / 4 * 5.0
    t1 = run_test(ps, "T1arc119", arc_t1(), 5.0, q4)
    t2 = run_test(ps, "T2interp", arc_t2(), 5.0, q4)
    rect_hole = 20.0 * 10.0 * 5.0 - math.pi * 9.0 * 5.0
    t3 = run_test(ps, "T3circle", arc_t3(), 5.0, rect_hole)
    state["arc_tests"] = {"T1arc119": t1, "T2interp": t2, "T3circle": t3}
    json.dump(state, open("out/ons/state.json"), "w", indent=1)

if __name__ == "__main__":
    main()
