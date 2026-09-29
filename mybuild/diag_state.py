"""Dump the raw state the model sees after the first base pad, for two goals."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import os
os.environ.setdefault("FREECAD_PYTHON", "/home/bruce/freecad/squashfs-root/usr/bin/python")
os.environ.setdefault("FREECAD_LIB", "/home/bruce/freecad/squashfs-root/usr/lib")

from freecad_s1.runtime.client import FreeCADEnv
from freecad_s1.schema import Goal, State

GOALS = {
    "v1_base": {"features": [
        {"kind": "base_box", "params": {"w": 48.0, "d": 58.0, "h": 5.0}},
        {"kind": "hole", "params": {"r": 2.15, "x": -14.0, "y": 22.0}},
        {"kind": "hole", "params": {"r": 2.15, "x": 14.0, "y": 22.0}},
        {"kind": "boss_box", "params": {"w": 35.0, "d": 40.0, "x": 0.0, "y": -5.0, "h": 25.0}},
        {"kind": "pocket_rect", "params": {"w": 22.0, "d": 28.0, "x": 0.0, "y": -5.0, "depth": 21.0}},
        {"kind": "fillet_top", "params": {"r": 1.0}}], "level": 4, "scale": 58.0},
    "v2_base": {"features": [
        {"kind": "base_box", "params": {"w": 46.0, "d": 48.0, "h": 5.0}},
        {"kind": "hole", "params": {"r": 2.15, "x": -17.5, "y": 17.5}},
        {"kind": "hole", "params": {"r": 2.15, "x": 17.5, "y": 17.5}},
        {"kind": "hole", "params": {"r": 2.15, "x": -17.5, "y": -17.5}},
        {"kind": "hole", "params": {"r": 2.15, "x": 17.5, "y": -17.5}},
        {"kind": "boss_cyl", "params": {"r": 21.0, "x": 0.0, "y": 0.0, "h": 30.0}},
        {"kind": "pocket_rect", "params": {"w": 18.0, "d": 18.0, "x": 0.0, "y": 0.0, "depth": 26.0}},
        {"kind": "fillet_top", "params": {"r": 1.0}}], "level": 4, "scale": 48.0},
}
STEPS = ["PartDesign_Body", "Select:Plane:XY", "PartDesign_NewSketch", "Sketcher_CreateRectangle",
         "Sketcher_ConstrainLock", "Sketcher_ConstrainDistanceY", "Sketcher_ConstrainDistanceX",
         "Sketcher_LeaveSketch", "PartDesign_Pad"]


def run(env: FreeCADEnv, name: str) -> None:
    r = env.call({"op": "reset", "goal": GOALS[name], "start": {"doc_open": True, "workbench": "PartDesignWorkbench"}})
    goal = Goal.from_json(r["goal"])
    for act in STEPS:
        s = env.call({"op": "step", "action": act})
        if s["info"].get("error"):
            print(f"[{name}] {act} ERROR: {s['info']['error']}")
            return
    st = State.from_json(s["state"])
    print(f"===== {name} : state after base pad =====")
    print("shape:", json.dumps(st.shape.__dict__))
    for n in st.tree:
        num = {k: round(v, 3) for k, v in n.num.items() if v}
        print(f"node {n.name} ({n.type}) num={num} geo={n.geo} cons={n.cons}")
    print("valid actions:", s["actions"][:8], "... total", len(s["actions"]))
    print("expert:", s["expert"])


def main() -> None:
    env = FreeCADEnv()
    try:
        for name in sys.argv[1:]:
            run(env, name)
    finally:
        env.close()


if __name__ == "__main__":
    main()
