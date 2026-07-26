"""Wasilah blog-link publisher: Facebook Page link posts, natively scheduled.

Facebook only, by design. These carry a URL to a wasilah.site article and
Instagram captions cannot hold a clickable link, so cross-posting them would
be noise. The Page renders the article's own og:image as the link card, which
is why each article has its own card rather than one shared image.

Unlike the statics/reels publishers, this does NOT wait for the cron to reach
the post time. It hands each post to Facebook's own scheduler with
scheduled_publish_time, so publication happens at the exact minute even if a
runner is late or skipped, and the queue is visible in Business Suite's
Scheduled tab. The cron is only a safety net that registers anything not yet
handed over.

Secret: META_PAGE_TOKEN.
"""
import datetime, json, os, urllib.error, urllib.parse, urllib.request

GRAPH = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["META_PAGE_TOKEN"]
CFG = json.load(open("config.json"))

SCHEDULE = "links.json"
STATE = "posted_links.json"

# Facebook rejects scheduled_publish_time under 10 minutes out; keep margin.
MIN_LEAD = datetime.timedelta(minutes=15)


def _get(path, params=None):
    p = dict(params or {}); p["access_token"] = TOKEN
    return json.loads(urllib.request.urlopen(
        f"{GRAPH}/{path}?" + urllib.parse.urlencode(p), timeout=30).read())


def _post(path, params, timeout=120):
    p = dict(params); p["access_token"] = TOKEN
    req = urllib.request.Request(f"{GRAPH}/{path}",
                                 data=urllib.parse.urlencode(p).encode(), method="POST")
    try:
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except urllib.error.HTTPError as e:
        return {"_error": json.loads(e.read().decode()).get("error", {})}


def publish_fb_link(page_id, item, when=None):
    """POST /{page}/feed with message + link. Facebook scrapes the URL and
    attaches the og card itself, so no media upload is involved.

    With `when`, the post is handed to Facebook's scheduler rather than
    published now: published=false plus a unix scheduled_publish_time."""
    params = {"message": item["message"], "link": item["link"]}
    if when is not None:
        params["published"] = "false"
        params["scheduled_publish_time"] = str(int(when.timestamp()))
    r = _post(f"{page_id}/feed", params)
    ok = r.get("id") or r.get("post_id")
    return bool(ok), (str(r.get("post_id") or r.get("id")) if ok
                      else f"FB link error {r.get('_error')}")


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sched = json.load(open(SCHEDULE))
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    now = datetime.datetime.now(datetime.timezone.utc)
    page_id = _get("me").get("id")

    pending = [s for s in sched if not state.get(s["slug"])]
    if not pending:
        print(f"[{stamp}] no links pending")
        return

    for s in pending:
        when = datetime.datetime.fromisoformat(s["iso"].replace("Z", "+00:00"))
        if when > now + MIN_LEAD:
            ok, info = publish_fb_link(page_id, s, when=when)
            verb = f"scheduled for {s['iso']}"
        else:
            # already due, or too close for Facebook to accept a schedule
            ok, info = publish_fb_link(page_id, s)
            verb = "published now"
        state[s["slug"]] = info if ok else False
        print(f"[{stamp}] FB link {s['slug']}: {verb + ' ' + info if ok else info}")

    json.dump(state, open(STATE, "w"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
