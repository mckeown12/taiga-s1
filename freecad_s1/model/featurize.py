"""State/goal/action -> token arrays (numpy), and batch collation (torch).

The state is encoded as a *sequence of typed tokens*, not a flat vector:

    [CLS] [GLOBAL] [NODE x tree order ...] [SEL ...] [RECENT x recency ...]
    [GOAL_GLOBAL] [GOAL_FEAT x goal order ...]

Every token carries a segment id, a primary categorical id (node type,
selection kind, action id, goal kind, workbench), a secondary categorical id
(tree depth / selected object type), a position (tree index, recency, goal
order) and a segment-specific numeric vector. Feature-tree nodes keep their
document order and parent depth so the encoder sees the tree as a sequence.

Candidate actions are encoded independently of the state: catalogue id,
category, scope, word pieces of the command name, and an argument vector.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..actions import ACTION_IDS, CATALOGUE, CATEGORIES, SCOPES, WORD_VOCAB, action_vector, action_words
from ..schema import (
    CONSTRAINT_KINDS, GEOMETRY_KINDS, GOAL_KINDS, GOAL_LENGTH_KEYS, GOAL_PARAM_KEYS, LENGTH_KEYS,
    NODE_NUM_KEYS, NODE_TYPES, SELECTION_KINDS, WORKBENCHES, Goal, State,
)

SEG_CLS, SEG_GLOBAL, SEG_NODE, SEG_SEL, SEG_RECENT, SEG_GOAL_GLOBAL, SEG_GOAL = range(7)
N_SEGMENTS = 7
NUM_DIM = len(NODE_NUM_KEYS) + len(GEOMETRY_KINDS) + len(CONSTRAINT_KINDS)
MAX_POS = 64
MAX_NODES = 40
MAX_SEL = 4
MAX_GOAL = 8
MAX_WORDS = 8
ACT_VEC_DIM = 6

# Primary-id vocab per segment, laid out in one shared embedding table.
_A_SIZES = [1, len(WORKBENCHES), len(NODE_TYPES), len(SELECTION_KINDS), len(ACTION_IDS), 1, len(GOAL_KINDS)]
A_OFFSETS = np.cumsum([0] + _A_SIZES[:-1]).tolist()
A_VOCAB = int(sum(_A_SIZES))
B_VOCAB = len(NODE_TYPES) + 4  # depth buckets share the table with object types

_NODE_TYPE = {t: i for i, t in enumerate(NODE_TYPES)}
_WB = {w: i for i, w in enumerate(WORKBENCHES)}
_SEL = {k: i for i, k in enumerate(SELECTION_KINDS)}
_ACT = {a: i for i, a in enumerate(ACTION_IDS)}
_GOAL = {k: i for i, k in enumerate(GOAL_KINDS)}
_CAT = {c: i for i, c in enumerate(CATEGORIES)}
_SCOPE = {c: i for i, c in enumerate(SCOPES)}
_WORD = {w: i for i, w in enumerate(WORD_VOCAB)}
FACE_DIRS = ["+Z", "-Z", "+X", "-X", "+Y", "-Y", "|Z"]


@dataclass
class Tokens:
    seg: np.ndarray  # (L,) int8
    a: np.ndarray  # (L,) int16  (already offset into A_VOCAB)
    b: np.ndarray  # (L,) int16
    pos: np.ndarray  # (L,) int8
    num: np.ndarray  # (L, NUM_DIM) float16


def _clip(x: float, lim: float = 8.0) -> float:
    return float(max(-lim, min(lim, x)))


def encode_state(state: State, goal: Goal) -> Tokens:
    scale = goal.scale if goal.scale > 0 else 1.0
    tgt_vol = goal.target.volume if goal.target.volume > 0 else scale ** 3
    rows: list[tuple[int, int, int, int, list[float]]] = []

    rows.append((SEG_CLS, 0, 0, 0, []))

    sh = state.shape
    g = [float(state.doc_open), float(state.has_body), float(state.edit is not None), float(state.undo_available),
         len(state.selection) / 4, float(sh.valid), _clip(sh.volume / tgt_vol),
         *(_clip(x / scale) for x in sh.bbox), sh.n_faces / 50, sh.n_edges / 100, float(sh.n_solids),
         *(float(d in sh.face_dirs) for d in FACE_DIRS), len(state.tree) / 10]
    rows.append((SEG_GLOBAL, _WB.get(state.workbench, 0), 0, 0, g))

    for i, node in enumerate(state.tree[:MAX_NODES]):
        num = [_clip(node.num.get(k, 0.0) / (scale if k in LENGTH_KEYS else 1.0)) for k in NODE_NUM_KEYS]
        num += [node.geo.get(k, 0) / 10 for k in GEOMETRY_KINDS]
        num += [node.cons.get(k, 0) / 10 for k in CONSTRAINT_KINDS]
        b = len(NODE_TYPES) + min(node.depth, 3)
        rows.append((SEG_NODE, _NODE_TYPE.get(node.type, 0), b, min(i, MAX_POS - 1), num))

    for i, sel in enumerate(state.selection[:MAX_SEL]):
        num = [*sel.normal, _clip(sel.offset / scale), sel.count / 10]
        rows.append((SEG_SEL, _SEL.get(sel.kind, _SEL["other"]), _NODE_TYPE.get(sel.object_type, 0), i, num))

    for i, act in enumerate(reversed(state.recent)):
        rows.append((SEG_RECENT, _ACT.get(act, 0), 0, i, []))

    t = goal.target
    gg = [*(_clip(x / scale) for x in t.bbox), _clip(t.volume / scale ** 3), t.n_faces / 50, t.n_edges / 100,
          len(goal.features) / 10]
    rows.append((SEG_GOAL_GLOBAL, 0, 0, 0, gg))

    for i, f in enumerate(goal.features[:MAX_GOAL]):
        num = []
        for k in GOAL_PARAM_KEYS:
            v = f.params.get(k)
            num.append(0.0 if v is None else _clip(v / scale if k in GOAL_LENGTH_KEYS else v / 10))
        num += [float(k in f.params) for k in GOAL_PARAM_KEYS]
        # Relative order, so "which intent is next / is this the last one"
        # does not hinge on absolute position embeddings seen in training.
        n_goal = len(goal.features)
        num += [i / max(n_goal - 1, 1), float(i == n_goal - 1), (n_goal - 1 - i) / 10]
        rows.append((SEG_GOAL, _GOAL.get(f.kind, 0), 0, min(i, MAX_POS - 1), num))

    n = len(rows)
    seg = np.zeros(n, np.int8)
    a = np.zeros(n, np.int16)
    b = np.zeros(n, np.int16)
    pos = np.zeros(n, np.int8)
    num = np.zeros((n, NUM_DIM), np.float16)
    for j, (s, ai, bi, p, v) in enumerate(rows):
        seg[j], a[j], b[j], pos[j] = s, A_OFFSETS[s] + ai, bi, p
        if v:
            num[j, : len(v)] = v
    return Tokens(seg, a, b, pos, num)


_ACTION_CACHE: dict[str, tuple[int, int, int, list[int], list[float]]] = {}


def encode_action(action_id: str) -> tuple[int, int, int, list[int], list[float]]:
    """(id, category, scope, word ids[MAX_WORDS], arg vector) for one action.
    Unknown commands (e.g. from a live GUI) keep their word pieces."""
    hit = _ACTION_CACHE.get(action_id)
    if hit is not None:
        return hit
    spec = CATALOGUE.get(action_id)
    words = [_WORD.get(w, 1) for w in action_words(action_id)][:MAX_WORDS]
    words += [0] * (MAX_WORDS - len(words))
    out = (_ACT.get(action_id, 0), _CAT.get(spec.category, 0) if spec else 0,
           _SCOPE.get(spec.scope, 0) if spec else 0, words, action_vector(action_id))
    _ACTION_CACHE[action_id] = out
    return out


def encode_actions(actions: list[str]) -> dict[str, np.ndarray]:
    enc = [encode_action(a) for a in actions]
    return {
        "id": np.array([e[0] for e in enc], np.int16),
        "cat": np.array([e[1] for e in enc], np.int8),
        "scope": np.array([e[2] for e in enc], np.int8),
        "words": np.array([e[3] for e in enc], np.int16).reshape(len(enc), MAX_WORDS),
        "vec": np.array([e[4] for e in enc], np.float32).reshape(len(enc), ACT_VEC_DIM),
    }


@dataclass
class Example:
    tokens: Tokens
    actions: dict[str, np.ndarray]
    target: np.ndarray  # (N,) bool, acceptable actions


def make_example(state: State, goal: Goal, actions: list[str], acceptable: list[str] | None = None) -> Example:
    acc = set(acceptable or [])
    return Example(encode_state(state, goal), encode_actions(actions),
                   np.array([a in acc for a in actions], dtype=bool))


def collate(examples: list[Example]):
    """Pad a list of examples into a dict of torch tensors."""
    import torch

    bsz = len(examples)
    L = max(len(e.tokens.seg) for e in examples)
    N = max(len(e.target) for e in examples)
    seg = np.zeros((bsz, L), np.int64)
    a = np.zeros((bsz, L), np.int64)
    b = np.zeros((bsz, L), np.int64)
    pos = np.zeros((bsz, L), np.int64)
    num = np.zeros((bsz, L, NUM_DIM), np.float32)
    tmask = np.zeros((bsz, L), bool)
    aid = np.zeros((bsz, N), np.int64)
    cat = np.zeros((bsz, N), np.int64)
    scope = np.zeros((bsz, N), np.int64)
    words = np.zeros((bsz, N, MAX_WORDS), np.int64)
    vec = np.zeros((bsz, N, ACT_VEC_DIM), np.float32)
    amask = np.zeros((bsz, N), bool)
    target = np.zeros((bsz, N), bool)
    for i, e in enumerate(examples):
        t, n = len(e.tokens.seg), len(e.target)
        seg[i, :t], a[i, :t], b[i, :t], pos[i, :t] = e.tokens.seg, e.tokens.a, e.tokens.b, e.tokens.pos
        num[i, :t] = e.tokens.num
        tmask[i, :t] = True
        aid[i, :n], cat[i, :n], scope[i, :n] = e.actions["id"], e.actions["cat"], e.actions["scope"]
        words[i, :n], vec[i, :n] = e.actions["words"], e.actions["vec"]
        amask[i, :n] = True
        target[i, :n] = e.target
    to = torch.from_numpy
    return {
        "seg": to(seg), "a": to(a), "b": to(b), "pos": to(pos), "num": to(num), "token_mask": to(tmask),
        "act_id": to(aid), "act_cat": to(cat), "act_scope": to(scope), "act_words": to(words),
        "act_vec": to(vec), "action_mask": to(amask), "target": to(target),
    }
