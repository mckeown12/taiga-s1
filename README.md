# FreeCAD-S1 — a System-1 next-action model for FreeCAD

A ~1.18M-parameter model, trained from scratch, that looks at the structured state of a FreeCAD session plus a goal and scores every action that is currently valid. It does this in a single forward pass (<1 ms on CPU). There is no LLM, no vision model and no screenshots. Everything it sees comes from FreeCAD's Python API.

```
FreeCAD (App/Gui API) ──snapshot──► State ─┐
goal (ordered feature intents + target) ───┼─► StateEncoder (typed-token transformer) ─► context (L×d)
valid actions (isCommandActive ∩ catalogue)─► ActionEncoder ─► options (N×d)
                                               options ─► [self-attn ▸ cross-attn→context ▸ FFN]×2 ─► score per action ─► softmax
```

## Layout

| Path | What |
|---|---|
| `freecad_s1/schema.py` | `State` (feature tree, selection, workbench, edit mode, recent actions, shape descriptors), `Goal`, vocabularies. Uses only the standard library. |
| `freecad_s1/actions.py` | Action catalogue: real FreeCAD command names, `Select:*` pseudo-commands for selection clicks, `Std_Workbench:*` and `Done`. `enumerate_actions(state)` returns the valid set. |
| `freecad_s1/goals.py` | Goal intents, the command recipe for each intent, and a curriculum sampler (L1 single feature → L3 multi-feature with patterns, mirrors and dressups). |
| `freecad_s1/expert.py` | Scripted expert. It works from the current state, not from a replayed script, so it can label any state, including off-policy ones. It returns the set of acceptable next actions. |
| `freecad_s1/runtime/session.py` | `HeadlessSession`: snapshot, enumeration, execution through App-level executors. There is one FreeCAD transaction per action, so `Std_Undo` maps exactly onto `doc.undo()`. Document observer hooks feed the event stream. |
| `freecad_s1/runtime/gui_session.py` | `GuiSession`: reads workbench, edit mode, selection and valid commands from `FreeCADGui` (`activeWorkbench`, `getInEdit`, `Selection.getSelectionEx`, `listCommands`/`isCommandActive`, selection observer). |
| `freecad_s1/runtime/params.py` | Stand-in for the separate parameter-prediction stage. It fills numeric arguments from the goal intent. |
| `freecad_s1/runtime/worker.py`, `client.py` | JSON-lines RPC so the torch process (which can't import FreeCAD) can drive N FreeCAD processes in lockstep. |
| `freecad_s1/datagen.py` | Phase 1: synthetic data from scripted workflows, with noise injection so mistakes and their recovery are also covered. |
| `freecad_s1/model/` | Featurization and the PyTorch model. |
| `freecad_s1/train_sft.py` | Phase 2: supervised training with a multi-label loss, plus optional DAgger rounds against live FreeCAD. |
| `freecad_s1/evaluate.py` | Per-step accuracy and multi-step episode success. |
| `freecad_s1/rl_ppo.py` | Phase 3: PPO against live FreeCAD with an IoU-shaped reward, starting from the SFT policy. |

## Quick start

```bash
uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python torch numpy pytest
.venv/bin/python -m pytest -q                       # unit tests + FreeCAD integration tests
./scripts/run_all.sh                                # data -> SFT + DAgger -> eval (~1.5 h on an M-series Mac)
.venv/bin/python -m freecad_s1.rl_ppo --init runs/sft/last.pt --out runs/ppo --iters 50
```

FreeCAD is found at `/Applications/FreeCAD.app` or on common Linux paths. Otherwise set `FREECAD_PYTHON` and `FREECAD_LIB`. The torch process never imports FreeCAD. It launches FreeCAD's own interpreter as a worker (`runtime/worker.py`), and each worker runs at ~3 ms per action headless.

## Design

**State (structured, sequential).** A snapshot turns the document into typed tokens:
- `[CLS]`
- `[GLOBAL]`: workbench, edit mode, undo availability, shape descriptors and the planar face directions present.
- one `[NODE]` per feature-tree object, in document order, with its parent depth. Sketches carry geometry and constraint counts, DOF, closed-wire flag and support plane. Features carry length, through-all, radius and occurrences.
- `[SEL]` per selected element: kind, normal, offset, count.
- the last 8 actions.
- `[GOAL_GLOBAL]`: the target solid's bbox, volume and face/edge counts.
- one `[GOAL]` per feature intent: kind, normalized parameters and relative order.

A 3-layer transformer encodes the whole sequence. Goal and state share this encoder, so the model can line up what is built against what is wanted.

**Actions.** Candidates are the currently valid commands. `enumerate_actions` is the headless equivalent of toolbar contents plus `isCommandActive`. `GuiSession` intersects it with the real `Gui.isCommandActive`. Each candidate is embedded from its catalogue id, category, scope, word pieces of the command name and an argument vector. The word pieces mean an unseen command such as `PartDesign_SubtractiveHelix` still gets a meaningful embedding, and id-dropout during training forces the model to use them.

**Head.** Two decoder layers: self-attention across the candidate set, cross-attention from candidates to the state, then an FFN. This produces one logit per candidate, followed by a softmax over the valid set. A value head on `[CLS]` serves PPO.

**Command type only.** The model picks the command. Numeric arguments come from `runtime/params.py`, a stand-in for the separate parameter stage that reads them from the goal intent. When the policy picks the wrong command, the stand-in still produces real (wrong) geometry. The policy then has to notice it and undo it.

**Expert and labels.** The expert reads privileged bookkeeping that the model never sees: which intent each object serves, and whether the action that created it was on plan. From that it returns the set of acceptable next actions. Constraints within a sketch can be applied in any order, so the loss is multi-label NLL. Any off-plan document change is labeled `Std_Undo`. A wrong selection or workbench is labeled with the direct fix.

**Data (Phase 1).** 48k episodes across three curriculum levels, with a randomized start (no document or a wrong workbench), randomized geometry and randomized goal structure. 60% of episodes inject random valid actions at rates of 10–30%, so the data contains mistakes and their repairs. Every rollout is verified: the expert rebuilds the target in every episode (100% success).

**Training (Phase 2).** SFT on ~1.1M labeled states, followed by DAgger rounds. In each round the policy drives live FreeCAD, the expert labels the states the policy actually visits, and the model retrains on the union.

**RL (Phase 3).** PPO against live FreeCAD. The reward is 10·ΔIoU (exact volumetric IoU via OCC booleans against the target), −0.02 per step, +5 for a correct Done, and −1 for a wrong Done or running out of steps. An optional behavior-cloning term on the expert labels keeps the policy anchored.

**Evaluation.**
- *Per-step*: argmax accuracy against the acceptable set on a held-out dataset generated with a different seed, broken down by level, label category and clean/noisy.
- *Episodes*: fresh goals with test-only seeds. Success means the model emits Done and the final solid has IoU ≥ 0.99 with the target, within a budget of 2× expert length + 6. The eval also reports clean success, steps relative to the expert, on-policy agreement and a failure breakdown.
- *Level 4*: held out of all training data. It is longer compositions (boss + two cut groups + dressup, 6–7 features) and tests compositional and length generalization.
- *`--perturb p`*: injects random off-plan actions at rate p during the episode to test recovery.

## Results (v2, in-distribution)

Model: 1,180,162 parameters. Forward pass ~0.9 ms on CPU (batch 1).

Training: SFT on 1.13M states (4 epochs) plus 2 DAgger rounds (+41k on-policy states). Total 38 minutes on an M-series Mac (MPS). All numbers come from `runs/sft/eval.json` and `runs/sft/eval_perturb.json`.

**Per-step accuracy** (73,894 held-out states from 3k test episodes generated with a different seed): **99.98%**.
- Worst categories: sketch constraints 99.94%, undo 99.93%. Every other category is 100%.
- States from noisy episodes (recovery situations): 99.97%.

**Episodes** (100 fresh goals per level, test-only seeds, greedy decoding):

| | L1 | L2 | L3 | L4 (held out) |
|---|---|---|---|---|
| Success (Done + IoU ≥ 0.99) | 100% | 100% | 100% | 8% |
| Success with 20% random actions injected | 100% | 100% | 100% | 8% |
| Steps / expert steps (successful episodes) | 1.00 | 1.00 | 1.00 | 0.91 |
| Mean final IoU | 1.000 | 1.000 | 1.000 | 0.960 |

The baseline in `runs/baseline_v1` was trained with rigid L3 templates, 1 epoch, and no relative goal positions. It scored 96/100/98% on L1–L3 with injected random actions, and 6% on L4. The runs taught three things:

1. **The in-distribution task is solved.** In-distribution L1–L3 is saturated: the model tracks progress through the goal, repairs injected mistakes (undo off-plan changes, re-select, switch the workbench back) and finishes in exactly the expert's step count.
2. **Template shortcuts were the first L4 failure, and the fix worked.** With rigid L3 templates, a pattern or mirror was always followed by a dressup or Done, so the model learned that ordering instead of reading the goal. It failed at the start of every second cut group (`scripts/diagnose.py` finds the first step where the policy leaves the expert's acceptable set). Randomizing L3 structure plus relative-order goal features removed that failure: L4 went from 6% to 27% after one epoch.
3. **Length extrapolation is the remaining gap, and it gets worse with more training.** Training goals have at most 5 features and L4 has 6–7. After one epoch the model mostly said `Done` once 5 features existed. After full training it fits the ≤5-feature distribution more tightly, and L4 falls to 8% with more varied errors: spurious `Std_Undo` on unfamiliar long trees, the wrong pattern type for the second group, and early `Done`. Mean IoU on L4 is still 0.96, meaning most of the part is built correctly before it derails.

## Generalization research (v3)

The v2 results above measure in-distribution skill, and 98.8% of test goals reuse a feature structure seen in training. To test real generalization, I built a benchmark of held-out splits, generated from test-only seeds:

| Suite | What is held out |
|---|---|
| `iid` | nothing: L1–L3 goals with new dimensions and starts |
| `comp` | combinations: `boss_box` together with a pattern, and `hole_std` directly followed by `mirror`. Every feature and most pairs are seen elsewhere. |
| `comp2` | confirmation: `boss_box` → `mirror`, which the training sampler never produces. Never used for any design decision. |
| `len` / `len2` / `len3` | length: 6–7 / 8–10 / 11 intents. Training has at most 5. `len3` was held back as a confirmation suite. |

Training data (`data/gen_train`, 24k episodes) excludes every held-out rule and records the expert's progress index as an auxiliary label.

### Hypotheses from the literature, tested as ablations

All runs are SFT for 3 epochs on the same data, evaluated on 60 episodes per suite. `iid`, `comp` and `len` (6–7) are omitted from the table: every variant with randomized positions scores 88–100% there, and `comp` was 97–100% for all variants in this setting. Scripts: `scripts/ablate.sh`, `round*.sh`, `eval_mappings.sh`.

| Variant | Idea (source) | 8–10 intents | 11 intents |
|---|---|---|---|
| A: v2 architecture | – | 2% | – |
| D: + progress pointer | self-monitoring progress estimation ([Ma et al. 2019](https://arxiv.org/abs/1901.03035)) | 2% | – |
| J: + length-invariant numerics | counts expressed relative to the target | 2% | – |
| B: randomized positions | [Ruoss et al. 2023](https://arxiv.org/abs/2305.16843) | 65% / 37%† | – |
| C: B + coupled ordinals | position coupling / index hints ([Cho et al. 2024](https://arxiv.org/abs/2405.20671), [Zhou et al. 2024](https://arxiv.org/abs/2402.09371)) | 80 / 68 / 78%† | 5%† |
| C, consecutive test-time indices | same model, different test-time mapping | 97 / 97 / 95% | 95 / 63 / 83% |
| K: C + modular softmax pointer | stage-wise modular policy ([Diagnosing Compositional Generalization, 2026](https://arxiv.org/html/2607.29687)) | 48%† | – |
| **L: C + modular done-head policy**, consecutive indices | this work | **100 / 100 / 100%** | **100 / 100 / 100%** |

† = evenly spread test-time mapping (the default at the time). Values separated by slashes are seeds 0 / 1 / 2.

What mattered, in order:

1. **Randomized positions.** The v2 length failure was out-of-distribution position IDs (Ruoss et al.). This alone took 6–7-intent goals from 40% to 100%.
2. **Consecutive indices at test time.** Randomized training positions and ordinals were first mapped at test time onto evenly spaced values across their range. That squeezes large indices together and falls apart at 11 intents (5–8%). Keeping them consecutive, the tightest mapping in the training support, fixed it for every randomized variant. It was chosen on the 8–10-intent suite and then confirmed on the untouched 11-intent suite.
3. **Modular policy with per-intent "done" heads (variant L).**
   - **Design.** State tokens can't see goal tokens. Each intent token sees only the state and itself, plus an END sentinel. It predicts "is there a built feature with my ordinal?", which is an equality match on coupled ordinals. The first intent that isn't done is the active one, and the action decoder sees only the state and that intent. An invariance test (`test_modular_decision_ignores_other_intents`) checks that decisions don't change when more intents are appended.
   - **Why the softmax pointer (K) failed.** It needs a learned *successor* relation (ordinal = built + 1). A per-step probe (`scripts/probe_pointer.py`) showed it was perfect up to the trained intent index and ~70% beyond. Given the correct intent, the policy itself was 100% accurate.
   - **Result.** L is the only variant at 100% on 11 intents across all three seeds.
4. **Factorized feature types (variant M = L + `--type-dropout 0.15`).**
   - **The problem.** The full-length L training run (4 epochs + DAgger) regressed on `comp` to 53%. Every failure was the unseen adjacent pair `hole_std → mirror`: the model pressed Undo, because FreeCAD's `PartDesign::Hole` object had never been followed by a mirror.
   - **Supporting evidence.** `comp2` (`boss_box → mirror`) stayed at 100%, because a boss_box becomes a `Pad`, and Pad → Mirrored is seen in training. This matches the 2026 finding that unseen *pairs* are the hard case.
   - **The fix.** Tree nodes, selected objects and recent actions get a functional-category embedding (subtractive / additive / dressup / pattern). The specific type ID is dropped 15% of the time in training. This raised `comp` from 53% to 90%.

Ideas that did not help: the progress pointer alone (D), length-invariant numerics (H, J), stochastic test-time sampling of positions, and the softmax modular pointer (K).

### Final model: `runs/final_M`

Variant M (randomized positions, coupled ordinals, length-invariant numerics, modular done-head policy, factorized types, consecutive test-time indices), trained with SFT for 4 epochs plus 2 DAgger rounds. 1,228,163 parameters. Recipe: `EXTRA="--type-dropout 0.15" OUT=runs/final_M ./scripts/train_final.sh`.

| Suite (100 episodes each) | iid L1 | L2 | L3 | comp | comp2 | 6–7 | 8–10 | 11 |
|---|---|---|---|---|---|---|---|---|
| Success | 100 | 100 | 100 | 90 | 100 | 100 | 100 | 100 |
| Success, 20% random actions injected | 100 | 100 | 96 | 95 | 94 | 97 | 91 | 91 |
| v2 model (`checkpoints/v2_indist`) | 100 | 100 | 100 | n/a‡ | – | 8 | – | – |

‡ The v2 training data included these combinations.

Per-step accuracy on held-out states: 99.84%.
