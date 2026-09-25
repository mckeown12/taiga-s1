"""Phase 2: supervised training on expert-labeled state -> action pairs,
optionally followed by DAgger rounds against live FreeCAD.

    python -m freecad_s1.train_sft --data data/train --out runs/sft --epochs 10
    python -m freecad_s1.train_sft --data data/train --out runs/sft --epochs 10 --dagger-rounds 3

Loss: multi-label NLL, -log sum_{a in acceptable} softmax(logits)_a over the
valid action set, so order-free steps (e.g. which constraint first) are not
penalized. DAgger rolls the current policy out in FreeCAD, labels every
visited state with the expert and retrains on the union — this is what moves
episode completion, since pure SFT never sees its own mistakes.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch

from .data import Dataset, load_dataset
from .evaluate import TEST_SEED_BASE, multilabel_nll, offline_metrics, summarize
from .model.featurize import collate
from .model.net import S1Config, S1Model, parameter_count, save_checkpoint, select_device


def train_epochs(model, opt, ds: Dataset, device, epochs: int, batch_size: int, lr: float, warmup: int,
                 log_every: int = 200, val: Dataset | None = None, out: Path | None = None, tag: str = "sft",
                 best: dict | None = None) -> dict:
    n = len(ds)
    steps_per_epoch = math.ceil(n / batch_size)
    total = epochs * steps_per_epoch
    best = best if best is not None else {"acc": -1.0}
    step = 0
    for epoch in range(epochs):
        model.train()
        order = np.random.permutation(n)
        t0, run_loss, run_acc = time.time(), 0.0, 0.0
        for b in range(steps_per_epoch):
            idx = order[b * batch_size:(b + 1) * batch_size]
            batch = collate([ds.examples[i] for i in idx])
            batch = {k: v.to(device, non_blocking=True) for k, v in batch.items()}
            cur_lr = lr * min(1.0, (step + 1) / warmup) * 0.5 * (1 + math.cos(math.pi * step / total))
            for g in opt.param_groups:
                g["lr"] = cur_lr
            logits, _ = model(batch)
            loss = multilabel_nll(logits, batch["target"]).mean()
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            step += 1
            run_loss += loss.item()
            run_acc += batch["target"].gather(1, logits.argmax(-1, keepdim=True)).float().mean().item()
            if step % log_every == 0:
                print(f"[{tag}] epoch {epoch} step {step}/{total} loss {run_loss / log_every:.4f} "
                      f"acc {run_acc / log_every:.4f} lr {cur_lr:.2e} ({time.time() - t0:.0f}s)", flush=True)
                run_loss = run_acc = 0.0
        if val is not None:
            m = offline_metrics(model, val, device)
            print(f"[{tag}] epoch {epoch} val acc {m['acc']:.4f} nll {m['nll']:.4f} "
                  f"levels {json.dumps({k: v['acc'] for k, v in m['by_level'].items()})}", flush=True)
            if out is not None and m["acc"] >= best["acc"]:
                best.update(acc=m["acc"], epoch=epoch, tag=tag)
                save_checkpoint(out / "best.pt", model, {"val": m, "tag": tag, "epoch": epoch})
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="runs/sft")
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight-decay", type=float, default=0.01)
    ap.add_argument("--warmup", type=int, default=500)
    ap.add_argument("--width", type=int, default=128)
    ap.add_argument("--enc-layers", type=int, default=3)
    ap.add_argument("--dec-layers", type=int, default=2)
    ap.add_argument("--ff", type=int, default=384)
    ap.add_argument("--max-examples", type=int, default=0, help="subsample training set (0 = all)")
    ap.add_argument("--dagger-rounds", type=int, default=0)
    ap.add_argument("--dagger-episodes", type=int, default=240, help="episodes per level per round")
    ap.add_argument("--dagger-epochs", type=int, default=3)
    ap.add_argument("--dagger-workers", type=int, default=8)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    rng = random.Random(args.seed)
    device = select_device(args.device)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    full = load_dataset(args.data)
    train, val = full.split()
    if args.max_examples and len(train) > args.max_examples:
        train = train.subset(sorted(rng.sample(range(len(train)), args.max_examples)))
    print(f"loaded {len(full)} examples ({len(train)} train / {len(val)} val) in {time.time() - t0:.0f}s")

    cfg = S1Config(width=args.width, enc_layers=args.enc_layers, dec_layers=args.dec_layers, ff=args.ff)
    model = S1Model(cfg).to(device)
    print(f"model params: {parameter_count(model):,} on {device}")
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    best = train_epochs(model, opt, train, device, args.epochs, args.batch, args.lr, args.warmup, val=val, out=out)
    save_checkpoint(out / "sft_last.pt", model, {"phase": "sft"})
    history = {"sft_best": dict(best), "dagger": []}

    if args.dagger_rounds:
        from .rollout import Policy, run_episodes
        from .runtime.client import VecEnv

        vec = VecEnv(args.dagger_workers)
        try:
            for r in range(args.dagger_rounds):
                collected = Dataset()
                results = []
                beta = 0.5 ** (r + 1)  # mix expert actions early, pure policy later
                policy = Policy(model, device)
                for level in (1, 2, 3):
                    for s in range(0, args.dagger_episodes, args.dagger_workers):
                        specs = [{"level": level, "seed": 10_000 * (r + 1) + level * 1000 + s + i}
                                 for i in range(args.dagger_workers)]
                        assert specs[-1]["seed"] < TEST_SEED_BASE
                        results += run_episodes(policy, vec, specs, collect=collected, beta=beta, rng=rng)
                summary = summarize(results)
                print(f"[dagger {r}] beta {beta:.2f} rollout success {json.dumps({k: v['success'] if isinstance(v, dict) else v for k, v in summary.items()})} "
                      f"+{len(collected)} labeled states", flush=True)
                train.extend(collected)
                best = train_epochs(model, opt, train, device, args.dagger_epochs, args.batch, args.lr * 0.3, 100,
                                    val=val, out=out, tag=f"dagger{r}", best=best)
                history["dagger"].append({"round": r, "beta": beta, "rollout": summary, "added": len(collected)})
                save_checkpoint(out / "last.pt", model, {"phase": f"dagger{r}"})
        finally:
            vec.close()
    else:
        save_checkpoint(out / "last.pt", model, {"phase": "sft"})
    (out / "train_history.json").write_text(json.dumps(history, indent=2, default=str))
    print(f"done in {time.time() - t0:.0f}s; best val acc {best['acc']:.4f} ({best.get('tag')})")


if __name__ == "__main__":
    main()
