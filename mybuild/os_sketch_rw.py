"""Convert a read-format BTMSketch to write format (BTMSketch-151 body),
optionally rewriting the sketchPlane geometry id, and add it to a part studio.

Usage:
    from os_sketch_rw import read_sketch, to_write, add_sketch
"""
import json
import osapi as o

PARAM_BT = {
    "BTMParameterString": "BTMParameterString-149",
    "BTMParameterEnum": "BTMParameterEnum-145",
    "BTMParameterQuantity": "BTMParameterQuantity-147",
    "BTMParameterBoolean": "BTMParameterBoolean-144",
    "BTMParameterQueryList": "BTMParameterQueryList-148",
}


def w_query(q):
    """read-format query -> write format (IndividualQuery only; others pass through)"""
    qm = q["message"]
    if q["typeName"] == "BTMIndividualQuery":
        return {"btType": "BTMIndividualQuery-138", "geometryIds": qm["geometryIds"]}
    if q["typeName"] == "BTMIndividualSketchRegionQuery":
        return {"btType": "BTMIndividualSketchRegionQuery-140",
                **{k: v for k, v in qm.items() if v not in (None, "", [], False)
                   and k not in ("type", "typeName")}}
    return {"btType": f'{q["typeName"]}-{q["type"]}',
            **{k: v for k, v in qm.items() if v not in (None, "", [], False)}}


def w_filter(f):
    """read-format filter -> write format"""
    if not isinstance(f, dict):
        return f
    tn, t = f.get("typeName"), f.get("type")
    fm = f.get("message", {})
    if tn is None:
        return None  # type-0 "any" filter -> omit
    out = {"btType": f"{tn}-{t}"}
    for k, v in fm.items():
        if isinstance(v, dict) and "typeName" in v:
            out[k] = w_filter(v)
        else:
            out[k] = v
    return out


def w_param(p):
    pm = p["message"]
    pid = p["typeName"]
    if pid == "BTMParameterQueryList":
        out = {"btType": "BTMParameterQueryList-148",
               "queries": [w_query(q) for q in pm["queries"]],
               "parameterId": pm["parameterId"]}
        flt = w_filter(pm.get("filter"))
        if flt is not None:
            out["filter"] = flt
        return out
    if pid == "BTMParameterBoolean":
        return {"btType": "BTMParameterBoolean-144", "value": pm["value"], "parameterId": pm["parameterId"]}
    if pid == "BTMParameterString":
        return {"btType": "BTMParameterString-149", "value": pm["value"], "parameterId": pm["parameterId"]}
    if pid == "BTMParameterEnum":
        return {"btType": "BTMParameterEnum-145", "enumName": pm["enumName"],
                "value": pm["value"], "namespace": pm.get("namespace", ""),
                "parameterId": pm["parameterId"]}
    if pid == "BTMParameterQuantity":
        return {"btType": "BTMParameterQuantity-147", "units": pm.get("units", ""),
                "value": pm.get("value", 0.0), "isInteger": pm.get("isInteger", False),
                "expression": pm.get("expression", ""), "parameterId": pm["parameterId"]}
    raise ValueError(pid)


def w_entity(e):
    em = e["message"]
    g = em["geometry"]["message"]
    gbt = f'{em["geometry"]["typeName"]}-{em["geometry"]["type"]}'
    geom = {"btType": gbt}
    for k in ("pntX", "pntY", "dirX", "dirY", "pntZ", "dirZ", "pnt", "dir",
              "pntX1", "pntY1", "pntX2", "pntY2", "pntX3", "pntY3",
              "radius", "startAngle", "endAngle", "arcLength", "sweepAngle"):
        if k in g:
            geom[k] = g[k]
    return {"btType": "BTMSketchCurveSegment-155",
            "startPointId": em["startPointId"],
            "endPointId": em["endPointId"],
            "startParam": em["startParam"],
            "endParam": em["endParam"],
            "geometry": geom,
            "centerId": em.get("centerId", ""),
            "internalIds": em.get("internalIds", []),
            "curvedTextIds": em.get("curvedTextIds", []),
            "isConstruction": em.get("isConstruction", False),
            "parameters": [],
            "isFromSplineHandle": em.get("isFromSplineHandle", False),
            "isFromEndpointSplineHandle": em.get("isFromEndpointSplineHandle", False),
            "isFromSplineControlPolygon": em.get("isFromSplineControlPolygon", False),
            "entityId": em["entityId"],
            "namespace": em.get("namespace", ""),
            "index": em.get("index", 0),
            "name": em.get("name", ""),
            "hasUserCode": em.get("hasUserCode", False),
            }


def w_constraint(c):
    cm = c["message"]
    return {"btType": "BTMSketchConstraint-2",
            "constraintType": cm["constraintType"],
            "parameters": [w_param(p) for p in cm["parameters"]],
            "entityId": cm.get("entityId", ""),
            "namespace": cm.get("namespace", ""),
            "name": cm.get("name", ""),
            "hasUserCode": cm.get("hasUserCode", False),
            }


def to_write(sk_msg, plane_id=None, name=None):
    body = {
        "btType": "BTMSketch-151",
        "featureType": "newSketch",
        "name": name or sk_msg.get("name", "Sketch 1"),
        "entities": [w_entity(e) for e in sk_msg.get("entities", [])],
        "constraints": [w_constraint(c) for c in sk_msg.get("constraints", [])],
        "parameters": [w_param(p) for p in sk_msg.get("parameters", [])],
        "suppressed": False,
        "namespace": "",
        "hasUserCode": False,
    }
    if plane_id is not None:
        for p in body["parameters"]:
            if p.get("parameterId") == "sketchPlane":
                for q in p.get("queries", []):
                    if "geometryIds" in q:
                        q["geometryIds"] = [plane_id]
    return body


def read_sketch(doc, ws, ps):
    s, h, b = o.get(f"/partstudios/d/{doc}/w/{ws}/e/{ps}/features")
    assert s == 200, (s, b)
    sk = [f for f in b["features"] if f.get("typeName") == "BTMSketch"][0]
    return sk, b


def add_sketch(doc, ws, ps, body):
    s, h, meta = o.get(f"/partstudios/d/{doc}/w/{ws}/e/{ps}/features")
    assert s == 200
    call = {"btType": "BTFeatureDefinitionCall-1406", "feature": body,
            "serializationVersion": meta.get("serializationVersion"),
            "sourceMicroversion": meta.get("sourceMicroversion"),
            "libraryVersion": meta.get("libraryVersion")}
    s2, _, b2 = o.post(f"/partstudios/d/{doc}/w/{ws}/e/{ps}/features", call)
    return s2, b2


if __name__ == "__main__":
    # replay the user's hook sketch onto the probe studio's cube face
    src = ("3fe296226cf9309795c1c6cc", "c1d5d75daf3df90e2343cb2f", "6b6e869533ee4d9928a32dfd")
    # main test studio has the cube; its top face (normal +Z) is JHK
    dst = ("9482dce5e050c68e281c7ba7", "ada392af0057260735104656", "bde64379a9dae0454fbdef87")
    sk, _ = read_sketch(*src)
    body = to_write(sk["message"], plane_id="JHK", name="Replay")
    s2, b2 = add_sketch(*dst, body)
    print("replay sketch ->", s2)
    print(json.dumps(b2.get("featureState"), indent=1) if isinstance(b2, dict) else b2)
