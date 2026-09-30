"""Export the OnShape J-hook part studio as STL.

Flow: POST /documents/d/{doc}/w/{ws}/e/{ps}/export (202 + modelexport href)
-> GET href (fresh HMAC for the cad-usw2 host+path+query) -> 302 -> download.
"""
import json, sys
from urllib.parse import urlsplit, parse_qsl
import osapi as o
from os_arc_test import DOC, WS

STATE = "out/ons/state.json"
OUT = "out/ons/hook_onshape.stl"


def get_signed(sess, url):
    sp = urlsplit(url)
    q = dict(parse_qsl(sp.query)) or None
    hdrs = o._sign("GET", sp.path, q, o.CT_READ)
    return sess.get(url, headers=hdrs, timeout=300, allow_redirects=False)


def main():
    state = json.load(open(STATE))
    ps = state["final_ps"]
    import requests
    sess = requests.Session()

    path = f"/api/documents/d/{DOC}/w/{WS}/e/{ps}/export"
    ctype = "application/json;charset=UTF-8; qs=0.09"
    body = json.dumps({"format": "stl", "elementId": ps, "documentId": DOC})
    hdrs = o._sign("POST", path, None, ctype)
    r = sess.post(o.BASE + path, data=body, headers=hdrs, timeout=120)
    print("export request:", r.status_code, r.text[:300])
    if r.status_code not in (200, 202):
        sys.exit(1)
    href = (r.json() or {}).get("href")
    if not href:
        sys.exit("no href")

    import time
    data = None
    for attempt in range(24):
        r = get_signed(sess, href)
        if r.status_code == 200:
            data = r.content
            break
        if r.status_code in (301, 302):
            loc = r.headers.get("Location")
            url = loc if loc.startswith("http") else f"https://{urlsplit(href).netloc}{loc}"
            r = get_signed(sess, url)
            if r.status_code in (301, 302):
                loc2 = r.headers.get("Location")
                sp2 = urlsplit(loc2 if loc2.startswith("http") else url.rsplit("/", 1)[0] + loc2)
                r = get_signed(sess, sp2.geturl())
            if r.status_code == 200:
                data = r.content
                break
            print("redirect poll:", r.status_code, r.text[:200])
        else:
            print("poll:", r.status_code, r.text[:200])
        time.sleep(5)
    if data is None:
        sys.exit("export timeout")
    with open(OUT, "wb") as f:
        f.write(data)
    print("saved:", OUT, len(data), "bytes")


if __name__ == "__main__":
    main()
