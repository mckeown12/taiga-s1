"""Full-episode experiments to isolate why the v2 goal loops.

Usage: .venv/bin/python mybuild/experiments.py [exp1|exp2|exp3]
  exp1: v2 goal but 4 holes -> 2 (6 features)          isolates goal length
  exp2: v2 goal but boss_cyl -> boss_box (8 features)  isolates cylindrical cup
  exp3: v2 goal as-is (control)
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import os
os.environ.setdefault("FREECAD_PYTHON", "/home/bruce/freecad/squashfs-root/usr/bin/python")
os.environ.setdefault("FREECAD_LIB", "/home/bruce/freecad/squashfs-root/usr/lib")

from freecad_s1.model.net import from_pretrained
from freecad_s1.rollout import Policy
from freecad_s1.runtime.client import FreeCADEnv
from freecad_s1.schema import Goal, State

BASE = {"kind": "base_box", "params": {"w": 46.0, "d": 48.0, "h": 5.0}}
H4 = [{"kind": "hole", "params": {"r": 2.15, "x": x, "y": y}}
      for x, y in ((-17.5, 17.5), (17.5, 17.5), (-17.5, -17.5), (17.5, -17.5))]
H2 = H4[:2]
CYL = {"kind": "boss_cyl", "params": {"r": 21.0, "x": 0.0, "y": 0.0, "h": 30.0}}
BOX = {"kind": "boss_box", "params": {"w": 40.0, "d": 42.0, "x": 0.0, "y": 0.0, "h": 30.0}}
POCKET = {"kind": "pocket_rect", "params": {"w": 18.0, "d": 18.0, "x": 0.0, "y": 0.0, "depth": 26.0}}
FILLET = {"kind": "fillet_top", "params": {"r": 1.0}}

BASE_T13 = {"kind": "base_box", "params": {"w": 46.0, "d": 48.0, "h": 13.0}}
EXPS = {
    "exp1": [BASE, *H2, CYL, POCKET, FILLET],
    "exp2": [BASE, *H4, BOX, POCKET, FILLET],
    "exp3": [BASE, *H4, CYL, POCKET, FILLET],
    # exp4: exp2 with a 13mm plate -> base volume ratio ~0.39 (v1's working value)
    "exp4": [BASE_T13, *H4, BOX, POCKET, FILLET],
}


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "exp3"
    feats = EXPS[which]
    goal = {"features": feats, "level": 4, "scale": 48.0}
    model = from_pretrained("shhivv/taiga-s1")
    policy = Policy(model, "cpu")
    env = FreeCADEnv()
    try:
        r = env.call({"op": "reset", "goal": goal, "start": {"doc_open": True, "workbench": "PartDesignWorkbench"}})
        goal = Goal.from_json(r["goal"])
        state, actions, expert = State.from_json(r["state"]), r["actions"], r["expert"]
        steps, agree = 0, 0
        while steps < r["budget"]:
            probs = policy.score(state, goal, actions)
            action = next(iter(probs))
            ok = action in expert
            agree += ok
            steps += 1
            if not ok and steps <= 15:
                top = ", ".join(f"{a}={p:.2f}" for a, p in list(probs.items())[:3])
                print(f"{steps:3d}  {action:30s} [{top}]  (expert: {expert[0]})")
            s = env.call({"op": "step", "action": action})
            if s["info"].get("done") or not s["expert"]:
                break
            state, actions, expert = State.from_json(s["state"]), s["actions"], s["expert"]
        sc = env.call({"op": "score"})
        print(f"{which}: {'SUCCESS' if sc['match'] else 'MISMATCH'}  IoU {sc['iou']:.4f}  steps {steps}  agreement {agree}/{steps}")
    finally:
        env.close()


if __name__ == "__main__":
    main()
