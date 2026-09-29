"""Render a FreeCAD FCStd to orthographic PNGs (top/iso/front) + STL.

Working headless chain for FreeCAD 1.1 (AppImage python):
  QApplication -> Gui.showMainWindow() -> openDocument -> set visibility
  -> Gui.updateGui() -> processEvents -> view operations -> saveImage

Camera quaternions are captured once from the standard views (which
animate), then applied directly to the camera node for the actual
captures, so no transition frame can bleed into a saved image.
"""
import os
import pathlib
import sys
import time

import FreeCAD as App
from PySide6.QtWidgets import QApplication
import FreeCADGui as Gui
import MeshPart


def pump(app, s):
    end = time.time() + s
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def main():
    path, outdir = sys.argv[1], sys.argv[2]
    app = QApplication([])
    Gui.showMainWindow()

    doc = App.openDocument(path)
    doc.recompute()

    body = None
    for o in doc.Objects:
        if hasattr(o, "Shape") and o.Shape and o.Shape.Solids:
            body = o
    if body is None:
        sys.exit("no solid object found in document")
    for o in doc.Objects:
        # PartDesign features only draw while their Body stays visible
        o.Visibility = (o is body) or o.TypeId == "PartDesign::Body"
    Gui.updateGui()
    pump(app, 0.5)

    os.makedirs(outdir, exist_ok=True)
    stl = pathlib.Path(outdir) / (body.Name + ".stl")
    mesh = MeshPart.meshFromShape(Shape=body.Shape, LinearDeflection=0.1, AngularDeflection=0.5)
    mesh.write(str(stl))

    view = Gui.activeDocument().activeView()
    view.setCameraType("Orthographic")

    def capture(attr):
        getattr(view, attr)()
        pump(app, 1.2)  # let the animation finish, then read the final orientation
        return view.getCameraOrientation()

    q_top = capture("viewTop")
    q_iso = capture("viewIsometric")
    q_front = capture("viewFront")

    for name, q in (("top", q_top), ("iso", q_iso), ("front", q_front)):
        view.setCameraOrientation(q)  # direct set: no animation
        pump(app, 0.3)
        view.fitAll()
        pump(app, 0.5)
        view.saveImage(os.path.join(outdir, f"{body.Name}_{name}.png"), 1024, 1024, "White")

    print(f"rendered {outdir} stl={stl}")


if __name__ == "__main__":
    main()
