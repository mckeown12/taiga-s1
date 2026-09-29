"""State-based scripted expert.

The expert reads the session's privileged bookkeeping (`Meta`: which goal
intent each object was built for, whether it was built by an on-plan action)
and returns the *set* of acceptable next actions. Because it is a function of
state rather than a replay of a fixed script, it can label any state the
learner reaches — after noise injection or during DAgger — and it naturally
yields multiple correct answers where order does not matter (e.g. the
constraints of a sketch).

The model never sees `Meta`; it sees the `State` extracted from FreeCAD.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .goals import RECIPES
from .schema import Goal

PD = "PartDesignWorkbench"


@dataclass
class ObjMeta:
    name: str
    role: str  # "body" | "sketch" | "feature" | "other"
    goal_ref: int = -1
    command: str = ""
    geometry: list[str] = field(default_factory=list)  # create commands applied (sketches)
    constraints: list[str] = field(default_factory=list)  # constraint commands applied (sketches)
    groups: list[dict] = field(default_factory=list)  # executor bookkeeping (sketches)
    consumed_by: str | None = None
    valid: bool = True


@dataclass
class Meta:
    doc_open: bool = False
    workbench: str = "StartWorkbench"
    edit: str | None = None
    selection: list[str] = field(default_factory=list)  # Select args, e.g. ["Face+Z"]
    body: str | None = None
    objects: dict[str, ObjMeta] = field(default_factory=dict)
    dirty: int = 0  # doc changes made by off-plan actions that are still in the document


def progress(goal: Goal, meta: Meta) -> int:
    """Index of the first goal intent that has no finished feature."""
    done = {o.goal_ref for o in meta.objects.values() if o.role == "feature"}
    i = 0
    while i < len(goal.features) and i in done:
        i += 1
    return i


def current_sketch(meta: Meta, i: int) -> ObjMeta | None:
    for o in meta.objects.values():
        if o.role == "sketch" and o.goal_ref == i and o.consumed_by is None:
            return o
    return None


def expert_actions(goal: Goal, meta: Meta) -> list[str]:
    """Acceptable next actions (any of them is correct), canonical first."""
    if not meta.doc_open:
        return ["Std_New"] + ([f"Std_Workbench:{PD}"] if meta.workbench != PD else [])
    if meta.dirty > 0 or any(not o.valid for o in meta.objects.values()):
        return ["Std_Undo"]
    if meta.edit is None and meta.workbench != PD:
        return [f"Std_Workbench:{PD}"]
    if meta.body is None:
        return ["PartDesign_Body"]

    i = progress(goal, meta)
    if i >= len(goal.features):
        return ["Sketcher_LeaveSketch"] if meta.edit else ["Done"]
    recipe = RECIPES[goal.features[i].kind]

    if recipe.sketched:
        sk = current_sketch(meta, i)
        if sk is None:
            if meta.selection == [recipe.support]:
                return ["PartDesign_NewSketch"]
            return [f"Select:{recipe.support}"]
        if meta.edit == sk.name:
            if not sk.geometry:
                return [recipe.geometry]
            missing = [c for c in recipe.constraints if c not in sk.constraints]
            return missing or ["Sketcher_LeaveSketch"]
        return [recipe.feature]

    if recipe.select is None:  # atomic feature (e.g. hook sweep): no selection
        return [recipe.feature]
    if meta.selection == [recipe.select]:
        return [recipe.feature]
    return [f"Select:{recipe.select}"]


def expert_plan_length(goal: Goal, start_doc_open: bool, start_wb: str, start_body: bool) -> int:
    """Number of expert steps for a clean episode (used for step budgets)."""
    n = 1  # Done
    n += 0 if start_doc_open else 1
    n += 0 if start_wb == PD else 1
    n += 0 if start_body else 1
    for f in goal.features:
        r = RECIPES[f.kind]
        if r.sketched:
            n += 1 + 1 + 1 + len(r.constraints) + 1 + 1
        elif r.select is None:
            n += 1  # atomic feature: one command, no selection
        else:
            n += 2
    return n
