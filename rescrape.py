"""Force Facebook to re-fetch the og:image behind the surah links.

Facebook caches what it scraped off a URL the first time it saw it. The surah
cards were re-rendered on the video side after some posts were already
registered, so without this the Page would keep serving the old card.

POST /?id=<url>&scrape=true refetches one URL. Only the links that have not
published yet are worth refetching, so this walks the ledger and skips the rest.

Secret: META_PAGE_TOKEN.
"""
import datetime, json, os, urllib.error, urllib.parse, urllib.request

GRAPH = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["META_PAGE_TOKEN"]


def _post(path, params, timeout=120):
    p = dict(params); p["access_token"] = TOKEN
    req = urllib.request.Request(f"{GRAPH}/{path}",
                                 data=urllib.parse.urlencode(p).encode(), method="POST")
    try:
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except urllib.error.HTTPError as e:
        return {"_error": json.loads(e.read().decode()).get("error", {})}


def main():
    one = os.environ.get("SCRAPE_URL")
    if one:
        # A published post keeps whatever Facebook rendered at publish time, so
        # this refetch may or may not reach it. Worth one try before concluding
        # the post is stuck with an old card.
        r = _post("", {"id": one, "scrape": "true"})
        print(json.dumps(r, indent=1)[:800])
        return

    sched = json.load(open("surahs.json"))
    now = datetime.datetime.now(datetime.timezone.utc)
    done = 0
    for s in sched:
        when = datetime.datetime.fromisoformat(s["iso"].replace("Z", "+00:00"))
        if when <= now:
            continue  # already out, its attachment is fixed
        r = _post("", {"id": s["link"], "scrape": "true"})
        if "_error" in r:
            print(f"{s['slug']}: {r['_error'].get('message')}")
            continue
        img = (r.get("image") or [{}])[0].get("url", "")
        print(f"{s['slug']}: {r.get('title','')[:48]} | {img[:70]}")
        done += 1
    print(f"\n{done} urls refetched")


if __name__ == "__main__":
    main()
