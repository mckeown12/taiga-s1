"""Torch-side handles on FreeCAD worker processes (no FreeCAD import here)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field

from ..schema import Goal, State
from .fcenv import PROTOCOL_PREFIX as PREFIX
from .fcenv import freecad_env, freecad_python


class WorkerError(RuntimeError):
    pass


class FreeCADEnv:
    """One FreeCAD worker process. `send` + `recv` are split so several
    workers can compute concurrently (see `VecEnv`)."""

    def __init__(self) -> None:
        py, _ = freecad_python()
        self.proc = subprocess.Popen(
            [py, "-m", "freecad_s1.runtime.worker"], env=freecad_env(), text=True, bufsize=1,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )

    def send(self, req: dict) -> None:
        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()

    def recv(self) -> dict:
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise WorkerError(f"FreeCAD worker exited (code {self.proc.poll()})")
            if line.startswith(PREFIX):
                resp = json.loads(line[len(PREFIX):])
                if not resp.get("ok"):
                    raise WorkerError(resp.get("error", "unknown error"))
                return resp

    def call(self, req: dict) -> dict:
        self.send(req)
        return self.recv()

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                self.send({"op": "quit"})
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()


@dataclass
class Episode:
    """Book-keeping for one running episode inside a VecEnv slot."""

    goal: Goal
    budget: int
    level: int
    state: State
    actions: list[str]
    expert: list[str]
    steps: int = 0
    agree: int = 0
    done: bool = False
    history: list[str] = field(default_factory=list)
    outcome: str = ""
    iou: float = 0.0


class VecEnv:
    """N FreeCAD workers stepped in lockstep so the policy can batch."""

    def __init__(self, n: int) -> None:
        self.envs = [FreeCADEnv() for _ in range(n)]

    def __len__(self) -> int:
        return len(self.envs)

    def reset(self, specs: list[dict]) -> list[Episode]:
        for env, spec in zip(self.envs, specs):
            env.send({"op": "reset", **spec})
        eps = []
        for env, spec in zip(self.envs, specs):
            r = env.recv()
            goal = Goal.from_json(r["goal"])
            eps.append(Episode(goal, r["budget"], spec.get("level", goal.level), State.from_json(r["state"]),
                               r["actions"], r["expert"]))
        return eps

    def step(self, idx: list[int], actions: list[str], reward: bool = False) -> list[dict]:
        for i, a in zip(idx, actions):
            self.envs[i].send({"op": "step", "action": a, "reward": reward})
        return [self.envs[i].recv() for i in idx]

    def score(self, idx: list[int]) -> list[dict]:
        for i in idx:
            self.envs[i].send({"op": "score"})
        return [self.envs[i].recv() for i in idx]

    def close(self) -> None:
        for env in self.envs:
            env.close()
