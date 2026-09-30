# OnShape: FreeCAD translation + a local AI for OnShape models

Research report (2026-09-29). Goal: (a) translate FreeCAD models to OnShape,
(b) a *local* AI model that makes/tweaks OnShape models — i.e. port the
Taiga-S1 approach (goal -> typed-token state -> valid action -> numerics from
goal) to the OnShape cloud API.

## Verdict

**Feasible, and a better fit than expected.** OnShape's feature model is
structurally identical to what Taiga-S1 already speaks:

| Taiga-S1 (FreeCAD PartDesign) | OnShape API |
|---|---|
| feature tree node: TypeId + parameters | `BtmFeature`: `feature_type` + `parameters{}` + `sub_features[]` + `suppressed` |
| `enumerate_actions(state)` — valid commands now | `get_feature_specs` — OnShape publishes **machine-readable schemas of every creatable feature** (params, groups, ui_hints, filter_selectors) |
| sketch: geometry + constraints | sketch: entities (LINE/ARC/CIRCLE/ELLIPSE/SPLINE...) + constraints (COINCIDENT, TANGENT, PARALLEL, PERPENDICULAR, HORIZONTAL, VERTICAL, EQUAL, ANGLE, LENGTH, DIAMETER, RADIUS, FIX, ...) + dimensions |
| executor writes numerics from goal | `add_feature`/`update_feature` with a params dict |
| "tweak a model" | **native**: `update_feature` changes any feature's parameters downstream-safe |

Two complementary paths (do both, in this order):

1. **Feature-level translator** FreeCAD PartDesign <-> OnShape feature tree
   (days of work). Makes existing Taiga builds (incl. the hook) editable
   OnShape parts, and pulls OnShape parts into FreeCAD.
2. **Native OnShape policy** ("taiga-os1"): port Taiga-S1's runtime layer to
   the OnShape API (2-4 weeks). The local model drives cloud OnShape exactly
   as it drives local FreeCAD today.

## What was verified (and where)

- `api.onshape.com` is up and reachable. **`developer.onshape.com` does not
  resolve from this machine right now** (DNS empty; browser proxy also fails),
  so the docs site was unavailable during research — items marked
  *needs-verification* below must be confirmed in the Phase-0 smoke test.
- Official Python SDK **`onshape-client` 1.6.3** (PyPI; OpenAPI-generated,
  885 files) — downloaded and inspected; this is the authoritative API surface.
  27 API groups (documents, parts, assemblies, drawings, folders, webhooks,
  feature_studios, ...).
