# Taiga-S1 × Baby-Gate Wall Hook — overnight notes

## What the part is (corrected mid-night)
NOT a holder/cup. It's a **wall hook for a baby gate**: flat screw-mount flange,
round boss, and a **J-hook** — flat strap from the boss, rounded bend, tip curving
BACK toward the wall. U opens toward the wall so the gate latch slides up between
arm and tip. Matches the reference photo (dark plastic, 2 screws).

## Geometry (mm) — mybuild/hook_params.json
| part | value |
|---|---|
| flange | 46 × 46 × 4 (5 in the Taiga goal — see below), corners r3 |
| M4 holes | Ø4.3 at (±17, 0) — edge margin 3.85, boss clearance 1.85 |
| boss | Ø26 × 20, root fillet r2 |
| J-hook | width 7, thickness 3.5, arm 20, bend r5.5 (centerline), tip 10, rounded cap |
| overall | ~46 × 46 × 51 |

3D-print constraints met: min wall 3.5mm, holes Ø4.3, flange flat on bed,
only overhang = U-interior ceiling (~11×7mm, small tree support).
flange is 5mm in the Taiga goal (not 4): the stock model rejects base pads <
~39% of target volume; 5mm keeps margin. The retrained model inherits this.

## Deliverables (all in mybuild/out/)
| variant | how | volume | files |
|---|---|---|---|
| hook_hand | hand macro (mybuild/hook_hand.py) | 20167mm³ | hook_hand/{hook.FCStd,Hook.stl} |
| hook_taiga | stock Taiga-S1 builds base only (no sweep in vocab) | 21001mm³ | hook_taiga/hook_clean.FCStd |
| **hook_hybrid** | **Taiga base + macro strap fused (mybuild/hook_fuse.py)** | **22233mm³** | hook_hybrid/{hook.FCStd,Hook.stl} |

All STLs watertight (isSolid=True). Renders in out/renders4_* (front/iso/top).
**hook_hybrid/Hook.stl is the printable part** (orientation: flange down).

## The fork: hook_sweep (freecad_s1/)
Taiga's vocabulary had no sweep/loft/revolve, so the J-hook was inexpressible.
Added ONE atomic action `PartDesign_Sweep`:

- **Goal kind** `hook_sweep` (params: y, h, r, t, w, d, x — all reuse existing
  GOAL_PARAM_KEYS slots). A hook goal = base_box + 2×hole + boss_cyl + hook_sweep
  (level 3, 5 features).
- **Executor** (runtime/session.py `ex_sweep`): builds the strap as a
  `Part::Feature` (XZ profile: arm → outer arc → tip → rounded cap → inner arc →
  arm, extruded in Y, shifted by x) then fuses it into the Body with a
  `PartDesign::Boolean` (Type=Fuse). The boolean stays IN the feature chain, so
  undo/recompute/state-tracking all work as before.
- Model predicts only WHEN to fire the sweep; all numerics come from the goal
  (same philosophy as the rest of the runtime).
- Files touched: schema.py, actions.py, goals.py (sampler), expert.py,
  runtime/{params,session,worker}.py, model/{featurize,net}.py, datagen.py,
  train_sft.py, evaluate.py. ~150 lines total.

Verification (before training):
- clean expert builds the reference goal → **IoU 1.0000 vs the hand-built hybrid**
  (volume matches to the mm³: 22233)
- 12/12 randomly sampled hook goals build successfully
- worker RPC (reset/step/score) full rollout: 33 steps, IoU 1.0

## Training (from scratch — vocab grew, old checkpoints incompatible)
- Data (data/train/): 7000 episodes = 1000 L1 + 1500 L2 + 2000 L3 + **2500 hook**,
  207,182 records, expert_success 1.0 on all shards (8 FreeCAD workers, ~5 min)
- SFT 6 epochs on 196,259 examples → then DAgger: 2 rounds × (600 std + 300 hook)
  episodes, beta 0.5/0.25, 2 fine-tune epochs each round. Model 1.19M params, CPU.
- Checkpoints → checkpoints/taiga_hook/

