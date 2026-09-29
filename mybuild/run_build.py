"""Drive Taiga-S1 to build a part in headless FreeCAD and save the result.

Usage:
  .venv/bin/python mybuild/run_build.py --model shhivv/taiga-s1 --out mybuild/out/holder
  (adds --params mybuild/holder_params.json to tweak dimensions)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

FREECAD = Path("/home/bruce/freecad/squashfs-root")
import os
os.environ.setdefault("FREECAD_PYTHON", str(FREECAD / "usr/bin/python"))
os.environ.setdefault("FREECAD_LIB", str(FREECAD / "usr/lib"))

from freecad_s1.model.net import from_pretrained
from freecad_s1.rollout import Policy
from freecad_s1.runtime.client import FreeCADEnv
from freecad_s1.schema import Goal, State


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="shhivv/taiga-s1")
    ap.add_argument("--goal-module", default="holder_goal", help="python module exposing build_goal/load_params/check_printability")
    ap.add_argument("--params", default=None, help="JSON override of holder dimensions")
    ap.add_argument("--out", default="mybuild/out/holder")
    ap.add_argument("--sample", type=int, default=0, help="sanity check: build a sampled goal at this level instead of the holder")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--topk", type=int, default=3)
    args = ap.parse_args()

    import importlib
    gm = importlib.import_module(args.goal_module)

    if args.sample:
        import random
        from freecad_s1.goals import sample_goal
        rng = random.Random(args.seed)
        g = sample_goal(args.sample, rng)
        goal = g.to_json()
        name = f"sample_L{args.sample}_{args.seed}"
    else:
        p = gm.load_params(args.params)
        goal = gm.build_goal(p)
        warns = gm.check_printability(p)
        if warns:
            print("PARAM WARNINGS:")
            for w in warns:
                print("  -", w)
        name = Path(args.out).name

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}_goal.json").write_text(json.dumps(goal, indent=2))
    print("goal:", " -> ".join(f"{f['kind']}{json.dumps(f['params'])}" for f in goal["features"]))
    print("loading model...")
    model = from_pretrained(args.model)
    policy = Policy(model, "cpu")
    print("spawning FreeCAD worker...")
    env = FreeCADEnv()
    try:
        r = env.call({"op": "reset", "goal": goal, "start": {"doc_open": True, "workbench": "PartDesignWorkbench"}})
        goal = Goal.from_json(r["goal"])
        state, actions, expert = State.from_json(r["state"]), r["actions"], r["expert"]
        print(f"start: {r['start']}  budget: {r['budget']}")
        steps = 0
        agree = 0
        t0 = time.time()
        while steps < r["budget"]:
            t = time.perf_counter()
            probs = policy.score(state, goal, actions)
            action = next(iter(probs))
            ms = (time.perf_counter() - t) * 1000
            ok = action in expert
            agree += ok
            steps += 1
            top = ", ".join(f"{a}={p:.2f}" for a, p in list(probs.items())[: args.topk])
            tag = "" if ok else f"  (expert: {expert[0]})"
            print(f"{steps:3d}  {action:32s} [{top}]{tag}  {ms:5.1f} ms  {len(actions)} valid")
            s = env.call({"op": "step", "action": action})
            if s["info"].get("error"):
                print("      error:", s["info"]["error"])
            if s["info"]["done"] or not s["expert"]:
                print(f"      episode ended: done={s['info']['done']}")
                break
            state, actions, expert = State.from_json(s["state"]), s["actions"], s["expert"]
        sc = env.call({"op": "score"})
        fcstd = out / f"{name}.FCStd"
        env.call({"op": "save", "fcstd": str(fcstd)})
        print(f"\nresult: {'SUCCESS' if sc['match'] else 'MISMATCH'}  IoU {sc['iou']:.4f}  "
              f"steps {steps}  agreement {agree}/{steps}  wall {time.time() - t0:.1f}s")
        print("saved:", fcstd)
    finally:
        env.close()


if __name__ == "__main__":
    main()
