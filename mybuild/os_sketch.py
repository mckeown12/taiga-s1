"""Add a fully-constrained rectangle sketch (40 x 20 mm) to the phase-0 test
part studio via the OnShape features API, then extrude it.

Wire format (write): BTFeatureDefinitionCall-1406 wrapper around BTMSketch-151.
Entity IDs are 12-char base62 strings we generate; the server accepts them.
"""
import json
import osapi as o

DOC, WS, PS = "9482dce5e050c68e281c7ba7", "ada392af0057260735104656", "bde64379a9dae0454fbdef87"

W, H = 0.040, 0.020  # meters


def eid(tag):
    # deterministic 12-char base62 entity id
    import hashlib
    h = hashlib.md5(tag.encode()).hexdigest()
    return h[:12].upper()[:12]


def line(x0, y0, x1, y1, tag):
    return {
        "btType": "BTMSketchCurveSegment-155",
        "startPointId": f"{eid(tag)}.start",
        "endPointId": f"{eid(tag)}.end",
        "startParam": 0.0,
        "endParam": 1.0,
        "geometry": {
            "btType": "BTCurveGeometryLine-117",
            "pntX": x0, "pntY": y0,
            "dirX": x1 - x0, "dirY": y1 - y0,
        },
        "isConstruction": False,
        "entityId": eid(tag),
        "namespace": "",
        "name": "",
        "hasUserCode": False,
    }


def coincident(a, b):
    return {
        "btType": "BTMSketchConstraint-2",
        "constraintType": "COINCIDENT",
        "parameters": [
            {"btType": "BTMParameterString-149", "value": a, "parameterId": "localFirst"},
            {"btType": "BTMParameterString-149", "value": b, "parameterId": "localSecond"},
        ],
        "entityId": eid("c_" + a + b),
        "namespace": "",
        "name": "",
        "hasUserCode": False,
    }


def orient(kind, ent):
    return {
        "btType": "BTMSketchConstraint-2",
        "constraintType": kind,
        "parameters": [
            {"btType": "BTMParameterString-149", "value": ent, "parameterId": "localFirst"},
        ],
        "entityId": eid(kind + "_" + ent),
        "namespace": "",
        "name": "",
        "hasUserCode": False,
    }


def length(ent, mm):
    return {
        "btType": "BTMSketchConstraint-2",
        "constraintType": "LENGTH",
        "parameters": [
            {"btType": "BTMParameterString-149", "value": ent, "parameterId": "localFirst"},
            {"btType": "BTMParameterEnum-145", "enumName": "DimensionDirection", "value": "MINIMUM",
             "parameterId": "direction"},
            {"btType": "BTMParameterQuantity-147", "units": "", "value": 0.0, "isInteger": False,
             "expression": f"{mm} mm", "parameterId": "length"},
        ],
        "entityId": eid("len_" + ent),
        "namespace": "",
        "name": "",
        "hasUserCode": False,
    }


def build_sketch(plane_id="Top"):
    e1, e2, e3, e4 = (eid(t) for t in ("l1", "l2", "l3", "l4"))
    entities = [
        line(0.0, 0.0, W, 0.0, "l1"),
        line(W, 0.0, W, H, "l2"),
        line(W, H, 0.0, H, "l3"),
        line(0.0, H, 0.0, 0.0, "l4"),
    ]
    constraints = [
        coincident(f"{e1}.end", f"{e2}.start"),
        coincident(f"{e2}.end", f"{e3}.start"),
        coincident(f"{e3}.end", f"{e4}.start"),
        coincident(f"{e4}.end", f"{e1}.start"),
        orient("HORIZONTAL", e1), orient("HORIZONTAL", e3),
        orient("VERTICAL", e2), orient("VERTICAL", e4),
        length(e1, 40), length(e2, 20),
    ]
    return {
        "btType": "BTMSketch-151",
        "featureType": "newSketch",
        "name": "Sketch 1",
        "featureId": "Sketch 1",
        "entities": entities,
        "constraints": constraints,
        "parameters": [
            {"btType": "BTMParameterQueryList-148",
             "queries": [{"btType": "BTMIndividualQuery-138", "geometryIds": [plane_id]}],
             "parameterId": "sketchPlane"},
            {"btType": "BTMParameterBoolean-144", "value": False, "parameterId": "disableImprinting"},
        ],
        "suppressed": False,
        "namespace": "",
        "hasUserCode": False,
    }


def add_feature(body, name):
    s, h, meta = o.get(f"/partstudios/d/{DOC}/w/{WS}/e/{PS}/features")
    assert s == 200, (s, meta)
    call = {
        "btType": "BTFeatureDefinitionCall-1406",
        "feature": body,
        "serializationVersion": meta.get("serializationVersion"),
        "sourceMicroversion": meta.get("sourceMicroversion"),
        "libraryVersion": meta.get("libraryVersion"),
    }
    s2, h2, b2 = o.post(f"/partstudios/d/{DOC}/w/{WS}/e/{PS}/features", call)
    print("add_feature", name, "->", s2)
    if s2 != 200:
        print(json.dumps(b2)[:1500])
    return s2, b2


if __name__ == "__main__":
    body = build_sketch()
    add_feature(body, "sketch")
    # read back status
    s, h, b = o.get(f"/partstudios/d/{DOC}/w/{WS}/e/{PS}/features")
    for f in b["features"]:
        m = f.get("message", {})
        print(f.get("typeName"), "|", m.get("name"), "|", m.get("featureId"))
