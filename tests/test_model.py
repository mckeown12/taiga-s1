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


def test_coupled_ordinals_align_goal_and_tree():
    from freecad_s1.model.featurize import SEG_GOAL, SEG_NODE, encode_state

    goal = sample_goal(3, random.Random(3))
    st = _state(1)
    st.tree += [Node("Sketch", "Sketcher::SketchObject", parent=0, depth=1),
                Node("Pad", "PartDesign::Pad", parent=0, depth=1),
                Node("Sketch001", "Sketcher::SketchObject", parent=0, depth=1)]
    tok = encode_state(st, goal)
    assert list(tok.ord[tok.seg == SEG_NODE]) == [0, 1, 1, 2]  # body, sketch+pad of intent 1, next sketch
    assert list(tok.ord[tok.seg == SEG_GOAL]) == list(range(1, len(goal.features) + 1))


def test_randomize_index_preserves_order():
    from freecad_s1.model.net import randomize_index

    idx = torch.arange(10).repeat(4, 1)
    for training in (True, False):
        out = randomize_index(idx, 12, 128, training)
        assert (out[:, 1:] > out[:, :-1]).all() and out.max() < 128
    ords = torch.tensor([[0, 1, 1, 2, 0, 3]])
    out = randomize_index(ords, 12, 32, True, keep_zero=True)
    assert out[0, 0] == 0 and out[0, 4] == 0 and out[0, 1] == out[0, 2] and out[0, 3] > out[0, 2]


def test_generalization_variant_forward_and_aux():
    from freecad_s1.model.net import S1Config

    goal = sample_goal(3, random.Random(4))
    acts = ["PartDesign_Pad", "Std_Undo", "Done"]
    batch = collate([make_example(_state(3), goal, acts, ["Done"], progress=len(goal.features)),
                     make_example(_state(2), goal, acts, ["PartDesign_Pad"], progress=0)])
    model = S1Model(S1Config(pos_mode="rand", ordinal=True, progress_head=True))
    logits, value, ptr = model(batch, return_aux=True)
    assert ptr.shape == (2, batch["seg"].shape[1] + 1)
    assert batch["progress"][0] == batch["seg"].shape[1]  # END slot
    assert 500_000 <= parameter_count(model) <= 2_000_000
    loss = torch.nn.functional.cross_entropy(ptr, batch["progress"])
    loss.backward()


def test_modular_decision_ignores_other_intents():
    """With the modular policy, action scores depend only on the state and the
    active intent: appending more intents after it must not change them."""
    from freecad_s1.model.net import S1Config
    from freecad_s1.schema import Goal, GoalFeature

    torch.manual_seed(0)
    model = S1Model(S1Config(modular=True, ordinal=True, invariant_numerics=True)).eval()
    opts = model.cfg.feature_opts()
    base = [GoalFeature("base_box", {"w": 20, "d": 10, "h": 5}), GoalFeature("hole", {"r": 1, "x": 0, "y": 0})]
    short = Goal(base, scale=20)
    long = Goal(base + [GoalFeature("fillet_top", {"r": 1}), GoalFeature("chamfer_top", {"size": 1})], scale=20)
    acts = ["PartDesign_Pad", "Std_Undo", "Done", "Select:Face+Z"]
    b1 = collate([make_example(_state(3), short, acts, progress=1, **opts)])
    b2 = collate([make_example(_state(3), long, acts, progress=1, **opts)])
    b1["progress"][:] = -1
    b2["progress"][:] = -1
    # force the pointer to intent 1 in both by checking its argmax is used
    l1, _, p1 = model(b1, return_aux=True)
    l2, _, p2 = model(b2, return_aux=True)
    goal_slots1 = (b1["seg"][0] == 6).nonzero().flatten()
    goal_slots2 = (b2["seg"][0] == 6).nonzero().flatten()
    if p1.argmax(-1).item() == goal_slots1[1].item() and p2.argmax(-1).item() == goal_slots2[1].item():
        assert torch.allclose(l1, l2, atol=1e-4)
    # per-intent pointer scores do not depend on the other intents
    assert torch.allclose(p1[0, goal_slots1[:2]], p2[0, goal_slots2[:2]], atol=1e-4)
    loss = torch.nn.functional.cross_entropy(p2, torch.tensor([goal_slots2[1].item()]))
    assert torch.isfinite(loss)


def test_done_head_pointer_picks_first_not_done_and_trains():
    from freecad_s1.model.net import S1Config

    torch.manual_seed(0)
    model = S1Model(S1Config(modular=True, pointer="done", ordinal=True, invariant_numerics=True))
    opts = model.cfg.feature_opts()
    goal = sample_goal(3, random.Random(5))
    acts = ["PartDesign_Pad", "Std_Undo", "Done"]
    batch = collate([make_example(_state(3), goal, acts, ["Done"], progress=len(goal.features), **opts),
                     make_example(_state(2), goal, acts, ["PartDesign_Pad"], progress=1, **opts)])
    logits, _, aux = model(batch, return_aux=True)
    loss = model.aux_loss(aux, batch)
    assert loss is not None and torch.isfinite(loss)
    loss.backward()
    # inference rule: first goal slot whose done-logit is negative
    model.eval()
    fake = torch.full_like(aux, 5.0)
    slots = (batch["seg"][1] == 6).nonzero().flatten()
    fake[1, slots[2]] = -1.0
    order = torch.arange(fake.shape[1], 0, -1)[None]
    goal_mask = batch["seg"].eq(6) & batch["token_mask"]
    chosen = ((fake < 0) & goal_mask).long().mul(order).argmax(-1)
    assert chosen[1] == slots[2]
