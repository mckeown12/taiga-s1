"""Debug/fix the phase-0 extrude: replace its entities filter with the full
filter tree taken from the user's working extrude (sketch-object + FACE + PLANE
+ non-construction), keeping the BTMIndividualSketchRegionQuery."""
import json
import osapi as o

DOC, WS, PS = "9482dce5e050c68e281c7ba7", "ada392af0057260735104656", "bde64379a9dae0454fbdef87"

SKETCH_FID = "FVjyQOHceULvz10_1"
EXTRUDE_FID = "FYVYQXAVe7AAsRD_1"


def full_entities_filter():
    return {
        "btType": "BTAndFilter-110",
        "operand1": {
            "btType": "BTOrFilter-167",
            "operand1": {
                "btType": "BTAndFilter-110",
                "operand1": {
                    "btType": "BTAndFilter-110",
                    "operand1": {
                        "btType": "BTFlatSheetMetalFilter-3018", "allows": "MODEL_AND_FLATTENED"},
                    "operand2": {
                        "btType": "BTSketchObjectFilter-184",
                        "isSketchObject": True, "objectType": "ANY_SKETCH_OBJECT"},
                },
                "operand2": {"btType": "BTEntityTypeFilter-124", "entityType": "FACE"},
            },
            "operand2": {
                "btType": "BTAndFilter-110",
                "operand1": {
                    "btType": "BTAndFilter-110",
                    "operand1": {
                        "btType": "BTGeometryFilter-130", "geometryType": "PLANE"},
                    "operand2": {
                        "btType": "BTFlatSheetMetalFilter-3018", "allows": "MODEL_ONLY"},
                },
                "operand2": {"btType": "BTEntityTypeFilter-124", "entityType": "FACE"},
            },
        },
        "operand2": {"btType": "BTConstructionObjectFilter-113", "isConstruction": False},
    }


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


def main():
    s, h, meta = o.get(f"/partstudios/d/{DOC}/w/{WS}/e/{PS}/features")
    feature = {
        "btType": "BTMFeature-134",
        "featureType": "extrude",
        "featureId": EXTRUDE_FID,
        "name": "Extrude 1",
        "parameters": [
            e("domain", "OperationDomain", "MODEL"),
            e("bodyType", "ExtendedToolBodyType", "SOLID"),
            e("operationType", "NewBodyOperationType", "NEW"),
            e("surfaceOperationType", "NewSurfaceOperationType", "NEW"),
            e("flatOperationType", "FlatOperationType", "REMOVE"),
            q("entities",
              [{"btType": "BTMIndividualSketchRegionQuery-140", "featureId": SKETCH_FID}],
              full_entities_filter()),
            b("midplane", False),
            num("thickness", "5 mm"),
            b("flipWall", False),
            num("thickness1", "5 mm"),
            num("thickness2", "0 mm"),
            e("endBound", "BoundingType", "BLIND"),
            b("oppositeDirection", False),
            num("depth", "25 mm"),
        ],
        "suppressed": False,
        "namespace": "",
        "hasUserCode": False,
    }
    call = {
        "btType": "BTUpdateFeaturesCall-1748",
        "features": [feature],
        "serializationVersion": meta.get("serializationVersion"),
        "sourceMicroversion": meta.get("sourceMicroversion"),
        "libraryVersion": meta.get("libraryVersion"),
    }
    s2, _, b2 = o.post(f"/partstudios/d/{DOC}/w/{WS}/e/{PS}/features/updates", call)
    print("update extrude ->", s2)
    print(json.dumps(b2)[:800] if isinstance(b2, dict) else b2)

    s4, _, b4 = o.get(f"/partstudios/d/{DOC}/w/{WS}/e/{PS}/massproperties")
    print("mass:", json.dumps(b4.get("bodies"))[:300])


if __name__ == "__main__":
    main()
