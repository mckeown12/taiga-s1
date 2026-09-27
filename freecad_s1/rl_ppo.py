"""Phase 3: PPO against live FreeCAD, initialized from the SFT/DAgger policy.

Reward (per step), with IoU against the target solid computed by OCC booleans:
    + 10 * (IoU_t - IoU_{t-1})     potential-based shaping toward the target geometry
    - 0.02                         step cost
    + 5 on Done if IoU >= 0.99, -1 on Done otherwise, -1 on budget/unrecoverable
The shaping term telescopes, so it cannot be farmed by build/undo loops.

An optional behavior-cloning term on the expert labels (which the workers
return for free) keeps the policy anchored while RL explores.

    python -m freecad_s1.rl_ppo --init runs/sft/last.pt --out runs/ppo --iters 50
"""

from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from .evaluate import multilabel_nll, online_metrics
from .model.featurize import collate, make_example
from .model.net import load_checkpoint, save_checkpoint, select_device
from .runtime.client import VecEnv
from .schema import Goal, State

RL_SEED_BASE = 20_000_000  # disjoint from datagen/DAgger (<1e6), test (1e6+), probes, calibration (7e6+)


@dataclass
class Transition:
    example: object
    action: int
    logp: float
    value: float
    reward: float = 0.0
    done: bool = False


