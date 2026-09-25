"""Action catalogue and valid-action enumeration.

An action id is either a real FreeCAD command name (``PartDesign_Pad``), a
command with an argument (``Std_Workbench:PartDesignWorkbench``), a selection
pseudo-command (``Select:Face+Z``) standing in for Gui.Selection clicks, or
the terminal ``Done``. The model only ever predicts command *type*; numeric
parameters come from a separate stage (see `runtime.params`).

`enumerate_actions` mirrors what `Gui.isCommandActive` + the visible toolbars
offer at a given moment, computed from the structured `State` so the same
rules apply headless and in the GUI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import State


@dataclass(frozen=True)
class ActionSpec:
    id: str
    category: str
    scope: str  # "any" | "nodoc" | "doc" | "PartDesign" | "Part" | "sketch"
    doc_modifying: bool


def _spec(id_: str, category: str, scope: str, modifies: bool = True) -> ActionSpec:
    return ActionSpec(id_, category, scope, modifies)


SELECT_PLANES = ["Plane:XY", "Plane:XZ", "Plane:YZ"]
SELECT_FACES = ["Face+Z", "Face-Z", "Face+X", "Face-X", "Face+Y", "Face-Y"]
SELECT_OTHER = ["Edges@Face+Z", "Edges|Z", "Tip", "Clear"]
WORKBENCH_TARGETS = ["PartDesignWorkbench", "PartWorkbench", "SketcherWorkbench"]

CATALOGUE: dict[str, ActionSpec] = {
    s.id: s
    for s in [
        _spec("Std_New", "std", "nodoc"),
        *[_spec(f"Std_Workbench:{w}", "workbench", "any", False) for w in WORKBENCH_TARGETS],
        _spec("Std_Undo", "std", "doc"),
        _spec("Std_ViewFitAll", "view", "doc", False),
        _spec("Done", "terminal", "doc", False),
        *[_spec(f"Select:{a}", "select", "doc", False) for a in SELECT_PLANES + SELECT_FACES + SELECT_OTHER],
        _spec("PartDesign_Body", "body", "PartDesign"),
        _spec("PartDesign_NewSketch", "sketch", "PartDesign"),
        _spec("PartDesign_Pad", "additive", "PartDesign"),
        _spec("PartDesign_Revolution", "additive", "PartDesign"),
        _spec("PartDesign_Pocket", "subtractive", "PartDesign"),
        _spec("PartDesign_Groove", "subtractive", "PartDesign"),
        _spec("PartDesign_Hole", "subtractive", "PartDesign"),
        _spec("PartDesign_Fillet", "dressup", "PartDesign"),
        _spec("PartDesign_Chamfer", "dressup", "PartDesign"),
        _spec("PartDesign_Draft", "dressup", "PartDesign"),
        _spec("PartDesign_Thickness", "dressup", "PartDesign"),
        _spec("PartDesign_Mirrored", "pattern", "PartDesign"),
        _spec("PartDesign_LinearPattern", "pattern", "PartDesign"),
        _spec("PartDesign_PolarPattern", "pattern", "PartDesign"),
        _spec("Part_Box", "part_primitive", "Part"),
        _spec("Part_Cylinder", "part_primitive", "Part"),
        _spec("Sketcher_CreateRectangle", "sketch_geometry", "sketch"),
        _spec("Sketcher_CreateCircle", "sketch_geometry", "sketch"),
        _spec("Sketcher_CreateHexagon", "sketch_geometry", "sketch"),
        _spec("Sketcher_CreateLine", "sketch_geometry", "sketch"),
        _spec("Sketcher_CreatePoint", "sketch_geometry", "sketch"),
        _spec("Sketcher_ConstrainDistanceX", "sketch_constraint", "sketch"),
        _spec("Sketcher_ConstrainDistanceY", "sketch_constraint", "sketch"),
        _spec("Sketcher_ConstrainDiameter", "sketch_constraint", "sketch"),
        _spec("Sketcher_ConstrainRadius", "sketch_constraint", "sketch"),
        _spec("Sketcher_ConstrainLock", "sketch_constraint", "sketch"),
        _spec("Sketcher_ConstrainHorizontal", "sketch_constraint", "sketch"),
        _spec("Sketcher_ConstrainVertical", "sketch_constraint", "sketch"),
        _spec("Sketcher_ToggleConstruction", "sketch_misc", "sketch"),
        _spec("Sketcher_LeaveSketch", "sketch_misc", "sketch"),
    ]
}

ACTION_IDS = ["<unk>", *CATALOGUE]
CATEGORIES = ["<unk>", *sorted({s.category for s in CATALOGUE.values()})]
SCOPES = ["<unk>", *sorted({s.scope for s in CATALOGUE.values()})]

PROFILE_FEATURES = {"PartDesign_Pad", "PartDesign_Revolution", "PartDesign_Pocket", "PartDesign_Groove", "PartDesign_Hole"}
SUBTRACTIVE = {"PartDesign_Pocket", "PartDesign_Groove", "PartDesign_Hole"}
SOLID_FEATURE_TYPES = {
    "PartDesign::Pad", "PartDesign::Pocket", "PartDesign::Revolution", "PartDesign::Groove",
    "PartDesign::Hole", "PartDesign::Fillet", "PartDesign::Chamfer", "PartDesign::Draft",
    "PartDesign::Thickness", "PartDesign::Mirrored", "PartDesign::LinearPattern", "PartDesign::PolarPattern",
}

_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[+\-|@]?[A-Z0-9]+|[+\-|@]")


def action_words(action_id: str) -> list[str]:
    """Split an action id into lowercase word pieces, e.g.
    ``Select:Edges@Face+Z`` -> ``["select", "edges", "@", "face", "+", "z"]``.
    Lets the model generalize to command names outside the catalogue."""
    words: list[str] = []
    for part in re.split(r"[_:]", action_id):
        words.extend(w.lower() for w in _CAMEL.findall(part))
    return words


WORD_VOCAB = ["<pad>", "<unk>", *sorted({w for a in CATALOGUE for w in action_words(a)})]

_AXES = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "Z": (0.0, 0.0, 1.0)}


def action_vector(action_id: str) -> list[float]:
    """Small numeric descriptor for arguments: direction of a selected face
    or plane normal (sign included) and 3 flags (plane/face/edges)."""
    vec = [0.0] * 6
    if not action_id.startswith("Select:"):
        return vec
    arg = action_id.split(":", 1)[1]
    m = re.search(r"Face([+-])([XYZ])", arg)
    if m:
        sign = 1.0 if m.group(1) == "+" else -1.0
        vec[:3] = [sign * c for c in _AXES[m.group(2)]]
    elif arg.startswith("Plane:"):
        normal = {"XY": "Z", "XZ": "Y", "YZ": "X"}[arg.split(":")[1]]
        vec[:3] = list(_AXES[normal])
    elif arg == "Edges|Z":
        vec[:3] = list(_AXES["Z"])
    vec[3] = float(arg.startswith("Plane:"))
    vec[4] = float(arg.startswith("Face"))
    vec[5] = float(arg.startswith("Edges"))
    return vec


def enumerate_actions(state: State) -> list[str]:
    """Valid action ids for `state`, in catalogue order."""
    out: list[str] = []
    wb = state.workbench
    for w in WORKBENCH_TARGETS:
        if w != wb and not state.edit:
            out.append(f"Std_Workbench:{w}")
    if not state.doc_open:
        return ["Std_New", *out]

    if state.undo_available:
        out.append("Std_Undo")
    out.append("Std_ViewFitAll")

    if state.edit:
        sketch = next((n for n in state.tree if n.name == state.edit), None)
        has_geo = bool(sketch and sketch.num.get("n_geo", 0) > 0)
        for a in ("Sketcher_CreateRectangle", "Sketcher_CreateCircle", "Sketcher_CreateHexagon",
                  "Sketcher_CreateLine", "Sketcher_CreatePoint"):
            out.append(a)
        if has_geo:
            out += [a for a, s in CATALOGUE.items() if s.category == "sketch_constraint"]
            out.append("Sketcher_ToggleConstruction")
        out.append("Sketcher_LeaveSketch")
        return out

    out.append("Done")
    sel_kinds = {s.kind for s in state.selection}
    has_solid = state.shape.valid and state.shape.volume > 1e-9
    if state.has_body:
        out += [f"Select:{p}" for p in SELECT_PLANES]
    out += [f"Select:{f}" for f in SELECT_FACES if f[-2:] in state.shape.face_dirs]
    if "+Z" in state.shape.face_dirs:
        out.append("Select:Edges@Face+Z")
    if "|Z" in state.shape.face_dirs:
        out.append("Select:Edges|Z")
    if any(n.type in SOLID_FEATURE_TYPES for n in state.tree):
        out.append("Select:Tip")
    if state.selection:
        out.append("Select:Clear")

    if wb == "PartDesignWorkbench":
        out.append("PartDesign_Body")
        if state.has_body:
            if len(state.selection) == 1 and sel_kinds & {"plane", "face"}:
                out.append("PartDesign_NewSketch")
            open_profile = any(
                n.type == "Sketcher::SketchObject" and not n.num.get("consumed") and n.num.get("n_geo", 0) > 0
                for n in state.tree
            )
            if open_profile:
                out += ["PartDesign_Pad", "PartDesign_Revolution"]
                if has_solid:
                    out += ["PartDesign_Pocket", "PartDesign_Groove", "PartDesign_Hole"]
            if has_solid and "edges" in sel_kinds:
                out += ["PartDesign_Fillet", "PartDesign_Chamfer"]
            if has_solid and "face" in sel_kinds:
                out += ["PartDesign_Thickness", "PartDesign_Draft"]
            if "feature" in sel_kinds:
                out += ["PartDesign_Mirrored", "PartDesign_LinearPattern", "PartDesign_PolarPattern"]
    elif wb == "PartWorkbench":
        out += ["Part_Box", "Part_Cylinder"]
    order = {a: i for i, a in enumerate(CATALOGUE)}
    return sorted(dict.fromkeys(out), key=lambda a: order.get(a, 10**6))
