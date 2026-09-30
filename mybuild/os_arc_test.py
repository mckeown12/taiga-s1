"""Phase-1 step A: create the 'hook' part studio, probe the origin-plane
short IDs (Front/Right) via candidate sketch-plane tests, and validate the
rational-conic wire format with a quarter-arc volume test.

Conic arc wire (from the OnShape app serialize bundle, bsedit.GBTCurveGeometryConic):
    {"btType": "BTCurveGeometryConic-2284",
     "radius": 0, "xDir": 0, "yDir": 0, "xDir2": 0, "yDir2": 0, "clockwise": False,
     "rho": cos(theta/2),
     "points": [{"x": x0, "y": y0}, {"x": xc, "y": yc}, {"x": x1, "y": y1}]}
(points = start, tangent-intersection control, end)

Sketch/extrude bodies mirror the phase-0 wire that already produced
featureStatus OK (BTFeatureDefinitionCall-1406 create; string enum values;
operand1/operand2 filter tree).
"""
import json, math, os, uuid
import osapi as o

DOC = "9482dce5e050c68e281c7ba7"
WS = "ada392af0057260735104656"

def b62(i):
    A = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    s = ""
    while True:
        s = A[i % 62] + s
        i //= 62
        if not i:
            break
    return s

def b62v(s):
    A = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    v = 0
    for c in s:
        v = v * 62 + A.index(c)
    return v

def eid():
    return uuid.uuid4().hex[:20]

