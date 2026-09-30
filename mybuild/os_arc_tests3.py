"""Round 2 of arc-curve probing:
T2b: InterpolatedSpline-116 with FLAT interpolation points
T4:  plain circle extrude (the boss shape) - featureId region query
T3b: rectangle+hole with hidden-endpoint probing for region short IDs
"""
import json, math, os
import osapi as o
from os_arc_test import (DOC, WS, eid, mk_feature, status_of, sketch_body,
                         line_entity, extrude_body, mass)

R = 10.0

def arc_t2b():
    pts = []
    for i in range(10):
        a = math.radians(90 * i / 9)
        pts.extend([R * math.cos(a), R * math.sin(a)])
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
    return [e, line_entity((0.0, R), (0.0, -1.0)), line_entity((0.0, 0.0), (1.0, 0.0))]

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

def extrude_body_rid(name, sketch_fid, depth_mm, rid=None, operation="NEW"):
    """Extrude with optional region deterministicId."""
    qy = {"btType": "BTMIndividualSketchRegionQuery-140", "featureId": sketch_fid}
    if rid:
        qy["deterministicIds"] = [rid]
    q = {"btType": "BTMParameterQueryList-148", "parameterId": "entities",
         "queries": [qy],
         "filter": {"btType": "BTAndFilter-110",
                    "operand1": {"btType": "BTOrFilter-167",
                                 "operand1": {"btType": "BTAndFilter-110",
                                              "operand1": {"btType": "BTAndFilter-110",
                                                           "operand1": {"btType": "BTFlatSheetMetalFilter-3018",
                                                                        "allows": "MODEL_AND_FLATTENED"},
                                                           "operand2": {"btType": "BTSketchObjectFilter-184",
                                                                        "isSketchObject": True,
                                                                        "objectType": "ANY_SKETCH_OBJECT"}},
                                              "operand2": {"btType": "BTEntityTypeFilter-124",
                                                           "entityType": "FACE"}},
                                 "operand2": {"btType": "BTAndFilter-110",
                                              "operand1": {"btType": "BTAndFilter-110",
                                                           "operand1": {"btType": "BTGeometryFilter-130",
                                                                        "geometryType": "PLANE"},
                                                           "operand2": {"btType": "BTFlatSheetMetalFilter-3018",
                                                                        "allows": "MODEL_ONLY"}},
                                              "operand2": {"btType": "BTEntityTypeFilter-124",
                                                           "entityType": "FACE"}}},
                    "operand2": {"btType": "BTConstructionObjectFilter-113",
                                 "isConstruction": False}}}
    return {"btType": "BTMFeature-134", "featureType": "extrude", "name": name,
            "entities": [],
            "parameters": [
                {"btType": "BTMParameterEnum-145", "parameterId": "domain",
                 "enumName": "OperationDomain", "value": "MODEL", "namespace": ""},
                {"btType": "BTMParameterEnum-145", "parameterId": "bodyType",
                 "enumName": "ExtendedToolBodyType", "value": "SOLID", "namespace": ""},
                {"btType": "BTMParameterEnum-145", "parameterId": "operationType",
                 "enumName": "NewBodyOperationType", "value": operation, "namespace": ""},
                {"btType": "BTMParameterEnum-145", "parameterId": "surfaceOperationType",
                 "enumName": "NewSurfaceOperationType", "value": "NEW", "namespace": ""},
                {"btType": "BTMParameterEnum-145", "parameterId": "flatOperationType",
                 "enumName": "FlatOperationType", "value": "REMOVE", "namespace": ""},
                {"btType": "BTMParameterBoolean-144", "parameterId": "midplane", "value": False},
                {"btType": "BTMParameterQuantity-147", "parameterId": "thickness",
                 "units": "", "value": 0.0, "isInteger": False, "expression": "0 mm"},
                {"btType": "BTMParameterBoolean-144", "parameterId": "flipWall", "value": False},
                {"btType": "BTMParameterQuantity-147", "parameterId": "thickness1",
                 "units": "", "value": 0.0, "isInteger": False, "expression": "0 mm"},
                {"btType": "BTMParameterQuantity-147", "parameterId": "thickness2",
                 "units": "", "value": 0.0, "isInteger": False, "expression": "0 mm"},
                {"btType": "BTMParameterEnum-145", "parameterId": "endBound",
                 "enumName": "BoundingType", "value": "BLIND", "namespace": ""},
                q,
                {"btType": "BTMParameterBoolean-144", "parameterId": "oppositeDirection", "value": False},
                {"btType": "BTMParameterQuantity-147", "parameterId": "depth",
                 "units": "", "value": depth_mm / 1000.0, "isInteger": False,
                 "expression": f"{depth_mm} mm"}],
            "suppressed": False, "namespace": "", "hasUserCode": False}

