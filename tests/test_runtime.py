"""Integration tests against real FreeCAD (skipped when FreeCAD is absent)."""
import subprocess

import pytest

from freecad_s1.runtime.fcenv import REPO_ROOT, freecad_available, freecad_env, freecad_python

pytestmark = pytest.mark.skipif(not freecad_available(), reason="FreeCAD not installed")


def test_expert_rollouts_clean_and_noisy():
    py, _ = freecad_python()
    out = subprocess.run([py, str(REPO_ROOT / "scripts" / "smoke_expert.py"), "6"], env=freecad_env(),
                         capture_output=True, text=True, timeout=600)
    stats = dict(line.rsplit(" ", 1) for line in out.stdout.splitlines() if line.startswith("L") or line.startswith("un"))
    for level in (1, 2, 3):
        for noise in ("0.0", "0.3"):
            n = int(stats[f"L{level}_noise{noise}_n"])
            assert int(stats.get(f"L{level}_noise{noise}_match", 0)) == n, out.stdout
    assert "expert_invalid" not in stats and "undo_desync" not in stats, out.stdout + out.stderr


def test_worker_protocol_roundtrip():
    from freecad_s1.runtime.client import VecEnv

    vec = VecEnv(2)
    try:
        eps = vec.reset([{"level": 2, "seed": 3}, {"level": 1, "seed": 4}])
        for _ in range(200):
            live = [i for i, e in enumerate(eps) if e.expert and e.expert[0] != "Done"]
            if not live:
                break
            for i, r in zip(live, vec.step(live, [eps[i].expert[0] for i in live], reward=True)):
                assert r["info"]["error"] is None
                eps[i].expert = r["expert"]
        vec.step([0, 1], ["Done", "Done"])
        assert all(s["match"] for s in vec.score([0, 1]))
    finally:
        vec.close()