def conf(ps):
    s, h, b = o.get(f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/configuration")
    assert s == 200, (s, b)
    m = b.get("partStudioConfiguration") or b
    return m["sourceMicroversion"], m["serializationVersion"], m["libraryVersion"]

def mk_feature(ps, body):
    mv, sv, lv = conf(ps)
    call = {"btType": "BTFeatureDefinitionCall-1406", "feature": body,
            "serializationVersion": sv, "sourceMicroversion": mv, "libraryVersion": lv}
    s, _, b2 = o.post(f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/features", call)
    return s, b2

def delete_feature(ps, fid):
    s, _, b = o.delete(f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/features/featureid/{fid}")
    return s, b

def status_of(resp):
    """Extract (featureId, featureStatus) from a create-feature response."""
    if not isinstance(resp, dict):
        return None, str(resp)[:120]
    fs = resp.get("featureState") or {}
    st = fs.get("featureStatus") if isinstance(fs, dict) else str(resp)[:120]
    f = resp.get("feature") or {}
    fid = f.get("featureId") if isinstance(f, dict) else None
    if fid is None:
        fid = resp.get("featureId")
    return fid, st

def line_entity(p0, d, shared_end=None):
    return {"btType": "BTMSketchCurveSegment-155",
            "startPointId": eid(), "endPointId": shared_end or eid(),
            "startParam": 0.0, "endParam": 1.0,
            "geometry": {"btType": "BTCurveGeometryLine-117",
                         "pntX": p0[0], "pntY": p0[1], "dirX": d[0], "dirY": d[1]},
            "centerId": "", "internalIds": [], "curvedTextIds": [],
            "isConstruction": False, "parameters": [], "isFromSplineHandle": False,
            "isFromEndpointSplineHandle": False, "isFromSplineControlPolygon": False,
            "entityId": eid(), "namespace": "", "index": 0,
            "name": "", "hasUserCode": False}

def conic_entity(p0, p1, p2, rho, shared_end=None):
    """p0 start, p1 tangent-intersection control, p2 end."""
    return {"btType": "BTMSketchCurveSegment-155",
            "startPointId": eid(), "endPointId": shared_end or eid(),
            "startParam": 0.0, "endParam": 1.0,
            "geometry": {"btType": "BTCurveGeometryConic-2284",
                         "radius": 0, "xDir": 0, "yDir": 0, "xDir2": 0, "yDir2": 0,
                         "clockwise": False,
                         "rho": rho,
                         "points": [p0[0], p0[1], p1[0], p1[1], p2[0], p2[1]]},
            "centerId": "", "internalIds": [], "curvedTextIds": [],
            "isConstruction": False, "parameters": [], "isFromSplineHandle": False,
            "isFromEndpointSplineHandle": False, "isFromSplineControlPolygon": False,
            "entityId": eid(), "namespace": "", "index": 0,
            "name": "", "hasUserCode": False}

def circle_entity(cx, cy, r):
    return {"btType": "BTMSketchCurveSegment-155",
            "startPointId": eid(), "endPointId": eid(),
            "startParam": 0.0, "endParam": 1.0,
            "geometry": {"btType": "BTCurveGeometryCircle-115",
                         "radius": r, "xCenter": cx, "yCenter": cy,
                         "xDir": 0, "yDir": 0, "xDir2": 0, "yDir2": 0, "clockwise": False},
            "centerId": "", "internalIds": [], "curvedTextIds": [],
            "isConstruction": False, "parameters": [], "isFromSplineHandle": False,
            "isFromEndpointSplineHandle": False, "isFromSplineControlPolygon": False,
            "entityId": eid(), "namespace": "", "index": 0,
            "name": "", "hasUserCode": False}

def sketch_body(name, plane_id, entities):
    """Exactly the phase-0 working shape: sketchPlane IndividualQuery + disableImprinting."""
    q = {"btType": "BTMIndividualQuery-138", "deterministicIds": [plane_id]}
    return {"btType": "BTMSketch-151", "featureType": "newSketch", "name": name,
            "entities": entities, "constraints": [],
            "parameters": [
                {"btType": "BTMParameterQueryList-148", "parameterId": "sketchPlane",
                 "queries": [q]},
                {"btType": "BTMParameterBoolean-144", "parameterId": "disableImprinting",
                 "value": False}],
            "suppressed": False, "namespace": "", "hasUserCode": False}

def full_entities_filter():
    """The filter tree from the user's working extrude (phase 0)."""
    return {
        "btType": "BTAndFilter-110",
        "operand1": {
            "btType": "BTOrFilter-167",
            "operand1": {
                "btType": "BTAndFilter-110",
                "operand1": {
                    "btType": "BTAndFilter-110",
                    "operand1": {"btType": "BTFlatSheetMetalFilter-3018", "allows": "MODEL_AND_FLATTENED"},
                    "operand2": {"btType": "BTSketchObjectFilter-184",
                                 "isSketchObject": True, "objectType": "ANY_SKETCH_OBJECT"},
                },
                "operand2": {"btType": "BTEntityTypeFilter-124", "entityType": "FACE"},
            },
            "operand2": {
                "btType": "BTAndFilter-110",
                "operand1": {
                    "btType": "BTAndFilter-110",
                    "operand1": {"btType": "BTGeometryFilter-130", "geometryType": "PLANE"},
                    "operand2": {"btType": "BTFlatSheetMetalFilter-3018", "allows": "MODEL_ONLY"},
                },
                "operand2": {"btType": "BTEntityTypeFilter-124", "entityType": "FACE"},
            },
        },
        "operand2": {"btType": "BTConstructionObjectFilter-113", "isConstruction": False},
    }

def extrude_body(name, sketch_fid, depth_mm, operation, midplane=False):
    q = {"btType": "BTMParameterQueryList-148", "parameterId": "entities",
         "queries": [{"btType": "BTMIndividualSketchRegionQuery-140", "featureId": sketch_fid}],
         "filter": full_entities_filter()}
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
                {"btType": "BTMParameterBoolean-144", "parameterId": "midplane", "value": midplane},
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

def mass(ps):
    s, h, b = o.get(f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/massproperties")
    assert s == 200, (s, b)
    if isinstance(b, str):
        b = json.loads(b)
    out = {}
    for p in b.get("massProperties", []):
        out[p.get("bodyId")] = p
    return out

def main():
    outdir = os.path.join(os.path.dirname(__file__), "out", "ons")
    os.makedirs(outdir, exist_ok=True)
    state = json.load(open(os.path.join(outdir, "state.json"))) if os.path.exists(os.path.join(outdir, "state.json")) else {}

    # ------------------------------------------------- 1: find or create studio
    s, h, b = o.get(f"/documents/{DOC}/elements")
    els = b if isinstance(b, list) else b.get("items", [])
    ps = next((e["id"] for e in els if e.get("name") == "hook"), None)
    if ps is None:
        s, _, b2 = o.post(f"/partstudios/d/{DOC}/w/{WS}", {"name": "hook"})
        print("create studio:", s, "raw:", str(b2)[:200])
        assert s in (200, 201, 202), b2
        # response body may not carry the id -> re-list elements
        o.get(f"/documents/{DOC}/elements")
        s, h, b = o.get(f"/documents/{DOC}/elements")
        els = b if isinstance(b, list) else b.get("items", [])
        ps = next((e["id"] for e in els if e.get("name") == "hook"), None)
        assert ps, "hook studio not found after create"
        print("hook studio element:", ps)
    state["hook_ps"] = ps

    # ------------------------------------------------------- 2: probe planes
    if "planes" not in state:
        print("\n=== probing origin-plane short IDs (candidates around JDC=Top) ===")
        top_v = b62v("JDC")
        print("Top = JDC =", top_v)
        planes = {}
        for v in range(top_v - 9, top_v + 10):
            cid = b62(v)
            body = sketch_body(f"probe{cid}", cid, [line_entity((0.0, 0.0), (1.0, 0.0))])
            s, b2 = mk_feature(ps, body)
            fid, st = status_of(b2)
            tag = ""
            if s == 200 and st == "OK" and fid:
                ss, _, sb = o.get(f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/sketches")
                mat = None
                if ss == 200:
                    if isinstance(sb, str):
                        sb = json.loads(sb)
                    sks = sb if isinstance(sb, list) else sb.get("sketches", [])
                    for sk in sks:
                        if sk.get("featureId") == fid:
                            tm = sk.get("transformMatrix") or []
                            if len(tm) >= 12:
                                mat = [[tm[i * 4 + j] for j in range(4)] for i in range(4)]
                            break
                if mat:
                    lx = [mat[0][0], mat[1][0], mat[2][0]]
                    ly = [mat[0][1], mat[1][1], mat[2][1]]
                    n = [mat[0][2], mat[1][2], mat[2][2]]
                    kind = "Top" if abs(abs(n[2]) - 1) < 1e-6 else \
                           "Front?" if abs(abs(n[1]) - 1) < 1e-6 else \
                           "Right?" if abs(abs(n[0]) - 1) < 1e-6 else "?"
                    tag = (f"  [{kind}] x-axis={[round(c, 3) for c in lx]} "
                           f"y-axis={[round(c, 3) for c in ly]} normal={[round(c, 3) for c in n]}")
                    planes[cid] = {"kind": kind, "x": [round(c, 6) for c in lx],
                                   "y": [round(c, 6) for c in ly], "normal": [round(c, 6) for c in n]}
                delete_feature(ps, fid)
            print(f"  {cid} (v={v}): {s} {st or ''}{tag}")
        print("\nplanes found:", planes)
        state["planes"] = planes
        json.dump(state, open(os.path.join(outdir, "state.json"), "w"), indent=1)

    # --------------------------------------- 3: conic quarter-arc volume test
    if state.get("conic_test", {}).get("status") != "PASS" and state.get("conic_test", {}).get("status") != "SKIP":
        print("\n=== conic arc test: quarter circle r=10, extrude 5mm ===")
        R = 10.0
        p0 = (R, 0.0)          # start (phi=0)
        p2 = (0.0, R)          # end   (phi=90 CCW)
        pc = (R, R)            # tangent-intersection control point
        rho = math.cos(math.radians(90) / 2)
        e1 = conic_entity(p0, pc, p2, rho)
        e2 = line_entity(p2, (0.0, -1.0))
        e3 = line_entity((0.0, 0.0), (1.0, 0.0))
        s, b2 = mk_feature(ps, sketch_body("ArcTest2", "JDC", [e1, e2, e3]))
        fid, st = status_of(b2)
        print(f"sketch: {s} status={st} fid={fid}")
        if st != "OK":
            print("RAW:", json.dumps(b2)[:800])
            state["conic_test"] = {"status": "FAIL", "where": "sketch"}
            json.dump(state, open(os.path.join(outdir, "state.json"), "w"), indent=1)
            return
        s, b3 = mk_feature(ps, extrude_body("ArcExtrude2", fid, 5.0, "NEW"))
        fid2, st2 = status_of(b3)
        print(f"extrude: {s} status={st2} fid={fid2}")
        if st2 != "OK":
            print("RAW:", json.dumps(b3)[:800])
            state["conic_test"] = {"status": "FAIL", "where": "extrude"}
            json.dump(state, open(os.path.join(outdir, "state.json"), "w"), indent=1)
            return
        mp = mass(ps)
        total = 0.0
        for bid, p in mp.items():
            v = p.get("volume")
            if v:
                total += v
                print(f"  body {bid}: volume={v} m^3 = {v*1e9:.4f} mm^3")
        expected = math.pi * R * R / 4 * 5.0
        ok = abs(total * 1e9 - expected) < 0.05
        print(f"expected: {expected:.4f} mm^3 ; got: {total*1e9:.4f} mm^3")
        print("CONIC TEST:", "PASS" if ok else "FAIL")
        state["conic_test"] = {"status": "PASS" if ok else "FAIL",
                               "expected_mm3": expected, "got_mm3": total * 1e9,
                               "sketch_fid": fid, "extrude_fid": fid2}
        json.dump(state, open(os.path.join(outdir, "state.json"), "w"), indent=1)
    else:
        print("\nconic test already:", state["conic_test"])

if __name__ == "__main__":
    main()
