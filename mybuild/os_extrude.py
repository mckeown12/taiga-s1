"""Add an extrude of the phase-0 rectangle sketch, using BTMIndividualSketchRegionQuery
to reference the sketch region without knowing its server-assigned geometry id."""
import json
import osapi as o

DOC, WS, PS = "9482dce5e050c68e281c7ba7", "ada392af0057260735104656", "bde64379a9dae0454fbdef87"


def q(pid, queries, filter_):
    return {"btType": "BTMParameterQueryList-148", "queries": queries, "filter": filter_,
            "parameterId": pid}


def b(pid, v):
    return {"btType": "BTMParameterBoolean-144", "value": v, "parameterId": pid}


def e(pid, enumName, v):
    return {"btType": "BTMParameterEnum-145", "enumName": enumName, "value": v,
            "namespace": "", "parameterId": pid}


def num(pid, expr):
    return {"btType": "BTMParameterQuantity-147", "units": "", "value": 0.0,
            "isInteger": False, "expression": expr, "parameterId": pid}


def build_extrude(sketch_feature_id, depth="25 mm"):
    region_query = {"btType": "BTMIndividualSketchRegionQuery-140",
                    "featureId": sketch_feature_id}
    entities = q("entities", [region_query],
                 {"btType": "BTConstructionObjectFilter-113", "isConstruction": False})
    return {
        "btType": "BTMFeature-134",
        "featureType": "extrude",
        "name": "Extrude 1",
        "parameters": [
            e("domain", "OperationDomain", "MODEL"),
            e("bodyType", "ExtendedToolBodyType", "SOLID"),
            e("operationType", "NewBodyOperationType", "NEW"),
            e("surfaceOperationType", "NewSurfaceOperationType", "NEW"),
            e("flatOperationType", "FlatOperationType", "REMOVE"),
            entities,
            b("midplane", False),
            num("thickness", "5 mm"),
            b("flipWall", False),
            num("thickness1", "5 mm"),
            num("thickness2", "0 mm"),
            e("endBound", "BoundingType", "BLIND"),
            b("oppositeDirection", False),
            num("depth", depth),
        ],
        "suppressed": False,
        "namespace": "",
        "hasUserCode": False,
    }


def main():
    # find the sketch feature id
    s, h, b = o.get(f"/partstudios/d/{DOC}/w/{WS}/e/{PS}/features")
    assert s == 200
    sk = [f for f in b["features"] if f.get("typeName") == "BTMSketch"][0]
    fid = sk["message"]["featureId"]
    print("sketch featureId:", fid)

    call = {
        "btType": "BTFeatureDefinitionCall-1406",
        "feature": build_extrude(fid),
        "serializationVersion": b.get("serializationVersion"),
        "sourceMicroversion": b.get("sourceMicroversion"),
        "libraryVersion": b.get("libraryVersion"),
    }
    s2, h2, b2 = o.post(f"/partstudios/d/{DOC}/w/{WS}/e/{PS}/features", call)
    print("add extrude ->", s2)
    if s2 != 200:
        print(json.dumps(b2)[:2000])
        return

    # verify
    s3, _, b3 = o.get(f"/partstudios/d/{DOC}/w/{WS}/e/{PS}/features")
    for f in b3["features"]:
        m = f.get("message", {})
        print(f.get("typeName"), "|", m.get("name"), "| featureId:", m.get("featureId"))
    s4, _, b4 = o.get(f"/partstudios/d/{DOC}/w/{WS}/e/{PS}/massproperties")
    print("mass:", json.dumps(b4)[:400])


if __name__ == "__main__":
    main()
