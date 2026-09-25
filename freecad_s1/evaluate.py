"""Evaluation harness.

1. Per-step (offline): top-1 accuracy of the model's argmax against the
   expert's acceptable set on held-out labeled states, broken down by
   curriculum level, label category and whether the episode was noisy.
2. Multi-step (online): the model drives live FreeCAD from a fresh goal
   until it emits Done or exhausts the step budget (2x expert length + 6).
   Success = Done issued and the final solid matches the target with
   volumetric IoU >= 0.99. Also reports clean success (no leftover junk),
   step efficiency vs the expert, on-policy agreement with the expert and a
   failure breakdown. Level 4 goals (longer feature chains) never appear in
   training data and test compositional generalization; --perturb injects
   random off-plan actions to test recovery.

    python -m freecad_s1.evaluate --ckpt runs/sft/best.pt --data data/test --episodes 200
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict

import numpy as np
import torch

from .data import Dataset, load_dataset
from .model.featurize import collate
from .model.net import S1Model, load_checkpoint, select_device

TEST_SEED_BASE = 1_000_000  # online eval seeds; training/DAgger never use this range


def multilabel_nll(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """-log sum_{a in acceptable} p(a): any acceptable action counts as correct."""
    pos = logits.masked_fill(~target, torch.finfo(logits.dtype).min)
    return torch.logsumexp(logits, -1) - torch.logsumexp(pos, -1)


@torch.no_grad()
def offline_metrics(model: S1Model, ds: Dataset, device: torch.device, batch_size: int = 512) -> dict:
    model.eval()
    correct = np.zeros(len(ds), bool)
    nll = np.zeros(len(ds), np.float32)
    for start in range(0, len(ds), batch_size):
        batch = collate(ds.examples[start:start + batch_size])
        batch = {k: v.to(device) for k, v in batch.items()}
        logits, _ = model(batch)
        pred = logits.argmax(-1)
        hit = batch["target"].gather(1, pred[:, None]).squeeze(1)
        correct[start:start + len(pred)] = hit.cpu().numpy()
        nll[start:start + len(pred)] = multilabel_nll(logits, batch["target"]).cpu().numpy()

    def group(keys) -> dict:
        acc = defaultdict(list)
        for k, c in zip(keys, correct):
            acc[k].append(c)
        return {str(k): {"acc": round(float(np.mean(v)), 4), "n": len(v)} for k, v in sorted(acc.items())}

    return {
        "acc": round(float(correct.mean()), 4),
        "nll": round(float(nll.mean()), 4),
        "n": len(ds),
        "by_level": group(ds.level),
        "by_category": group(ds.category),
        "by_noise": group(["clean" if n == 0 else ("dagger" if n < 0 else "noisy") for n in ds.noise]),
    }


def online_metrics(model: S1Model, device: torch.device, levels=(1, 2, 3), episodes: int = 100,
                   workers: int = 8, seed_base: int = TEST_SEED_BASE, sample: bool = False,
                   perturb: float = 0.0) -> dict:
    from .rollout import Policy, run_episodes
    from .runtime.client import VecEnv

    policy = Policy(model, device)
    rng = random.Random(seed_base)
    vec = VecEnv(workers)
    results = []
    try:
        for level in levels:
            for start in range(0, episodes, workers):
                n = min(workers, episodes - start)
                specs = [{"level": level, "seed": seed_base + level * 100_000 + start + i} for i in range(n)]
                if n < workers:  # keep lockstep simple: idle workers replay a spec, results dropped
                    specs += [specs[0]] * (workers - n)
                results += run_episodes(policy, vec, specs, sample=sample, rng=rng, perturb=perturb)[:n]
    finally:
        vec.close()
    return summarize(results)


def summarize(results) -> dict:
    out = {}
    by_level = defaultdict(list)
    for r in results:
        by_level[r.level].append(r)
    for level, rs in sorted(by_level.items()):
        outcomes = defaultdict(int)
        for r in rs:
            outcomes[r.outcome] += 1
        ok = [r for r in rs if r.success]
        out[f"L{level}"] = {
            "episodes": len(rs),
            "success": round(np.mean([r.success for r in rs]), 4),
            "clean_success": round(np.mean([r.clean for r in rs]), 4),
            "mean_iou": round(float(np.mean([r.iou for r in rs])), 4),
            "on_policy_agreement": round(float(np.mean([r.agreement for r in rs])), 4),
            "steps_over_expert": round(float(np.mean([r.steps / max(r.expert_steps, 1) for r in ok])), 3) if ok else None,
            "outcomes": dict(outcomes),
        }
    out["overall_success"] = round(float(np.mean([r.success for r in results])), 4) if results else 0.0
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--data", help="held-out datagen directory for per-step accuracy")
    ap.add_argument("--episodes", type=int, default=100, help="online episodes per level (0 to skip)")
    ap.add_argument("--levels", type=int, nargs="+", default=[1, 2, 3, 4],
                    help="curriculum levels; level 4 is held out (never in training data)")
    ap.add_argument("--perturb", type=float, default=0.0,
                    help="probability of replacing the policy's action by a random valid one")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--sample", action="store_true", help="sample actions instead of argmax")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--out", help="write the report JSON here")
    args = ap.parse_args()
    device = select_device(args.device)
    model = load_checkpoint(args.ckpt, device)
    report = {}
    if args.data:
        report["per_step"] = offline_metrics(model, load_dataset(args.data), device)
        print(json.dumps({"per_step": report["per_step"]}, indent=2))
    if args.episodes:
        random.seed(0)
        report["episodes"] = online_metrics(model, device, tuple(args.levels), args.episodes, args.workers,
                                            sample=args.sample, perturb=args.perturb)
        print(json.dumps({"episodes": report["episodes"]}, indent=2))
    if args.out:
        with open(args.out, "w") as fh:
            json.dump(report, fh, indent=2)


if __name__ == "__main__":
    main()
