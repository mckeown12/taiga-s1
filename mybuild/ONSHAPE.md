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

## Unknowns for the Phase-0 smoke test

1. Rate limits (exact numbers) — determines datagen parallelism.
2. Document default unit + how to pin it; sketch/feature units end-to-end.
3. PAT creation UI + scopes for a personal agent.
4. SWEEP feature param shape (profile sketch + path sketch ids).
5. Whether the free plan includes API access.

## Phases

| phase | work | effort |
|---|---|---|
| 0 | account + PAT; create doc -> sketch -> extrude -> hole -> fillet -> STEP; measure latency/rate/units | half day |
| 1 | translator both directions; hook as test part | 1-2 weeks |
| 2 | taiga-os1: runtime port, datagen, SFT+DAgger, eval to parity (hook + original suites) | 2-4 weeks |

Requires from you: an OnShape account (any plan that allows API use) and a
personal access token.