def ppo(args) -> None:
    device = select_device(args.device)
    model = load_checkpoint(args.init, device)
    model.train()
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.0)
    vec = VecEnv(args.workers)
    rng = random.Random(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    seed_counter = [0]

    def spec() -> dict:
        seed_counter[0] += 1
        return {"level": rng.choice(args.levels), "seed": RL_SEED_BASE + args.seed * 100_000 + seed_counter[0]}

    def reset(i: int):
        r = vec.envs[i].call({"op": "reset", **spec()})
        return {"goal": Goal.from_json(r["goal"]), "state": State.from_json(r["state"]), "actions": r["actions"],
                "expert": r["expert"], "budget": r["budget"], "steps": 0}

    envs = [reset(i) for i in range(len(vec))]
    history = []
    try:
        for it in range(args.iters):
            t0 = time.time()
            trajs: list[list[Transition]] = [[] for _ in envs]
            ep_returns, ep_success = [], []
            ret_acc = [0.0] * len(envs)
            for _ in range(args.horizon):
                examples = [make_example(e["state"], e["goal"], e["actions"], e["expert"], **model.cfg.feature_opts()) for e in envs]
                batch = {k: v.to(device) for k, v in collate(examples).items()}
                with torch.no_grad():
                    model.eval()
                    logits, values = model(batch)
                dist = torch.distributions.Categorical(logits=logits)
                acts = dist.sample()
                logps = dist.log_prob(acts)
                for i, e in enumerate(envs):
                    vec.envs[i].send({"op": "step", "action": e["actions"][int(acts[i])], "reward": True})
                for i, e in enumerate(envs):
                    r = vec.envs[i].recv()
                    e["steps"] += 1
                    reward = 10.0 * r["delta_iou"] - 0.02
                    done = False
                    if r["info"]["done"]:
                        success = r["iou"] >= 0.99
                        reward += 5.0 if success else -1.0
                        done = True
                    elif not r["expert"] or e["steps"] >= e["budget"]:
                        reward -= 1.0
                        done, success = True, False
                    trajs[i].append(Transition(examples[i], int(acts[i]), float(logps[i]), float(values[i]), reward, done))
                    ret_acc[i] += reward
                    if done:
                        ep_returns.append(ret_acc[i])
                        ep_success.append(success)
                        ret_acc[i] = 0.0
                        envs[i] = reset(i)
                    else:
                        e["state"], e["actions"], e["expert"] = State.from_json(r["state"]), r["actions"], r["expert"]
            # Bootstrap values for unfinished trajectories.
            with torch.no_grad():
                examples = [make_example(e["state"], e["goal"], e["actions"], e["expert"], **model.cfg.feature_opts()) for e in envs]
                _, last_values = model({k: v.to(device) for k, v in collate(examples).items()})
            flat, advs, rets = [], [], []
            for i, traj in enumerate(trajs):
                gae, nxt = 0.0, float(last_values[i])
                a_list, r_list = [], []
                for t in reversed(traj):
                    nonterminal = 0.0 if t.done else 1.0
                    delta = t.reward + args.gamma * nxt * nonterminal - t.value
                    gae = delta + args.gamma * args.lam * nonterminal * gae
                    a_list.append(gae)
                    r_list.append(gae + t.value)
                    nxt = t.value
                flat += traj
                advs += a_list[::-1]
                rets += r_list[::-1]
            adv = torch.tensor(advs)
            adv = (adv - adv.mean()) / (adv.std() + 1e-8)
            ret = torch.tensor(rets)
            model.train()
            stats = {"pg": 0.0, "v": 0.0, "ent": 0.0, "bc": 0.0, "n": 0}
            for _ in range(args.epochs):
                order = np.random.permutation(len(flat))
                for s in range(0, len(flat), args.minibatch):
                    idx = order[s:s + args.minibatch]
                    batch = {k: v.to(device) for k, v in collate([flat[j].example for j in idx]).items()}
                    logits, values = model(batch)
                    dist = torch.distributions.Categorical(logits=logits)
                    a = torch.tensor([flat[j].action for j in idx], device=device)
                    old = torch.tensor([flat[j].logp for j in idx], device=device)
                    ratio = torch.exp(dist.log_prob(a) - old)
                    ad = adv[idx].to(device)
                    pg = -torch.min(ratio * ad, ratio.clamp(1 - args.clip, 1 + args.clip) * ad).mean()
                    vloss = (values - ret[idx].to(device)).pow(2).mean()
                    ent = dist.entropy().mean()
                    has_label = batch["target"].any(-1)
                    bc = multilabel_nll(logits[has_label], batch["target"][has_label]).mean() if has_label.any() else 0.0
                    loss = pg + args.vf_coef * vloss - args.ent_coef * ent + args.bc_coef * bc
                    opt.zero_grad(set_to_none=True)
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 0.5)
                    opt.step()
                    stats["pg"] += pg.item()
                    stats["v"] += vloss.item()
                    stats["ent"] += ent.item()
                    stats["bc"] += float(bc.detach()) if torch.is_tensor(bc) else bc
                    stats["n"] += 1
            n = max(stats.pop("n"), 1)
            row = {"iter": it, "episodes": len(ep_returns),
                   "mean_return": round(float(np.mean(ep_returns)), 3) if ep_returns else None,
                   "success": round(float(np.mean(ep_success)), 3) if ep_success else None,
                   **{k: round(v / n, 4) for k, v in stats.items()}, "sec": round(time.time() - t0, 1)}
            history.append(row)
            print(json.dumps(row), flush=True)
            if (it + 1) % args.save_every == 0 or it == args.iters - 1:
                save_checkpoint(out / "last.pt", model, {"phase": "ppo", "iter": it})
    finally:
        vec.close()
    (out / "ppo_history.json").write_text(json.dumps(history, indent=2))
    if args.eval_episodes:
        report = online_metrics(model.eval(), device, episodes=args.eval_episodes, workers=args.workers)
        print(json.dumps({"episodes": report}, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--init", required=True, help="SFT/DAgger checkpoint")
    ap.add_argument("--out", default="runs/ppo")
    ap.add_argument("--iters", type=int, default=50)
    ap.add_argument("--horizon", type=int, default=64, help="steps per worker per iteration")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--levels", type=int, nargs="+", default=[2, 3])
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--gamma", type=float, default=0.99)
    ap.add_argument("--lam", type=float, default=0.95)
    ap.add_argument("--clip", type=float, default=0.2)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--minibatch", type=int, default=256)
    ap.add_argument("--vf-coef", type=float, default=0.5)
    ap.add_argument("--ent-coef", type=float, default=0.003)
    ap.add_argument("--bc-coef", type=float, default=0.1)
    ap.add_argument("--save-every", type=int, default=10)
    ap.add_argument("--eval-episodes", type=int, default=0)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--seed", type=int, default=0)
    ppo(ap.parse_args())


if __name__ == "__main__":
    main()
