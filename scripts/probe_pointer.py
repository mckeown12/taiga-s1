"""Replay expert trajectories and measure, per step, (a) the modular pointer's
accuracy against the expert progress index and (b) action accuracy, split by
intent index. Isolates pointer errors from policy errors."""
import argparse, collections, torch
from freecad_s1.model.featurize import collate, make_example
from freecad_s1.model.net import load_checkpoint
from freecad_s1.runtime.client import VecEnv
from freecad_s1.schema import State

ap = argparse.ArgumentParser(); ap.add_argument("--ckpt"); ap.add_argument("--level", type=int, default=5)
ap.add_argument("--split", default="len"); ap.add_argument("--episodes", type=int, default=24)
args = ap.parse_args()
model = load_checkpoint(args.ckpt, "cpu"); opts = model.cfg.feature_opts()
vec = VecEnv(8)
ptr_ok = collections.defaultdict(list); act_ok = collections.defaultdict(list)
for s in range(0, args.episodes, 8):
    eps = vec.reset([{"level": args.level, "split": args.split, "seed": 4_000_000 + s + i} for i in range(8)])
    active = list(range(8))
    while active:
        exs = [make_example(eps[i].state, eps[i].goal, eps[i].actions, eps[i].expert, eps[i].progress, **opts) for i in active]
        b = collate(exs)
        with torch.no_grad():
            logits, _, ptr = model(b, return_aux=True)
        for k, i in enumerate(active):
            e = eps[i]
            if ptr is not None and b["progress"][k] >= 0:
                if model.cfg.pointer == "done":  # first not-done goal slot, as in the model
                    goal = (b["seg"][k] == 6) & b["token_mask"][k]
                    nd = ((ptr[k] < 0) & goal).nonzero().flatten()
                    pick = int(nd[0]) if len(nd) else int(goal.nonzero().flatten()[-1])
                else:
                    pick = int(ptr[k].argmax())
                ptr_ok[e.progress].append(pick == int(b["progress"][k]))
            act_ok[e.progress].append(e.actions[int(logits[k].argmax())] in e.expert)
        rs = vec.step(active, [eps[i].expert[0] for i in active]); nxt = []
        for i, r in zip(active, rs):
            e = eps[i]; e.state, e.actions, e.expert, e.progress = State.from_json(r["state"]), r["actions"], r["expert"], r["progress"]
            if not r["info"]["done"] and e.expert: nxt.append(i)
        active = nxt
vec.close()
for k in sorted(act_ok):
    p = f"pointer {sum(ptr_ok[k])/len(ptr_ok[k]):.3f}" if ptr_ok[k] else ""
    print(f"intent {k}: action {sum(act_ok[k])/len(act_ok[k]):.3f} (n={len(act_ok[k])}) {p}")
