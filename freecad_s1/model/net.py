"""FreeCAD-S1: option-attention next-action scorer (~1M params, from scratch).

    state tokens ──► StateEncoder (transformer) ──► context C (B, L, d)
    candidate actions ──► ActionEncoder ──► options O (B, N, d)
    O ──► ActionDecoder: [self-attn over the action set, cross-attn O→C, FFN] x k
      ──► per-action score ──► masked softmax over the valid set

Option attention: candidate actions query the state through attention and
get one logit each, so any number of options is scored in one forward pass.
The context is a typed token sequence built from structured FreeCAD state
plus the goal; options also attend to each other, so a score can depend on
what else is on offer (e.g. whether Undo is available); a value head on the
[CLS] token serves the PPO phase.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch import nn

from ..actions import ACTION_IDS, CATEGORIES, SCOPES, WORD_VOCAB
from .featurize import A_VOCAB, ACT_VEC_DIM, B_VOCAB, MAX_POS, N_SEGMENTS, NUM_DIM


@dataclass
class S1Config:
    width: int = 128
    heads: int = 4
    enc_layers: int = 3
    dec_layers: int = 2
    ff: int = 384
    dropout: float = 0.1
    id_dropout: float = 0.1  # replace action ids by <unk> in training so word pieces carry meaning


class StateEncoder(nn.Module):
    def __init__(self, cfg: S1Config) -> None:
        super().__init__()
        d = cfg.width
        self.a = nn.Embedding(A_VOCAB, d)
        self.b = nn.Embedding(B_VOCAB, d)
        self.seg = nn.Embedding(N_SEGMENTS, d)
        self.pos = nn.Embedding(MAX_POS, d)
        # Segment-specific numeric projections: the numeric columns mean
        # different things for nodes, selection, goal features, ...
        self.num_w = nn.Parameter(torch.randn(N_SEGMENTS, NUM_DIM, d) * NUM_DIM ** -0.5)
        self.num_b = nn.Parameter(torch.zeros(N_SEGMENTS, d))
        self.in_norm = nn.LayerNorm(d)
        layer = nn.TransformerEncoderLayer(d, cfg.heads, cfg.ff, cfg.dropout, batch_first=True, norm_first=True,
                                           activation="gelu")
        self.encoder = nn.TransformerEncoder(layer, cfg.enc_layers, enable_nested_tensor=False)
        self.out_norm = nn.LayerNorm(d)

    def forward(self, batch: dict[str, torch.Tensor]) -> torch.Tensor:
        seg = batch["seg"]
        per_seg = torch.einsum("blk,skd->blsd", batch["num"], self.num_w)  # all segment projections
        idx = seg.unsqueeze(-1).unsqueeze(-1).expand(-1, -1, 1, per_seg.shape[-1])
        num = per_seg.gather(2, idx).squeeze(2) + self.num_b[seg]
        x = self.a(batch["a"]) + self.b(batch["b"]) + self.seg(seg) + self.pos(batch["pos"]) + num
        x = self.encoder(self.in_norm(x), src_key_padding_mask=~batch["token_mask"])
        return self.out_norm(x)


class ActionEncoder(nn.Module):
    def __init__(self, cfg: S1Config) -> None:
        super().__init__()
        d = cfg.width
        self.id = nn.Embedding(len(ACTION_IDS), d)
        self.cat = nn.Embedding(len(CATEGORIES), d)
        self.scope = nn.Embedding(len(SCOPES), d)
        self.words = nn.Embedding(len(WORD_VOCAB), d, padding_idx=0)
        self.vec = nn.Linear(ACT_VEC_DIM, d)
        self.mlp = nn.Sequential(nn.LayerNorm(d), nn.Linear(d, cfg.ff), nn.GELU(), nn.Linear(cfg.ff, d))
        self.id_dropout = cfg.id_dropout

    def forward(self, batch: dict[str, torch.Tensor]) -> torch.Tensor:
        ids = batch["act_id"]
        if self.training and self.id_dropout > 0:
            ids = ids.masked_fill(torch.rand(ids.shape, device=ids.device) < self.id_dropout, 0)
        w = batch["act_words"]
        wmask = w.ne(0).unsqueeze(-1).float()
        words = (self.words(w) * wmask).sum(2) / wmask.sum(2).clamp_min(1)
        x = self.id(ids) + self.cat(batch["act_cat"]) + self.scope(batch["act_scope"]) + words + self.vec(batch["act_vec"])
        return x + self.mlp(x)


class S1Model(nn.Module):
    def __init__(self, cfg: S1Config | None = None) -> None:
        super().__init__()
        self.cfg = cfg = cfg or S1Config()
        d = cfg.width
        self.state_encoder = StateEncoder(cfg)
        self.action_encoder = ActionEncoder(cfg)
        layer = nn.TransformerDecoderLayer(d, cfg.heads, cfg.ff, cfg.dropout, batch_first=True, norm_first=True,
                                           activation="gelu")
        self.decoder = nn.TransformerDecoder(layer, cfg.dec_layers)
        self.score = nn.Sequential(nn.LayerNorm(d), nn.Linear(d, d), nn.GELU(), nn.Linear(d, 1))
        self.value_head = nn.Sequential(nn.LayerNorm(d), nn.Linear(d, d), nn.GELU(), nn.Linear(d, 1))

    def forward(self, batch: dict[str, torch.Tensor]) -> tuple[torch.Tensor, torch.Tensor]:
        """Returns (logits (B, N) with -inf-like fill on padded/invalid slots, value (B,))."""
        context = self.state_encoder(batch)
        options = self.action_encoder(batch)
        amask = batch["action_mask"]
        h = self.decoder(options, context, tgt_key_padding_mask=~amask, memory_key_padding_mask=~batch["token_mask"])
        logits = self.score(h).squeeze(-1).float()
        logits = logits.masked_fill(~amask, torch.finfo(logits.dtype).min)
        value = self.value_head(context[:, 0]).squeeze(-1)
        return logits, value


def parameter_count(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def select_device(name: str = "auto") -> torch.device:
    if name != "auto":
        return torch.device(name)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def save_checkpoint(path: str | Path, model: S1Model, metadata: dict | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"config": asdict(model.cfg), "state_dict": model.state_dict(), "metadata": metadata or {}}, path)
    path.with_suffix(".json").write_text(json.dumps({"config": asdict(model.cfg), "metadata": metadata or {}}, indent=2))
    return path


def load_checkpoint(path: str | Path, device: str | torch.device = "cpu") -> S1Model:
    blob = torch.load(path, map_location="cpu", weights_only=True)
    model = S1Model(S1Config(**blob["config"]))
    model.load_state_dict(blob["state_dict"])
    return model.to(device).eval()
