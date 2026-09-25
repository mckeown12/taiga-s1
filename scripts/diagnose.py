"""Find the first step where the policy leaves the expert's acceptable set."""
import argparse, collections, json, torch
from freecad_s1.model.net import load_checkpoint
from freecad_s1.rollout import Policy
from freecad_s1.runtime.client import VecEnv
from freecad_s1.schema import State

ap = argparse.ArgumentParser(); ap.add_argument("--ckpt"); ap.add_argument("--level", type=int, default=4)
ap.add_argument("--episodes", type=int, default=32); ap.add_argument("--seed", type=int, default=2_000_000)
args = ap.parse_args()
pol = Policy(load_checkpoint(args.ckpt, "cpu"), torch.device("cpu")); vec = VecEnv(8)
first = collections.Counter(); where = collections.Counter()
for s in range(0, args.episodes, 8):
    eps = vec.reset([{"level": args.level, "seed": args.seed + s + i} for i in range(8)])
    diverged = [False] * 8; active = list(range(8)); done_feats = [0] * 8
    for t in range(80):
        if not active: break
        acts = pol.act([eps[i].state for i in active], [eps[i].goal for i in active], [eps[i].actions for i in active])
        for i, a in zip(active, acts):
            if not diverged[i] and a not in eps[i].expert:
                diverged[i] = True
                nfeat = sum(1 for n in eps[i].state.tree if n.type.startswith("PartDesign::") and n.type != "PartDesign::Body")
                first[(eps[i].expert[0], a)] += 1
                where[f"built {nfeat}/{len(eps[i].goal.features)} feats"] += 1
        rs = vec.step(active, acts); nxt = []
        for i, a, r in zip(active, acts, rs):
            eps[i].state, eps[i].actions, eps[i].expert = State.from_json(r["state"]), r["actions"], r["expert"]
            if not r["info"]["done"] and r["expert"]: nxt.append(i)
        active = nxt
vec.close()
print("first divergence (expert, policy):", first.most_common(8))
print("progress at divergence:", where.most_common())
