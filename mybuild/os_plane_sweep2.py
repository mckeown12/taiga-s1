"""Wide sweep for the Front/Right origin-plane short IDs, then cleanup of all
probe sketches (OK and ERROR) from the hook studio.

Usage: python os_plane_sweep2.py [start_v end_v]
Default: 73600 73854
"""
import json, os, sys
import osapi as o
from os_arc_test import (DOC, WS, b62, b62v, eid, conf, mk_feature,
                         delete_feature, status_of, sketch_body, line_entity)

def sketches_map(ps):
    s, _, b = o.get(f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/sketches")
    if s != 200:
        return {}
    if isinstance(b, str):
        b = json.loads(b)
    sks = b if isinstance(b, list) else b.get("sketches", [])
    out = {}
    for sk in sks:
        tm = sk.get("transformMatrix") or []
        mat = None
        if len(tm) >= 12:
            mat = [[tm[i * 4 + j] for j in range(4)] for i in range(4)]
        out[sk.get("featureId")] = {
            "name": sk.get("name"), "featureId": sk.get("featureId"),
            "matrix": mat,
        }
    return out

def classify(mat):
    if not mat:
        return None
    lx = [mat[0][0], mat[1][0], mat[2][0]]
    ly = [mat[0][1], mat[1][1], mat[2][1]]
    n = [mat[0][2], mat[1][2], mat[2][2]]
    kind = ("Top" if abs(abs(n[2]) - 1) < 1e-6 else
            "Front" if abs(abs(n[1]) - 1) < 1e-6 else
            "Right" if abs(abs(n[0]) - 1) < 1e-6 else "?")
    return {"kind": kind,
            "x": [round(c, 6) for c in lx],
            "y": [round(c, 6) for c in ly],
            "normal": [round(c, 6) for c in n]}

def main():
    args = [int(a) for a in sys.argv[1:3]] if len(sys.argv) >= 3 else [73600, 73854]
    lo, hi = args
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "ons")
    os.makedirs(outdir, exist_ok=True)
    state = json.load(open(os.path.join(outdir, "state.json"))) if os.path.exists(os.path.join(outdir, "state.json")) else {}
    ps = state.get("hook_ps")
    assert ps, "run os_arc_test.py first to create/find the hook studio"
    state.setdefault("planes", {})
    probes = state.get("sweep_probes", {})

    # rescan existing probe sketches from earlier runs (ERROR ones were not deleted)
    sm = sketches_map(ps)
    for fid, sk in sm.items():
        if (sk.get("name") or "").startswith("probe"):
            probes[fid] = sk.get("name")
    # also pick up ERROR probe sketches from THIS run as we go
    done = state.get("sweep_done", set()) if isinstance(state.get("sweep_done"), list) else set()

    v = lo
    while v <= hi:
        cid = b62(v)
        if cid == "JDC" or cid in state.get("planes", {}):
            v += 1
            continue
        if str(v) in done:
            v += 1
            continue
        body = sketch_body(f"probe{cid}", cid, [line_entity((0.0, 0.0), (1.0, 0.0))])
        s, b2 = mk_feature(ps, body)
        fid, st = status_of(b2)
        tag = ""
        if s == 200 and st == "OK" and fid:
            sk = sketches_map(ps).get(fid)
            cls = classify(sk.get("matrix")) if sk else None
            if cls:
                state["planes"][cid] = cls
                tag = f"  >>> {cls['kind']}  x={cls['x']} y={cls['y']} n={cls['normal']}"
                print(f"[{v}] {cid}: PLANE {cls['kind']}", flush=True)
                json.dump(state, open(os.path.join(outdir, "state.json"), "w"), indent=1)
            probes[fid] = f"probe{cid}"
            delete_feature(ps, fid)
        else:
            if fid:
                probes[fid] = f"probe{cid}"
        print(f"  {cid} (v={v}): {s} {st or ''}{tag}", flush=True)
        done.add(str(v))
        state["sweep_done"] = list(done)
        v += 1

    # cleanup: delete every remaining probe sketch (ERROR state included)
    print("\n=== cleanup of probe sketches ===")
    sm = sketches_map(ps)
    n_del = 0
    for fid, sk in sm.items():
        if (sk.get("name") or "").startswith("probe"):
            s, b = delete_feature(ps, fid)
            n_del += 1
            if s not in (200, 202):
                print(f"  delete {fid} ({sk.get('name')}): {s} {str(b)[:80]}")
    print(f"deleted {n_del} probe sketches")
    state["sweep_probes"] = {}
    json.dump(state, open(os.path.join(outdir, "state.json"), "w"), indent=1)
    print("\nplanes:", json.dumps(state["planes"], indent=1))

if __name__ == "__main__":
    main()
