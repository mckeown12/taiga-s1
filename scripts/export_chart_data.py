"""Export chart data from results/ to viz/src/data.json (read by the Remotion stills)."""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"


def clean(path: Path, key: str):
    if not path.exists():
        return None
    eps = json.loads(path.read_text())["episodes"]
    return round(100 * eps[key]["clean_success"], 1) if key in eps else None


final, stress = RES / "eval.json", RES / "charts/taiga_stress.json"
v2_iid, v2_old, v2_new = ROOT / "checkpoints/v2_indist/eval.json", RES / "eval_v2_baseline.json", RES / "charts/v2_len2_len4.json"
mean = lambda xs: round(sum(xs) / len(xs), 1) if xs and None not in xs else None
length = {
    "categories": ["≤5", "6–7", "8–9", "11", "13", "15", "17"],
    "trainingIndex": 0,
    "series": [
        {"name": "Taiga-S1", "values": [mean([clean(final, f"iid-L{i}") for i in (1, 2, 3)]), clean(final, "len-L4"),
                                          clean(final, "len2-L5"), clean(final, "len3-L6"), clean(stress, "len4-L7"),
                                          clean(stress, "len5-L8"), clean(stress, "len6-L9")]},
        {"name": "Previous model (v2)", "values": [mean([clean(v2_iid, f"L{i}") for i in (1, 2, 3)]), clean(v2_old, "len-L4"),
                                                    clean(v2_new, "len2-L5"), clean(v2_old, "len3-L6"), clean(v2_new, "len4-L7"),
                                                    None, None]},
    ],
}
rows = [("v2 architecture", ["A_abs_s0", "A_abs_s1"]), ("+ randomized positions", ["B_rand_s0", "B_rand_s1"]),
        ("+ coupled ordinals", ["C_rand_ord_s0", "C_rand_ord_s1", "C_rand_ord_s2"]),
        ("+ modular done-head policy", ["L_done_s0", "L_done_s1", "L_done_s2"])]
ablation = []
for label, runs in rows:
    vals = [v for v in (clean(RES / f"charts/abl_{r}.json", "len3-L6") for r in runs) if v is not None]
    if vals:
        ablation.append({"label": label, "seeds": vals, "mean": mean(vals)})
ablation.append({"label": "Taiga-S1", "sublabel": "+ factorized types, DAgger", "seeds": [clean(final, "len3-L6")],
                 "mean": clean(final, "len3-L6"), "final": True})
out = ROOT / "viz/src/data.json"
out.write_text(json.dumps({"length": length, "ablation": ablation}, indent=2, ensure_ascii=False))
print("wrote", out)

parts = ROOT / "viz/public/parts"
parts.mkdir(parents=True, exist_ok=True)
for name in ["L3_comp3_5", "L3_iid_7", "L4_len_44", "L3_iid_37"]:
    im = Image.open(ROOT / "runs/cover" / f"{name}.png").convert("RGBA")
    im.crop(im.getchannel("A").getbbox()).save(parts / f"{name}.png")
print("parts ->", parts)