## Eval (commands to re-run)
```
cd /home/bruce/taiga-s1
export FREECAD_PYTHON=/home/bruce/freecad/squashfs-root/usr/bin/python
export FREECAD_LIB=/home/bruce/freecad/squashfs-root/usr/lib
# the money test: model builds the full hook from the goal
.venv/bin/python mybuild/run_build.py --model checkpoints/taiga_hook_v3/hf \
    --goal-module hook_goal --out mybuild/out/hook_model
# all held-out suites (hook + generalization + length frontier)
.venv/bin/python -m freecad_s1.evaluate --ckpt checkpoints/taiga_hook_v3/last.pt \
    --data data/train --suites hook len len2 len3 len4 comp iid --episodes 60
# retrain from scratch (~4.3h on 32 cores): datagen then SFT + DAgger
.venv/bin/python -m freecad_s1.datagen --out data/train \
    --episodes 1000 1500 2000 --hook-episodes 2500 --workers 8
.venv/bin/python -m freecad_s1.train_sft --data data/train --epochs 10 \
    --dagger-epochs 2 --dagger-levels 1,2,3,4,5,6,7 --dagger-hook-episodes 300 \
    --dagger-comp-episodes 200 --out checkpoints/taiga_hook_v3

## Results (model v1: 6 SFT epochs + 2 DAgger rounds)
- **model builds the reference baby-gate hook: IoU 1.0000, 32/32 expert agreement, 0.6s**
  (mybuild/out/hook_model/, renders in out/renders5_hook_model/)
- Held-out suites (60 eps each, pure top-1):
  | suite | v1 | original (official) |
  |---|---|---|
  | **hook-L3** | **60/60, IoU 1.0** | n/a (can't build hooks) |
  | comp-L3 | 60/60 | 54/60 |
  | iid-L1/2/3 | 60/60 each | 60/60 |
  | len-L4 (6-7 intents) | 20/60 | 60/60 |
  | len2-L5 (8-9 intents) | 0/60 | 60/60 |
  | len3-L6 (11 intents) | 0/60 | 60/60 |
  | len4-L7 (13 intents) | 0/60 | never tested |
- Diagnosis: on long goals the model emits Done at ~step 32 (right where a 5-feature
  goal ends) with confidence 1.0, skipping the remaining small features (IoU 0.90-0.98).
  Likely under-trained horizon + the 2500 fixed-structure hook episodes (35% of data)
  reinforcing the "5 features -> done" prior.
- per-step accuracy on all 207k labeled states: 0.9995 (original: 0.9984)

## v2 retrain (running since 10:16)
10 SFT epochs + 4 DAgger rounds, each round now includes **levels 1-6** (300 eps/level,
levels 4-6 via the 'len' split — direct exposure to long horizons) + 300 hook eps.
New arg: --dagger-levels. Watch: does it fix len-L4/L5/L6 without losing hook 100%?
`tail -f train_v2.log` -> checkpoints/taiga_hook_v2/

## v2 results (10 SFT + 4 DAgger rounds with levels 1-6; 9791s)
| suite | v1 | v2 | original |
|---|---|---|---|
| hook-L3 | 1.00 | **1.00** (IoU 1.0, zero-dev) | n/a |
| iid-L1/2/3 | 1.00 | 1.00 | 1.00 |
| comp-L3 | 1.00 | **0.85** (mirrored_hole_std 0.70, 9 budget failures) | 0.90 |
| len-L4 | 0.33 | **1.00** | 1.00 |
| len2-L5 | 0.00 | **1.00** | 1.00 |
| len3-L6 | 0.00 | **1.00** | 1.00 |
| len4-L7 (frontier, never tested) | 0.00 | 0.18 | ? |
| per-step | 0.9995 | **0.9997** | 0.9984 |

DAgger convergence: L4/L5/L6 rollout success 0.44/0.07/0.02 (round 0, beta .5) ->
1.0/0.81/0.81 (round 1) -> 1.0/1.0/1.0 (rounds 2-3). v2 reference build: IoU 1.0, 32/32.
checkpoints/taiga_hook_v2/ + hf/; renders out/renders6_hook_v2/

## v3 results (FINAL: 10 SFT + 4 DAgger rounds with levels 1-7 + comp; 15448s)
| suite (60 fresh episodes each, pure top-1) | v1 | v2 | v3 | original |
|---|---|---|---|---|
| **hook-L3** | 1.00 | 1.00 | **1.00** | n/a (no sweep in vocab) |
| iid-L1/2/3 | 1.00 | 1.00 | 1.00 each | 1.00 |
| comp-L3 | 1.00 | 0.85 | **1.00** | 0.90 |
| len-L4 (6-7 intents) | 0.33 | 1.00 | 1.00 | 1.00 |
| len2-L5 (8-9) | 0.00 | 1.00 | 1.00 | 1.00 |
| len3-L6 (11) | 0.00 | 1.00 | 1.00 | 1.00 |
| **len4-L7 (13, frontier)** | 0.00 | 0.18 | **1.00** | never tested |
| per-step (207k states) | 0.9995 | 0.9997 | **0.9997** | 0.9984 |

**Overall online success: 1.0000 (420/420 episodes, all IoU 1.0, all clean,
zero deviation from expert step counts).** v3 DAgger convergence: L7 0.05 (r0,
beta .5) -> 0.78 (r1) -> 0.99 (r2) -> 0.997 (r3).

Generalization checks (v2/v3, all IoU 1.0000, 32/32 steps):
- reference baby-gate params (46/±17/r13/h20/w7/t3.5/arm20/r5.5/tip10)
- big: 60mm flange, ±22 holes, r16 boss h24, arm25/r7/t4/w8/tip12
- small: 40mm flange, ±14.5 holes, r10 boss h15, arm15/r4.5/t3/w6/tip8
  (out/hook_big, out/hook_small, out/hook_model_v3; renders out/renders7_*, renders8_*)

Final artifacts:
- model: checkpoints/taiga_hook_v3/ (+ hf/ layout, committed)
- printable: mybuild/out/hook_hybrid/Hook.stl (22.2cm3, watertight, flange down,
  small tree support on the U-interior ceiling)
- comparison images: out/hook_comparison.png (hand/hybrid/model), out/hook_sizes.png

## Gotchas learned (FreeCAD 1.1 headless)
- Always `import FreeCAD` before `import Part/Mesh` (else segfault exit 139).
- PartDesign::Boolean: set `b.Group=[operand]` (FreeCAD reparents it), `body.Tip=b`.
- Render ghosts = viewTop/viewIsometric animate ~1s; capture quaternion after a
  warm-up pump, then `setCameraOrientation(q)` before `saveImage`.
- Reopened docs: object Visibility defaults False → all-white renders.
- `QT_QPA_PLATFORM=offscreen` breaks QOpenGLWidget — use real Xvfb + LIBGL_ALWAYS_SOFTWARE.
