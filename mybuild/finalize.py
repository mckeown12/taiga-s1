"""Export the trained checkpoint to Hugging Face layout (model.safetensors + config.json)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_s1.model.net import load_checkpoint, save_pretrained

src = sys.argv[1] if len(sys.argv) > 1 else "checkpoints/taiga_hook/last.pt"
dst = sys.argv[2] if len(sys.argv) > 2 else "checkpoints/taiga_hook/hf"
m = load_checkpoint(src)
save_pretrained(dst, m, {"note": "taiga-s1 + hook_sweep (baby-gate J-hook)"})
print("exported:", dst)