- Auth: OAuth2 authorization-code flow (SDK ships `oauth/local_server.py`);
  personal access tokens are the practical route for a local agent
  (*where they're created in the UI: needs-verification*).

### Key endpoints (all verified in SDK)

| op | use |
|---|---|
| `POST /documents`, `POST /parts` | fresh workspace per episode |
| `GET .../features` | feature tree (state snapshot) |
| `GET .../feature_specs` | **the action catalogue**: every feature type with full parameter schemas |
| `POST .../features`, `PUT .../features` | create / tweak (tweak = the "adjust my model" use case) |
| `DELETE .../features/{id}` | remove a feature (no undo API exists — recovery must use this + update) |
| `GET .../sketch_info` | sketch entities/constraints (state) |
| `POST .../sketches` | create sketch (entities + constraints + dimensions in one call) |
| `GET .../step` (+ stl, 3mf, wmv) | exports — used for eval (mesh IoU) and the dumb-solid fallback |
| `POST .../eval_feature_script` | server-side scripting (power tool; not needed for the policy) |

Sketch constraint enum from the SDK (filter enum; the full list is in the
docs — note SYMMETRIC is in the product UI but missing from this enum,
*needs-verification*): ANGLE, COINCIDENT, CONCENTRIC, DIAMETER, DISTANCE,
EQUAL, FIX, HORIZONTAL, LENGTH, MIDPOINT, NORMAL, PARALLEL, PERPENDICULAR,
PIERCE, PROJECTED, QUADRANT, RADIUS, TANGENT, VERTICAL (+ pattern/derived
variants).

## FreeCAD <-> OnShape vocabulary map

| Taiga-S1 action (FreeCAD PartDesign) | OnShape feature |
|---|---|
| sketch on datum plane | sketch on plane (local coords) |
| Pad | Extrude |
| Revolve | Revolve |
| Sweep (**our hook_sweep**) | **Sweep (profile + path) — built-in 1:1** |
| Loft | Loft |
| Hole (ISO M4 clearance) | Hole (diameter/depth/thread types incl. M4) |
| Fillet / Chamfer | Fillet / Chamfer (edge refs) |
| Shell | Shell |
| Mirror | Mirror |
| LinearPattern / CircularPattern | LinearPattern / CircularPattern |
| PartDesign::Boolean (our fuse) | **not needed** — OnShape auto-fuses overlapping features within one body |

Notable differences:
- **No undo API.** Taiga's recovery behavior (undo off-plan changes) becomes
  `delete_feature`/`update_feature`; the action catalogue needs those two.
- **Units** are document-level (default inches, *needs-verification*): API
  numbers are unitless — set/confirm during Phase 0; the policy's goal
  sampler works in mm, so a fixed unit mode is required.
- **Rate limits** are the one real bottleneck for data generation
  (*exact numbers: needs-verification* — docs site down).

## Path 1: translator (quick win)

- **FC -> OnShape:** walk the Body's feature chain in order; for each sketch
  emit entities + constraints + dimensions (near-1:1 name mapping); for each
  feature emit the params per the table above, calling `add_feature` in
  chain order. Verify: download STEP from OnShape, mesh it, compare IoU to
  the FreeCAD solid (target 1.0) + feature-count/structure match.
- **OnShape -> FreeCAD:** `get_features` + `get_sketch_info`, then replay
  through the existing `runtime/session.py` executors (`ex_pad`, `ex_hole`,
  ...) which already build FreeCAD features from param dicts — **~half the
  code already exists** from the Taiga-S1 fork.
- Fallback (always available, but not editable): STEP export/import both ways.

Deliverable: `mybuild/onshape_bridge.py` — `to_onshape(part.FCStd, token, doc)`
and `from_onshape(doc, out_dir)`; run it on the hook as the test case.

## Path 2: native policy (taiga-os1)

Keep unchanged: model architecture (typed-token transformer, 1.2M params),
goal system + parameterization, expert teacher logic, DAgger loop, eval
framework.

Replace:
- `runtime/worker.py` + `session.py` -> `onsession.py`: one OnShape document
  per episode (parallel documents), snapshot = `get_features` + sketch info
  (cached between mutations), action = POST/PUT feature/sketch calls.
- Action catalogue re-targeted to OnShape features (use `get_feature_specs`
  output as the source of truth for parameter schemas).
- Featurize: same grammar, new words (~40 actions, ~20 node types).

Cost model: ~590k decisions (same data as the FreeCAD model) x ~2 calls/step
= ~1.2M API calls. At a per-document rate limit with N parallel documents
this is hours-to-a-day of wall time, not CPU-bound like FreeCAD was. The
early-Done and composition regressions from the hook retrain (NOTES.md v1->v3)
apply here too — train with long levels + comp episodes from round 1.

Eval: per-step accuracy on held-out states + end-to-end IoU (STEP download,
mesh, compare vs expert-built reference) + feature-tree agreement.

## Unknowns for the Phase-0 smoke test (status after smoke test)

1. Rate limits — **RESOLVED**: per-endpoint-family and per-account; each family
   (features, massproperties, configuration, sketches, documents, ...) has its own
   3000-call budget. `features` GET budget exhausted by the plane-ID sweep ->
   `Retry-After: 35664s` (~10h). Workaround found: the `configuration` endpoint
   (separate pool) returns `serializationVersion`, `sourceMicroversion`,
   `libraryVersion` — everything a write call needs.
2. Units — **RESOLVED**: wire format and mass properties are SI (m, m^3);
   quantity parameters take an `expression` string ("10 mm") that carries units.
3. PAT creation UI + scopes — **RESOLVED**: API key/secret from account settings;
   HMAC signing implemented in `osapi.py` (scheme extracted from the SDK).
4. SWEEP feature param shape — open (phase 1): spec available via the feature
   catalogue (see WS capture technique below).
5. Free plan API access — **RESOLVED**: works; new documents must be public
   (`isPublic: true`) on the free plan (409 on private).

## Phase-0 result: full write loop VERIFIED (sketch + extrude via pure REST)

A closed-rectangle sketch on the **Top origin plane** and a 10 mm blind extrude
were created through REST calls only (no UI, no SDK), and the resulting solid was
verified by `massproperties`: **volume = 2.000e-6 m^3 = 2000 mm^3 exactly**
(20 x 10 x 10 mm). The block renders live in the OnShape UI (same workspace
session syncs the REST mutations in real time).

### The three blockers and their resolutions

**1. Sketch on an origin plane failed with featureStatus ERROR
("Select a sketch plane" / param value `Item: Nothing`).**

Root cause: `geometryIds` is a **read-format-only** field. The write format of
`BTMIndividualQuery-138` uses **`deterministicIds`**; `geometryIds` in a write
body is silently ignored, so the plane query resolved to nothing.

Wire evidence (captured from the UI's websocket, see below): the UI sends
`sketchPlane -> JDC (type "Face") -> nodeId -> "Top.planeOp"`.

Working write query:
```json
{"btType": "BTMIndividualQuery-138", "deterministicIds": ["JDC"]}
```

**2. Origin-plane short IDs were invisible to REST.**

Exhausted all 248 endpoints in the official OpenAPI spec (`GET /openapi`),
including SDK-missing `fstable`, `featurescriptrepresentation`, `gltf` — none
expose origin-plane geometry IDs. The UI gets them via the websocket state
channel. Two working solutions:
- **Fixed IDs**: origin planes have deterministic short IDs across part
  studios: **Top = `JDC`** (verified in two different documents; wire type
  `Face`, entity name `Top.planeOp`). Front/Right IDs can be captured the same
  way if needed (only Top is needed for the hook: flange, boss and hook all
  sketch on the Top plane).
- **WebSocket capture** (general technique, used throughout):
  `page.addInitScript` monkey-patches `window.WebSocket` to log every text
  frame into `window.__wsLog` (list of `{ws, events:[{dir,s}]}`). Bootstrap
  frames contain the full feature-parameter catalogue (all 97 feature types
  with param ids, enums, unit nodeIds), the geometry ID table, and every
  feature definition. UI operations (plane select, extrude commit) are sent
  as operations whose frames include the relevant short IDs — e.g. plane
  select sends `"Add entity : Sketch plane"` + `JDC` + nodeIds.

**3. Stale `sourceMicroversion` -> 404 "Not found" on POST /features.**

Any concurrent mutation (UI or API, another client on the same workspace)
advances the microversion. Fix: fetch `configuration` (cheap, separate rate
budget) immediately before each write call and use its `sourceMicroversion`,
`serializationVersion` ("1.2.21") and `libraryVersion` (3083).

### Verified write-format recipes

Sketch (new feature, `POST /partstudios/d/{doc}/w/{ws}/e/{eid}/features` with
`BTFeatureDefinitionCall-1406` wrapping a `BTMSketch-151` body):
- lines: `BTMSketchCurveSegment-155` + `BTCurveGeometryLine-117`
  (`pntX,pntY,dirX,dirY` in **meters**); entity/node ids are assigned by the
  server on create (client sends md5-style ids, server echoes nodeIds back).
- plane: `sketchPlane` = `BTMParameterQueryList-148` with
  `[BTMIndividualQuery-138 {deterministicIds:["JDC"]}]` +
  `disableImprinting` = `BTMParameterBoolean-144`.
- **Constraints are optional**: 4 lines with exactly matching endpoints form a
  closed region with zero constraints (the UI only *warns* "not fully defined"
  and refuses interactive selection; the REST extrude of such a region works).

Extrude (`BTMFeature-134` body, `featureType: "extrude"`):
```json
"parameters": [
  {"btType":"BTMParameterEnum-145","enumName":"OperationDomain","value":"MODEL","namespace":"","parameterId":"domain"},
  {"btType":"BTMParameterEnum-145","enumName":"ExtendedToolBodyType","value":"SOLID","namespace":"","parameterId":"bodyType"},
  {"btType":"BTMParameterEnum-145","enumName":"NewBodyOperationType","value":"NEW","namespace":"","parameterId":"operationType"},
  {"btType":"BTMParameterQueryList-148","parameterId":"entities",
   "queries":[{"btType":"BTMIndividualSketchRegionQuery-140","featureId":"<sketch_feature_id>"}],
   "filter": {"btType":"BTAndFilter-110","operand1":{"btType":"BTOrFilter-167",
     "operand1":{"btType":"BTAndFilter-110",
       "operand1":{"btType":"BTAndFilter-110",
         "operand1":{"btType":"BTFlatSheetMetalFilter-3018","allows":"MODEL_AND_FLATTENED"},
         "operand2":{"btType":"BTSketchObjectFilter-184","isSketchObject":true,"objectType":"ANY_SKETCH_OBJECT"}},
       "operand2":{"btType":"BTEntityTypeFilter-124","entityType":"FACE"}},
     "operand2":{"btType":"BTAndFilter-110",
       "operand1":{"btType":"BTAndFilter-110",
         "operand1":{"btType":"BTGeometryFilter-130","geometryType":"PLANE"},
         "operand2":{"btType":"BTFlatSheetMetalFilter-3018","allows":"MODEL_ONLY"}},
       "operand2":{"btType":"BTEntityTypeFilter-124","entityType":"FACE"}}},
   "operand2":{"btType":"BTConstructionObjectFilter-113","isConstruction":false}}},
  {"btType":"BTMParameterBoolean-144","value":false,"parameterId":"midplane"},
  {"btType":"BTMParameterQuantity-147","units":"","value":0.0,"isInteger":false,"expression":"5 mm","parameterId":"thickness"},
  {"btType":"BTMParameterBoolean-144","value":false,"parameterId":"flipWall"},
  {"btType":"BTMParameterQuantity-147","units":"","value":0.0,"isInteger":false,"expression":"5 mm","parameterId":"thickness1"},
  {"btType":"BTMParameterQuantity-147","units":"","value":0.0,"isInteger":false,"expression":"0 mm","parameterId":"thickness2"},
  {"btType":"BTMParameterEnum-145","enumName":"BoundingType","value":"BLIND","namespace":"","parameterId":"endBound"},
  {"btType":"BTMParameterBoolean-144","value":false,"parameterId":"oppositeDirection"},
  {"btType":"BTMParameterQuantity-147","units":"","value":0.0,"isInteger":false,"expression":"10 mm","parameterId":"depth"}
]
```
Notes: the region is selected by sketch `featureId` + filter tree (no region
short ID needed); `depth`/`thickness*` use unit-bearing `expression` strings;
`BTMFeature-134` (base type) serializes fine for extrude. Updates use
`POST .../features/updates` with `BTUpdateFeaturesCall-1748` (returns
`featureStates` — the feedback loop); deletes use
`DELETE .../features/featureid/{fid}`; rollback via `POST .../features/rollback`
(`BTSetFeatureRollbackCall-1899`, `rollbackIndex`).

### Operational notes
- Write headers: Content-Type **and** Accept must be
  `application/vnd.onshape.v2+json;charset=utf-8;qs=0.2` (plain JSON -> 400).
- OnShape auto-fuses overlapping features in one body (no boolean step needed,
  unlike the FreeCAD PartDesign::Boolean workaround).
- No undo API: recovery = delete/update feature or rollback.
- Empty UI sketches are session-only: they have a featureId while the sketch
  tool is open but are not persisted features (DELETE -> 404 once abandoned).
- Both a headless and a user browser can be attached to the same workspace
  concurrently; every REST mutation syncs into both UIs live, and UI actions
  advance the microversion seen by the next REST call (hence the
  configuration-refresh-before-write rule).

## Phases

| phase | work | effort |
|---|---|---|
| 0 | account + PAT; create doc -> sketch -> extrude -> hole -> fillet -> STEP; measure latency/rate/units | half day | **DONE** — see "Phase-0 result" above (sketch+extrude+mass-verify via pure REST; holes/fillets/STEP export still to exercise) |
| 1 | translator both directions; hook as test part | 1-2 weeks |
| 2 | taiga-os1: runtime port, datagen, SFT+DAgger, eval to parity (hook + original suites) | 2-4 weeks |

Requires from you: an OnShape account (any plan that allows API use) and a
personal access token.

## Phase-1 result: the J-hook, built by hand via pure REST (2026-09-30)

The complete wall hook (46×46×4 flange w/ 2× Ø4.3 holes, Ø26 boss to z=24,
7×3.5 J-strap U-opening toward the wall) was built feature-by-feature through
`osapi.py` — no UI, no SDK — in public doc `9482dce5e050c68e281c7ba7`,
part studio `fa03fcc92b16395e6db6ad62` ("HookFinal").

### Feature chain (all `POST .../features` with fresh `configuration` microversion)

1. **Flange sketch** on Top plane `JDC`: 46×46 rounded rect (3 mm corner
   fillets as 8-seg arcs) **with the two M4 holes as inner loops** (32-gons,
   r 2.15, x=±17) — extrude has no CUT operation, so holes are inner
   boundaries, single `NEW` extrude 4 mm.
2. **Boss**: circle sketch (64-gon — real circles are inert as region
   boundaries) r 13, extrude `NEW` 24 mm from z=0 (auto-fuses with flange).
3. **Step**: 30×30×2 plate (cosmetic; sits inside the flange).
4. **Strap** — the interesting part (datum planes are unaddressable via REST;
   see recipe below):
   - profile polyline of `hook_shape.make_hook` (z0=23, arm 20, U r5.5, tip
     10) **plotted on the Top (XY) plane with y' = world-z**; all three
     semicircles as 8-segment polygon chains (`strap_poly.py`, 30 line
     entities, meters);
   - extrude `NEW` 7 mm in +Z (the slab that will become the strap's width);
   - `transform` **ROTATION 90° about the X axis** (axis = a real edge: the
     helper ridge's bottom edge at y=0,z=0; `oppositeDirection: true` to get
     (y,z)→(−z,y));
   - `transform` **TRANSLATION_3D dy=+3.5 mm** to center the 7 mm width on y=0.
5. **Helper ridge** (kept, functional): 40×0.3×4.3 pad providing the X-axis
   edge used as the rotation axis (datum planes' short IDs can't be obtained
   via REST — cPlane features don't expose their plane ID and the Front/Right
   origin planes aren't discoverable; `MID_PLANE` of two lines is unsupported
   in the kernel, `LINE_ANGLE` cPlanes work but can't be referenced from a
   sketch's `sketchPlane` parameter).

### Lessons that differ from the Phase-0 notes

- **Units**: the studio default is **meters** — all sketch coordinates are
  mm×0.001; depth expressions carry units ("7 mm"). Massproperties volume is
  reported in m³; per-body volumes are best computed from
  `tessellatedfaces` (divergence theorem) because `massproperties` only
  exposes the `-all-` aggregate (sum of body volumes, not union).
- **Transform feature** (`transformType: ROTATION` needs `transformAxis` =
  edge/vertex query + `angle`; `TRANSLATION_3D` needs dx/dy/dz quantities) is
  the workhorse for building on planes you can't sketch on — rotate an
  extruded slab into the desired orientation instead of sketching on a datum
  plane.
- **Delete cascades**: deleting a sketch deletes its dependent features
  (used to fix a mis-rotated strap: delete sketch → rebuild chain with the
  corrected flag). `features/updates` requires a `featureId` (creation
  responses don't return one; the feature tree does, but `GET /features`
  rate-limits hard — ~7–10 h per 3000 calls).
- **Free plan**: `POST .../export` (STL/STEP) returns 202 then
  "Export failed" for **any** studio — server-side export is not available on
  the account; STL was reconstructed from `tessellatedfaces` instead
  (`os_export_stl.py` documents the attempt; union via trimesh+manifold3d).

### Verification (OnShape vs FreeCAD reference `hook_hand.py`)

| metric | OnShape | FreeCAD |
|---|---|---|
| bbox | 46 × 46 × 50.25 mm | 46 × 46 × 50.75 mm (strap z0 23.5) |
| strap bbox | x[−1.75,12.75] y[−3.5,3.5] z[23,50.25] | same (±0.5 z offset) |
| union volume | **20,191 mm³** (watertight manifold union) | **20,219 mm³** |

−28 mm³ (0.14%) = 8-seg arc approximations + missing root/corner fillets —
within print tolerance. STL: `out/ons/hook_onshape.stl` (vs
`out/hook_hand/hook.stl`). View live: OnShape UI, doc `HookFinal`.

### Leftovers (user can trash in UI; my API key has no document scope)

- Part studios in the same doc: `bde64379...` (phase-0 probe), `cbec2362...`
  (first hook attempt), `adae9690...` ("HookFinal2" probe).
- Feature `FhN0NlGhysDlraB_2` (step pad) and the 40 mm helper ridge are
  intentionally kept (the ridge edge is referenced by the strap's rotation).

