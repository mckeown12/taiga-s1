import sys, os, json
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO)); sys.path.insert(0, str(Path(__file__).parent))
FC = Path("/home/bruce/freecad/squashfs-root")
os.environ.setdefault("FREECAD_PYTHON", str(FC / "usr/bin/python")); os.environ.setdefault("FREECAD_LIB", str(FC / "usr/lib"))
from freecad_s1.model.net import from_pretrained
from freecad_s1.rollout import Policy
from freecad_s1.runtime.client import FreeCADEnv
from freecad_s1.schema import Goal, State
from holder_goal import build_goal

def P(w=48.0, d=58.0, t=5.0, hr=2.15, hdx=14.0, hdy=22.0, cw=35.0, cd=40.0, ch=25.0, cdx=0.0, cdy=-5.0, v=22.0, u=28.0, dep=21.0, fr=1.0):
    return {"flange_w":w,"flange_d":d,"flange_t":t,"hole_r":hr,"hole_dx":hdx,"hole_dy":hdy,
            "cup_w":cw,"cup_d":cd,"cup_h":ch,"cup_dx":cdx,"cup_dy":cdy,"cav_w":v,"cav_d":u,"cav_depth":dep,"rim_fillet_r":fr}

def run(policy, name, goal):
    env = FreeCADEnv()
    try:
        r = env.call({"op":"reset","goal":goal,"start":{"doc_open":True,"workbench":"PartDesignWorkbench"}})
        goal = Goal.from_json(r["goal"]); state, actions, expert = State.from_json(r["state"]), r["actions"], r["expert"]
        dev = None; steps = 0
        while steps < r["budget"]:
            a = policy.act([state],[goal],[actions])[0]
            if a not in expert and dev is None: dev = (steps+1, a, expert[:2])
            steps += 1
            s = env.call({"op":"step","action":a})
            if s["info"]["done"] or not s["expert"]: break
            state, actions, expert = State.from_json(s["state"]), s["actions"], s["expert"]
        sc = env.call({"op":"score"})
        print(f"{name:22s} IoU={sc['iou']:.3f} match={sc['match']} steps={steps} dev={dev}")
    finally:
        env.close()

model = from_pretrained("shhivv/taiga-s1"); policy = Policy(model, "cpu")
run(policy, "1_real_props", build_goal(P()))                      # holes y=22 (slightly OOD)
run(policy, "2_holes_inrange", build_goal(P(hdy=20.0)))           # holes y=20 (in range)
run(policy, "3_cup_roundish", build_goal(P(cw=34.0, cd=42.0, v=20.0, u=28.0)))  # taller/narrower cup
