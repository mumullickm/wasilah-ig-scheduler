"""Read-only: list every Instagram post on the account with permalink, time, caption head
and engagement, into ig_media.json (uploaded as a run artifact, never committed).
Built 2026-10-16 to find the carousel duplicates of 19 Sep to 15 Oct.
"""
import json, os, urllib.parse, urllib.request

GRAPH = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["META_PAGE_TOKEN"]
CFG = json.load(open("config.json"))


def get(path, params):
    p = dict(params); p["access_token"] = TOKEN
    return json.loads(urllib.request.urlopen(f"{GRAPH}/{path}?" + urllib.parse.urlencode(p), timeout=60).read())


ig = CFG["igUserId"]
out, after = [], None
while True:
    p = {"fields": "id,media_type,media_product_type,timestamp,permalink,caption,like_count,comments_count", "limit": 100}
    if after: p["after"] = after
    r = get(f"{ig}/media", p)
    for m in r.get("data", []):
        m["caption"] = (m.get("caption") or "")[:160]
        out.append(m)
    after = r.get("paging", {}).get("cursors", {}).get("after")
    if not r.get("paging", {}).get("next"): break
json.dump(out, open("ig_media.json", "w"), ensure_ascii=False, indent=1)
print(len(out), "posts;", sum(1 for m in out if m["media_type"] == "CAROUSEL_ALBUM"), "carousels")
