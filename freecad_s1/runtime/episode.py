"""Episode utilities that run inside FreeCAD: target construction, expert
rollouts with noise injection, and final scoring."""

from __future__ import annotations

import random

from ..expert import expert_plan_length
from ..goals import StartSpec, sample_split_goal, sample_start
from ..schema import Goal
from .session import HeadlessSession, iou, shape_info

SUCCESS_IOU = 0.99


class GoalBuildError(Exception):
    pass


def build_target(session: HeadlessSession, goal: Goal, max_steps: int = 200):
    """Run the clean expert to build the goal. Fills `goal.target` and returns
    the target solid (a detached copy). Raises GoalBuildError if the goal is
    geometrically infeasible (invalid feature, boolean failure, ...)."""
    session.reset(goal, StartSpec(doc_open=True, workbench="PartDesignWorkbench"))
    for _ in range(max_steps):
        acts = session.expert()
        if acts[0] == "Done":
            break
        if acts[0] == "Std_Undo":
            raise GoalBuildError("expert path produced an invalid feature")
        info = session.step(acts[0])
        if info["error"]:
            raise GoalBuildError(info["error"])
    else:
        raise GoalBuildError("expert did not finish")
    shape = session.solid()
    if shape is None or not shape.isValid() or len(shape.Solids) != 1:
        raise GoalBuildError("target is not a single valid solid")
    goal.target = shape_info(shape)
    target = shape.copy()
    session.close()
    return target


def sample_feasible_goal(session: HeadlessSession, level: int, rng: random.Random, tries: int = 20,
                         split: str = "train"):
    for _ in range(tries):
        goal = sample_split_goal(split, level, rng)
        try:
            target = build_target(session, goal)
        except GoalBuildError:
            continue
        return goal, target
    raise GoalBuildError(f"no feasible goal at level {level} after {tries} tries")


def step_budget(goal: Goal, start: StartSpec) -> int:
    n = expert_plan_length(goal, start.doc_open, start.workbench, start.body)
    return 2 * n + 6


def score(session: HeadlessSession, target) -> dict:
    shape = session.solid()
    value = iou(shape, target)
    return {"iou": value, "match": value >= SUCCESS_IOU}


def new_episode(session: HeadlessSession, level: int, rng: random.Random, split: str = "train"):
    goal, target = sample_feasible_goal(session, level, rng, split=split)
    start = sample_start(rng, level)
    session.reset(goal, start)
    return goal, start, target
