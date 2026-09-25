"""Locate a FreeCAD Python interpreter that can `import FreeCAD`.

Override with FREECAD_PYTHON (interpreter) and FREECAD_LIB (directory that
contains FreeCAD.so / FreeCAD.pyd). Pure stdlib; used by the torch process to
spawn FreeCAD workers.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PREFIX = "@@S1 "  # marks worker responses on stdout

_CANDIDATES = [
    ("/Applications/FreeCAD.app/Contents/Resources/bin/python", "/Applications/FreeCAD.app/Contents/Resources/lib"),
    ("/usr/lib/freecad/bin/python3", "/usr/lib/freecad/lib"),
    ("/usr/lib/freecad-python3/bin/python3", "/usr/lib/freecad-python3/lib"),
]


def freecad_python() -> tuple[str, str]:
    """Return (python executable, FreeCAD lib dir)."""
    py, lib = os.environ.get("FREECAD_PYTHON"), os.environ.get("FREECAD_LIB")
    if py and lib:
        return py, lib
    for cand_py, cand_lib in _CANDIDATES:
        if Path(cand_py).exists() and Path(cand_lib).exists():
            return py or cand_py, lib or cand_lib
    if lib:
        return py or shutil.which("python3") or "python3", lib
    raise FileNotFoundError("FreeCAD not found; set FREECAD_PYTHON and FREECAD_LIB")


def freecad_env() -> dict[str, str]:
    """Environment for a subprocess running FreeCAD's Python with this repo importable."""
    _, lib = freecad_python()
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([lib, str(REPO_ROOT), env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def freecad_available() -> bool:
    try:
        freecad_python()
        return True
    except FileNotFoundError:
        return False
