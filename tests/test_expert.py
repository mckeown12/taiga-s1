from freecad_s1.expert import Meta, ObjMeta, expert_actions, expert_plan_length
from freecad_s1.goals import RECIPES
from freecad_s1.schema import Goal, GoalFeature

BOX = Goal([GoalFeature("base_box", {"w": 20, "d": 10, "h": 5}), GoalFeature("fillet_top", {"r": 1})], scale=20)


def test_start_sequence_is_order_free():
    assert set(expert_actions(BOX, Meta(workbench="PartWorkbench"))) == {"Std_New", "Std_Workbench:PartDesignWorkbench"}
    assert expert_actions(BOX, Meta(doc_open=True, workbench="PartWorkbench")) == ["Std_Workbench:PartDesignWorkbench"]
    assert expert_actions(BOX, Meta(doc_open=True, workbench="PartDesignWorkbench")) == ["PartDesign_Body"]


def _meta(**kw) -> Meta:
    m = Meta(doc_open=True, workbench="PartDesignWorkbench", body="Body")
    m.objects["Body"] = ObjMeta("Body", "body")
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def test_sketch_phase_offers_all_missing_constraints():
    m = _meta(edit="Sketch")
    m.objects["Sketch"] = ObjMeta("Sketch", "sketch", goal_ref=0, geometry=["Sketcher_CreateRectangle"],
                                  constraints=["Sketcher_ConstrainDistanceY"])
    assert set(expert_actions(BOX, m)) == {"Sketcher_ConstrainDistanceX", "Sketcher_ConstrainLock"}
    m.objects["Sketch"].constraints = list(RECIPES["base_box"].constraints)
    assert expert_actions(BOX, m) == ["Sketcher_LeaveSketch"]


def test_off_plan_change_requires_undo_and_selection_is_fixed_directly():
    m = _meta(dirty=1)
    assert expert_actions(BOX, m) == ["Std_Undo"]
    m = _meta(selection=["Face-Z"])
    assert expert_actions(BOX, m) == ["Select:Plane:XY"]


def test_dressup_and_done():
    m = _meta()
    m.objects["Sketch"] = ObjMeta("Sketch", "sketch", goal_ref=0, consumed_by="Pad")
    m.objects["Pad"] = ObjMeta("Pad", "feature", goal_ref=0)
    assert expert_actions(BOX, m) == ["Select:Edges@Face+Z"]
    m.selection = ["Edges@Face+Z"]
    assert expert_actions(BOX, m) == ["PartDesign_Fillet"]
    m.objects["Fillet"] = ObjMeta("Fillet", "feature", goal_ref=1)
    m.selection = []
    assert expert_actions(BOX, m) == ["Done"]


def test_plan_length():
    # New/WB/Body + (select, sketch, rect, 3 constraints, leave, pad) + (select, fillet) + Done
    assert expert_plan_length(BOX, False, "StartWorkbench", False) == 3 + 8 + 2 + 1
