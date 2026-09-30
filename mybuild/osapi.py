"""Minimal OnShape REST client using the access_key/secret_key HMAC scheme
(exactly mirrors onshape_client.apikey_headers, minus the broken model layer).

Auth headers per request:
    Date:         RFC1123 UTC
    On-Nonce:     25-char random alnum
    Authorization: On <access_key>:HmacSHA256:<b64(hmac_sha256(secret, string_to_sign))>
string_to_sign = (method\nnonce\ndate\nctype\npath\nquery\n).lower()

Usage:
    from osapi import request, get, post, put, delete as _d
    os, hdr, body = osapi.get("/documents")
"""
import base64, datetime, hashlib, hmac, json, os, random, string, urllib.parse
import requests

BASE = "https://cad.onshape.com"
CREDS_FILE = os.path.expanduser("~/.config/onshape/credentials.json")

_session = None

def _creds():
    with open(CREDS_FILE) as f:
        c = json.load(f)
    return c["access_key"], c["secret_key"]

def _sign(method, path, query, ctype):
    access, secret = _creds()
    date = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    nonce = "".join(random.choice(string.digits + string.ascii_letters) for _ in range(25))
    qs = urllib.parse.urlencode(query or {})
    s2s = f"{method.lower()}\n{nonce}\n{date}\n{ctype}\n{path}\n{qs}\n".lower()
    sig = base64.b64encode(hmac.new(secret.encode(), s2s.encode("utf-8"), hashlib.sha256).digest()).decode()
    return {
        "Date": date,
        "On-Nonce": nonce,
        "Authorization": f"On {access}:HmacSHA256:{sig}",
        "Content-Type": ctype,
    }

CT_READ = "application/json"
CT_WRITE = "application/vnd.onshape.v2+json;charset=utf-8;qs=0.2"  # required for feature writes

def request(method, path, query=None, body=None):
    global _session
    if _session is None:
        _session = requests.Session()
    if not path.startswith("/api"):
        path = "/api" + path
    ctype = CT_WRITE if body is not None else CT_READ
    data = json.dumps(body) if body is not None else None
    full = BASE + path + (("?" + urllib.parse.urlencode(query)) if query else "")
    headers = _sign(method, path, query, ctype)
    if body is not None:
        headers["Accept"] = CT_WRITE  # server rejects writes without this Accept
    r = _session.request(method, full, data=data, headers=headers, timeout=120)
    try:
        parsed = r.json() if r.content and r.headers.get("content-type", "").startswith("application/json") else r.text
    except ValueError:
        parsed = r.text
    return r.status_code, dict(r.headers), parsed

def get(path, query=None):
    return request("GET", path, query)

def post(path, body=None, query=None):
    return request("POST", path, query, body)

def put(path, body=None, query=None):
    return request("PUT", path, query, body)

def delete(path, body=None, query=None):
    return request("DELETE", path, query, body)

if __name__ == "__main__":
    s, h, b = get("/documents")
    print("status:", s)
    print("rate-limit remaining:", h.get("X-Rate-Limit-Remaining"))
    docs = b if isinstance(b, list) else b.get("items", [])
    print("documents:", len(docs))
    for d in docs[:10]:
        print("  -", d.get("name"), d.get("id"))
