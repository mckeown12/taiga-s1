"""Extract the final solid from an episode FCStd into a clean single-object file.

The episode file contains the PartDesign Body plus sketches/origin; rendering it
in place ghosts those over the part. This produces a one-Part::Feature document
that renders cleanly.

Usage (FreeCAD python, no display needed):
  $FREECAD_PYTHON mybuild/make_clean.py part.FCStd [clean_out.FCStd]
"""
from __future__ import annotations

import sys
from pathlib import Path

import FreeCAD as App


def main() -> None:
    srcpath = Path(sys.argv[1])
    outpath = Path(sys.argv[2]) if len(sys.argv) > 2 else srcpath.with_name(srcpath.stem + "_clean.FCStd")

    srcdoc = App.openDocument(str(srcpath))
    src = next((o for o in srcdoc.Objects if o.TypeId == "PartDesign::Body"), None)
    if src is None:
        src = next((o for o in srcdoc.Objects if hasattr(o, "Shape") and o.Shape and o.Shape.Solids), None)
    if src is None:
        print("no solid in document", file=sys.stderr)
        sys.exit(1)
    shape = src.Shape.copy()

    doc = App.newDocument("clean")
    obj = doc.addObject("Part::Feature", "Holder")
    obj.Shape = shape
    obj.Visibility = True
    doc.saveAs(str(outpath))
    print(f"clean: {outpath}  (volume {shape.Volume:.0f} mm3, {len(shape.Solids)} solid)")


if __name__ == "__main__":
    main()
