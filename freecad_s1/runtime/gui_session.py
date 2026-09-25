"""Live-GUI runtime: same interface as HeadlessSession, but workbench, edit
mode, selection and the valid action set come from FreeCADGui.

    Gui.activeWorkbench()                  -> State.workbench
    Gui.ActiveDocument.getInEdit()         -> State.edit
    Gui.Selection.getSelectionEx()         -> State.selection
    Gui.listCommands()/isCommandActive()   -> valid actions (catalogue ∩ active commands)
    Gui.Selection.addObserver()            -> events stream
    App.addDocumentObserver()              -> events stream (inherited)

Execution: commands that run without interaction (Std_ViewFitAll,
workbench switches, Undo, entering/leaving sketch edit, selection) go
through the GUI. Commands that would open an interactive tool or task
dialog in the GUI (sketch geometry, constraints, Pad/Pocket/... dialogs) are
executed through the same App-level executors as headless mode — their
effect on the document is identical, and it keeps the agent from blocking
on a modal dialog. Parameters come from the parameter stage (runtime.params).

Load inside a running FreeCAD GUI (Python console or macro):

    from freecad_s1.runtime.gui_session import GuiSession
    s = GuiSession(); s.reset(goal); s.valid_actions(); s.step("Select:Plane:XY")

Not exercised by the automated tests (they run headless).
"""

from __future__ import annotations

import FreeCAD as App
import FreeCADGui as Gui

from ..actions import CATALOGUE, enumerate_actions
from ..goals import StartSpec
from ..schema import Goal, SelItem, State
from .session import HeadlessSession, snapshot

# Pseudo-commands that have no Gui command of their own.
_PSEUDO_PREFIXES = ("Select:", "Done")


class _SelectionObserver:
    def __init__(self, sink):
        self.sink = sink

    def addSelection(self, doc, obj, sub, pnt):  # noqa: N802 (FreeCAD callback names)
        self.sink.append(f"select:{obj}.{sub}")

    def removeSelection(self, doc, obj, sub):  # noqa: N802
        self.sink.append(f"deselect:{obj}.{sub}")

    def clearSelection(self, doc):  # noqa: N802
        self.sink.append("clear_selection")


class GuiSession(HeadlessSession):
    def __init__(self) -> None:
        super().__init__()
        self._sel_observer = _SelectionObserver(self.events)
        Gui.Selection.addObserver(self._sel_observer)

    def shutdown(self) -> None:
        Gui.Selection.removeObserver(self._sel_observer)
        super().shutdown()

    # -- state from the GUI ------------------------------------------------

    def workbench(self) -> str:
        wb = Gui.activeWorkbench()
        return wb.name() if hasattr(wb, "name") else type(wb).__name__

    def edit_object(self) -> str | None:
        gdoc = Gui.ActiveDocument
        vp = gdoc.getInEdit() if gdoc is not None else None
        return vp.Object.Name if vp is not None else None

    def state(self) -> State:
        self.meta.workbench = self.workbench()
        self.meta.edit = self.edit_object()
        st = snapshot(self)
        st.selection = self._gui_selection()
        return st

    def _gui_selection(self) -> list[SelItem]:
        items = []
        for sx in Gui.Selection.getSelectionEx():
            obj = sx.Object
            subs = list(sx.SubElementNames)
            if obj.TypeId == "App::Plane":
                n = obj.Placement.Rotation.multVec(App.Vector(0, 0, 1))
                items.append(SelItem("plane", obj.Name, obj.TypeId, subs, (n.x, n.y, n.z), 0.0, 0))
            elif subs and all(s.startswith("Face") for s in subs):
                f = obj.Shape.getElement(subs[0])
                u0, u1, v0, v1 = f.ParameterRange
                n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
                items.append(SelItem("face", obj.Name, obj.TypeId, subs, (n.x, n.y, n.z),
                                     f.CenterOfMass.dot(n), len(subs)))
            elif subs and all(s.startswith("Edge") for s in subs):
                items.append(SelItem("edges", obj.Name, obj.TypeId, subs, (0.0, 0.0, 0.0), 0.0, len(subs)))
            elif not subs and obj.TypeId.startswith("PartDesign::"):
                items.append(SelItem("feature", obj.Name, obj.TypeId, [], (0.0, 0.0, 0.0), 0.0, 0))
            elif not subs and obj.TypeId == "Sketcher::SketchObject":
                items.append(SelItem("sketch", obj.Name, obj.TypeId, [], (0.0, 0.0, 0.0), 0.0, 0))
            else:
                items.append(SelItem("other", obj.Name, obj.TypeId, subs, (0.0, 0.0, 0.0), 0.0, len(subs)))
        return items

    def valid_actions(self, state: State | None = None) -> list[str]:
        state = state or self.state()
        known = set(Gui.listCommands())
        out = []
        for a in enumerate_actions(state):
            if a.startswith(_PSEUDO_PREFIXES) or a.startswith("Std_Workbench:"):
                out.append(a)
                continue
            cmd = a.split(":", 1)[0]
            if cmd in known and (Gui.isCommandActive(cmd) or cmd.startswith("Sketcher_")):
                out.append(a)
            elif cmd not in known:
                out.append(a)  # command not registered in this build: keep the headless semantics
        return out

    # -- execution ---------------------------------------------------------

    def reset(self, goal: Goal, start: StartSpec | None = None) -> None:
        start = start or StartSpec()
        super().reset(goal, start)
        if start.workbench != "StartWorkbench":
            Gui.activateWorkbench(start.workbench)
        self.meta.workbench = self.workbench()

    def step(self, action: str) -> dict:
        spec = CATALOGUE.get(action)
        if action.startswith("Std_Workbench:"):
            Gui.activateWorkbench(action.split(":", 1)[1])
        info = super().step(action)
        if spec is None or info["error"]:
            return info
        if action == "Std_ViewFitAll" and Gui.ActiveDocument is not None:
            Gui.runCommand("Std_ViewFitAll")
        self._sync_gui()
        return info

    def _sync_gui(self) -> None:
        """Mirror session bookkeeping (selection, edit mode) into the GUI."""
        if self.doc is None:
            return
        App.setActiveDocument(self.doc.Name)
        gdoc = Gui.getDocument(self.doc.Name)
        in_edit = gdoc.getInEdit()
        if self.meta.edit and (in_edit is None or in_edit.Object.Name != self.meta.edit):
            gdoc.setEdit(self.meta.edit)
        elif not self.meta.edit and in_edit is not None:
            gdoc.resetEdit()
        Gui.Selection.clearSelection()
        for obj_name, subs, _ in self.sel_refs:
            if subs:
                for sub in subs:
                    Gui.Selection.addSelection(self.doc.Name, obj_name, sub)
            else:
                Gui.Selection.addSelection(self.doc.Name, obj_name)
        if self.body is not None:
            view = gdoc.ActiveView
            if view is not None and hasattr(view, "setActiveObject"):
                view.setActiveObject("pdbody", self.body)