def probe_hidden(ps, sid):
    paths = [
        f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/sketches/{sid}/tessellatedentities",
        f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/sketches/{sid}/boundingboxes",
        f"/sketches/d/{DOC}/w/{WS}/e/{ps}/{sid}/tessellatedentities",
        f"/sketches/d/{DOC}/w/{WS}/e/{ps}/{sid}/boundingboxes",
        f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/sketches/{sid}/regions",
    ]
    for p in paths:
        s, h, b = o.get(p)
        print("   ", s, p.split("/e/")[-1][:80])
        if s == 200:
            t = b if not isinstance(b, str) else json.loads(b)
            print("      ", json.dumps(t)[:600])
            return t
    return None

def run(ps, label, ents, depth=5.0, expected=None, rid=None):
    print(f"\n=== {label} ===")
    s, b2 = mk_feature(ps, sketch_body(label, "JDC", ents))
    fid, st = status_of(b2)
    print(f"sketch: {s} status={st} fid={fid}")
    if s != 200 or st != "OK":
        print("RAW:", json.dumps(b2)[:300])
        return None
    s, b4 = mk_feature(ps, extrude_body_rid(label + "X", fid, depth, rid=rid))
    fid2, st2 = status_of(b4)
    print(f"extrude: {s} status={st2} fid={fid2}")
    if st2 != "OK":
        print("RAW:", json.dumps(b4)[:300])
        return None
    mp = mass(ps)
    total = sum(p.get("volume") or 0.0 for p in mp.values())
    got = total * 1e9
    if expected is not None:
        print(f"volume: {got:.4f} vs {expected:.4f} mm^3 ->",
              "PASS" if abs(got - expected) / expected < 2e-3 else "MISMATCH")
    else:
        print(f"volume: {got:.4f} mm^3")
    return {"sketch": fid, "extrude": fid2, "volume_mm3": got}

def main():
    state = json.load(open("out/ons/state.json"))
    ps = state["hook_ps"]
    s, _, b = o.post(f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/features/rollback",
                     {"btType": "BTSetFeatureRollbackCall-1899", "rollbackIndex": 0})
    print("rollback:", s)
    q4 = math.pi * R * R / 4 * 5.0

    t2b = run(ps, "T2binterp", arc_t2b(), 5.0, q4)

    # T4: plain circle -> cylinder
    t4 = run(ps, "T4circle", [circle_ent(0.0, 0.0, 5.0)], 8.0,
             math.pi * 25.0 * 8.0)

    # T3b: rect + hole; probe hidden endpoints for region ids
    h, w = 10.0, 20.0
    t3 = run(ps, "T3bhole",
             [line_entity((0.0, 0.0), (1.0, 0.0)),
              line_entity((w, 0.0), (0.0, 1.0)),
              line_entity((w, h), (-1.0, 0.0)),
              line_entity((0.0, h), (0.0, -1.0)),
              circle_ent(10.0, 5.0, 3.0)],
             5.0, (w * h - math.pi * 9.0) * 5.0)
    if t3 is None:
        print("T3b failed - probing hidden sketch endpoints for region ids...")
        # recreate the sketch, probe, retry with region deterministicId
        s, b2 = mk_feature(ps, sketch_body("T3chold2", "JDC",
                                           [line_entity((0.0, 0.0), (1.0, 0.0)),
                                            line_entity((w, 0.0), (0.0, 1.0)),
                                            line_entity((w, h), (-1.0, 0.0)),
                                            line_entity((0.0, h), (0.0, -1.0)),
                                            circle_ent(10.0, 5.0, 3.0)]))
        fid, st = status_of(b2)
        print(f"recreated sketch: {s} {st} fid={fid}")
        data = probe_hidden(ps, fid)
        # guess region ids from any tessellation data
        rids = []
        if data:
            txt = json.dumps(data)
            import re
            rids = re.findall(r'"J[A-Za-z0-9]{2}"', txt)
            print("candidate region ids:", sorted(set(rids)))
        for rid in sorted(set(rids))[:4]:
            s, b4 = mk_feature(ps, extrude_body_rid(f"T3rid{rid}", fid, 5.0, rid=rid))
            fid2, st2 = status_of(b4)
            print(f"  extrude with rid={rid}: {s} {st2}")
            if st2 == "OK":
                mp = mass(ps)
                total = sum(p.get("volume") or 0.0 for p in mp.values())
                print(f"  volume: {total*1e9:.4f} (expected {(w*h-math.pi*9.0)*5.0:.4f})")
                t3 = {"sketch": fid, "extrude": fid2, "rid": rid, "volume_mm3": total * 1e9}
                break

    state["arc_tests2"] = {"T2b": t2b, "T4": t4, "T3b": t3}
    with open("out/ons/state.json", "w") as f:
        json.dump(state, f, indent=1)

if __name__ == "__main__":
    main()
