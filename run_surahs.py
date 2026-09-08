"""Wasilah Qur'an series publisher: one Facebook link post per surah, 1 to 114.

Same transport as run_links.py (POST /{page}/feed with message + link, handed
to Facebook's own scheduler), so publication happens at the exact minute even
if a runner is late. Facebook scrapes the YouTube URL and renders its og:image,
which is the surah's own 1280x720 card, so no media is uploaded from here.

Facebook only. Instagram captions cannot carry a clickable link.

Difference from run_links.py: a rolling HORIZON. The whole 114-day series is
never handed over at once, because a Page has a ceiling on how many posts can
sit scheduled. Each run registers only what falls due inside the window, and
the daily cron walks the window forward. Anything already handed over is in the
ledger and is never sent twice.

Secret: META_PAGE_TOKEN.
"""
import datetime, json, os, urllib.error, urllib.parse, urllib.request

GRAPH = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["META_PAGE_TOKEN"]

SCHEDULE = "surahs.json"
STATE = "posted_surahs.json"

HORIZON = datetime.timedelta(days=25)
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

    pending = []
    for s in sched:
        if state.get(s["slug"]):
            continue
        when = datetime.datetime.fromisoformat(s["iso"].replace("Z", "+00:00"))
        if when > now + HORIZON:
            continue
        pending.append((s, when))

    if not pending:
        print(f"[{stamp}] no surah posts due inside the {HORIZON.days}-day window")
        return

    for s, when in pending:
        if when > now + MIN_LEAD:
            ok, info = publish_fb_link(page_id, s, when=when)
            verb = f"scheduled for {s['iso']}"
        else:
            # already due, or too close for Facebook to accept a schedule
            ok, info = publish_fb_link(page_id, s)
            verb = "published now"
        state[s["slug"]] = info if ok else False
        print(f"[{stamp}] FB {s['slug']}: {verb + ' ' + info if ok else info}")
        if not ok:
            # A cap or token failure will hit every remaining item the same way.
            # Stop, keep what succeeded, let the next daily tick retry.
            print(f"[{stamp}] stopping this run after a failure")
            break

    json.dump(state, open(STATE, "w"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
