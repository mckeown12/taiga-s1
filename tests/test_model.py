import random

import torch

from freecad_s1.actions import CATALOGUE, action_words
from freecad_s1.goals import sample_goal
from freecad_s1.model.featurize import collate, make_example
from freecad_s1.model.net import S1Model, parameter_count
from freecad_s1.schema import Node, SelItem, ShapeInfo, State


def _state(n_nodes: int = 3) -> State:
    tree = [Node("Body", "PartDesign::Body", num={"active_body": 1.0})]
    for i in range(1, n_nodes):
        tree.append(Node(f"Sketch{i}", "Sketcher::SketchObject", parent=0, depth=1,
                         num={"n_geo": 0.4, "closed": 1.0, "sk_w": 20.0}, geo={"line": 4}, cons={"Horizontal": 2}))
    return State(doc_open=True, workbench="PartDesignWorkbench", has_body=True, tree=tree,
                 selection=[SelItem("face", "Pad", "PartDesign::Pad", ["Face6"], (0, 0, 1), 10.0, 1)],
                 recent=["PartDesign_Body", "Select:Plane:XY"], shape=ShapeInfo(True, 1000.0, 600.0, (10, 10, 10), 6, 12, 1, ["+Z"]))


def test_parameter_budget():
    n = parameter_count(S1Model())
    assert 500_000 <= n <= 2_000_000, n


def test_variable_action_sets_and_masking():
    goal = sample_goal(3, random.Random(0))
    a1 = ["PartDesign_Pad", "Std_Undo", "Done"]
    a2 = list(CATALOGUE)[:30]
    batch = collate([make_example(_state(2), goal, a1, ["PartDesign_Pad"]), make_example(_state(6), goal, a2, ["Done"])])
    model = S1Model().eval()
    logits, value = model(batch)
    assert logits.shape == (2, 30) and value.shape == (2,)
    probs = torch.softmax(logits, -1)
    assert torch.allclose(probs.sum(-1), torch.ones(2), atol=1e-5)
    assert probs[0, 3:].max() < 1e-6  # padded slots get no mass


def test_scores_are_permutation_equivariant():
    goal = sample_goal(2, random.Random(1))
    acts = ["PartDesign_Pad", "Std_Undo", "Done", "Select:Face+Z", "PartDesign_Pocket"]
    model = S1Model().eval()
    l1, _ = model(collate([make_example(_state(), goal, acts)]))
    perm = [3, 0, 4, 2, 1]
    l2, _ = model(collate([make_example(_state(), goal, [acts[i] for i in perm])]))
    assert torch.allclose(l1[0, perm], l2[0], atol=1e-4)


def test_unknown_command_still_encodes():
    goal = sample_goal(1, random.Random(2))
    ex = make_example(_state(), goal, ["PartDesign_Pad", "PartDesign_SubtractiveHelix"])
    assert ex.actions["id"][1] == 0  # <unk> id ...
    assert (ex.actions["words"][1] > 1).sum() >= 2  # ... but known word pieces survive
    assert action_words("Select:Edges@Face+Z")[:2] == ["select", "edges"]
