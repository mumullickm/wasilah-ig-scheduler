"""Delete one already-published surah post and post it again.

Only reason this exists: a published Facebook link post keeps whatever card
Facebook rendered at publish time. A re-scrape moves the cache for future posts
but does not touch a live one, so a card fixed after publication can only reach
that post by replacing it.

Destructive and deliberately narrow. It takes one slug, refuses anything the
ledger does not already hold as published, prints the old post's details before
removing it, and rewrites the ledger so the queue stays honest.

Secrets: META_PAGE_TOKEN.  Env: SLUG.
"""
import hashlib, json, os, sys, urllib.error, urllib.parse, urllib.request

GRAPH = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["META_PAGE_TOKEN"]
SLUG = os.environ["SLUG"]


def _call(path, params, method):
    p = dict(params); p["access_token"] = TOKEN
    data = urllib.parse.urlencode(p).encode() if method == "POST" else None
    url = f"{GRAPH}/{path}" + ("?" + urllib.parse.urlencode(p) if method != "POST" else "")
    try:
        return json.loads(urllib.request.urlopen(
            urllib.request.Request(url, data=data, method=method), timeout=60).read())
    except urllib.error.HTTPError as e:
        return {"_error": json.loads(e.read().decode()).get("error", {})}


def main():
    sched = {s["slug"]: s for s in json.load(open("surahs.json"))}
    state = json.load(open("posted_surahs.json"))
    sync = json.load(open("surahs_synced.json"))

    item = sched.get(SLUG)
    old = state.get(SLUG)
    if not item or not isinstance(old, str):
        sys.exit(f"{SLUG} is not a published post in the ledger")

    before = _call(old, {"fields": "is_published,created_time,permalink_url"}, "GET")
    print("replacing:", json.dumps(before, indent=1))
    if before.get("is_published") is not True:
        sys.exit("that post is not published, edit it in place instead of replacing it")

    d = _call(old, {}, "DELETE")
    if "_error" in d:
        sys.exit(f"delete failed: {d['_error']}")
    print("deleted", old)

    page_id = _call("me", {}, "GET").get("id")
    r = _call(f"{page_id}/feed", {"message": item["message"], "link": item["link"]}, "POST")
    new = r.get("id") or r.get("post_id")
    if not new:
        sys.exit(f"repost failed after the delete: {r.get('_error')}")
    print("posted", new)

    state[SLUG] = str(new)
    sync[SLUG] = hashlib.sha256(
        (item["message"] + "|" + item["iso"] + "|" + item["link"]).encode()).hexdigest()[:16]
    json.dump(state, open("posted_surahs.json", "w"), ensure_ascii=False, indent=2)
    json.dump(sync, open("surahs_synced.json", "w"), ensure_ascii=False, indent=2)
    print(_call(str(new), {"fields": "permalink_url,full_picture"}, "GET"))


if __name__ == "__main__":
    main()
