"""Run expert rollouts (clean + noisy) inside FreeCAD and report stats."""
import random, sys, time, collections
from freecad_s1.runtime.session import HeadlessSession
from freecad_s1.runtime.episode import new_episode, score, step_budget
from freecad_s1.goals import sample_goal
from freecad_s1.runtime.episode import build_target, GoalBuildError

s = HeadlessSession()
rng = random.Random(0)
stats = collections.Counter()
t0 = time.time(); nsteps = 0
for level in (1, 2, 3, 4):
    feas = 0
    for ep in range(int(sys.argv[1]) if len(sys.argv) > 1 else 15):
        try:
            goal = sample_goal(level, rng); target = build_target(s, goal); feas += 1
        except GoalBuildError as e:
            stats[f"L{level}_infeasible"] += 1; continue
        for noise in (0.0, 0.3):
            from freecad_s1.goals import sample_start
            start = sample_start(rng, level); s.reset(goal, start)
            budget = step_budget(goal, start) * (3 if noise else 1)
            for t in range(budget):
                st = s.state(); valid = s.valid_actions(st); exp = s.expert()
                if not exp: stats["unrecoverable"] += 1; break
                bad = [a for a in exp if a not in valid]
                if bad:
                    stats["expert_invalid"] += 1; print("EXPERT INVALID", bad, exp, valid, goal.features, st.edit, st.selection, file=sys.stderr); break
                a = rng.choice([x for x in valid if x != "Done"]) if rng.random() < noise else exp[0]
                info = s.step(a); nsteps += 1
                if s.doc is not None and sum(e.doc_tx for e in s.undo_stack) != min(20, s.doc.UndoCount):
                    stats["undo_desync"] += 1; print("DESYNC after", a, noise, s.doc.UndoCount, s.doc.UndoNames, [(e.doc_tx) for e in s.undo_stack], list(s.recent), file=sys.stderr); break
                if info["error"]: stats["errors"] += 1; stats["err:" + info["error"][:60]] += 1
                if info["done"]: break
            sc = score(s, target)
            if not s.done and noise == 0: print("CLEAN FAIL", goal.features, list(s.recent), s.expert(), s.meta.dirty, file=sys.stderr)
            key = f"L{level}_noise{noise}"
            stats[key + "_done"] += int(s.done); stats[key + "_match"] += int(sc["match"] and s.done); stats[key + "_n"] += 1
            if s.done and not sc["match"]: print("MISMATCH", key, goal.features, sc, file=sys.stderr)
    stats[f"L{level}_feasible"] = feas
dt = time.time() - t0
for k in sorted(stats): print(k, stats[k])
print(f"{nsteps} steps in {dt:.1f}s = {1000*dt/max(nsteps,1):.1f} ms/step")
