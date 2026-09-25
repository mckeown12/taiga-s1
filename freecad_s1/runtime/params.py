"""Parameter stage (stand-in).

The System-1 model predicts *which* command to run; numeric arguments
(sketch sizes, pad lengths, fillet radii, pattern counts) are a separate
prediction stage. Until that stage exists, this resolver fills them in from
the goal intent the command is being applied to. When the command does not
match the intent (the policy made a mistake) it still returns plausible
values derived from the intent, so the mistake produces real, wrong geometry
the policy then has to notice and undo.

Pure stdlib: no FreeCAD import.
"""

from __future__ import annotations

from ..schema import Goal, GoalFeature


def intent(goal: Goal, index: int) -> GoalFeature:
    if not goal.features:
        return GoalFeature("<unk>", {})
    return goal.features[max(0, min(index, len(goal.features) - 1))]


def profile_box(f: GoalFeature, scale: float) -> tuple[float, float, float, float]:
    """(center_x, center_y, size_x, size_y) of the sketch profile for intent
    `f`. Coordinates are global XY for XY-plane/top-face sketches and
    sketch-local (radial, height) for the ring's XZ-plane sketch."""
    p = f.params
    if f.kind == "base_box":
        return 0.0, 0.0, p["w"], p["d"]
    if f.kind in ("base_cyl", "base_hex"):
        return 0.0, 0.0, 2 * p["r"], 2 * p["r"]
    if f.kind == "base_ring":
        return (p["ri"] + p["ro"]) / 2, p["h"] / 2, p["ro"] - p["ri"], p["h"]
    if f.kind in ("boss_cyl", "hole", "hole_std"):
        return p["x"], p["y"], 2 * p["r"], 2 * p["r"]
    if f.kind in ("boss_box", "pocket_rect"):
        return p["x"], p["y"], p["w"], p["d"]
    return 0.0, 0.0, scale / 4, scale / 4


def pad_length(f: GoalFeature, scale: float) -> float:
    return f.params.get("h") or max(1.0, round(scale * 0.2, 1))


def pocket_spec(f: GoalFeature, scale: float) -> tuple[str, float]:
    """(Type, Length) for a Pocket."""
    if f.kind == "pocket_rect":
        return "Length", f.params["depth"]
    if f.kind in ("hole", "hole_std"):
        return "ThroughAll", 0.0
    return "Length", max(1.0, round(scale * 0.1, 1))


def hole_diameter(f: GoalFeature, scale: float) -> float:
    if "r" in f.params and f.kind in ("hole", "hole_std", "boss_cyl"):
        return 2 * f.params["r"]
    return max(1.0, round(scale * 0.1, 1))


def dressup_value(f: GoalFeature, command: str) -> float:
    if command == "PartDesign_Fillet" and f.kind.startswith("fillet"):
        return f.params["r"]
    if command == "PartDesign_Chamfer" and f.kind == "chamfer_top":
        return f.params["size"]
    if command == "PartDesign_Thickness" and f.kind == "shell":
        return f.params["t"]
    if command == "PartDesign_Draft":
        return 3.0  # degrees
    return 1.0


def pattern_spec(f: GoalFeature, command: str, scale: float) -> dict[str, float]:
    n = int(f.params.get("n", 3 if command == "PartDesign_PolarPattern" else 2))
    return {"n": max(2, n), "length": f.params.get("length", round(scale * 0.4, 1))}
