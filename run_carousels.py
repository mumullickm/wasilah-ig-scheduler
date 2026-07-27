"""Wasilah carousel auto-publisher: Instagram only, image or video children.

Facebook never receives these. The carousel is the Instagram-only layer, and
mirroring it to the Page would duplicate content already posted there as four
separate statics.

A carousel is a two-step publish that run_statics.py cannot express:
  1. one child container per slide, each flagged is_carousel_item
  2. one parent container of media_type=CAROUSEL holding those child ids
  3. publish the parent

Video children need polling: the container sits in IN_PROGRESS while Instagram
transcodes, and publishing a parent that references an unfinished child fails.

Self-healing like the other publishers: anything due-but-unposted is picked up
on the next run, so a missed cron catches up rather than silently dropping.

Secret: META_PAGE_TOKEN.
"""
import datetime, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

GRAPH = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["META_PAGE_TOKEN"]
CFG = json.load(open("config.json"))
STATIC_BASE = CFG["staticBase"]
VIDEO_BASE = CFG["videoBase"]

STATE = "posted_carousels.json"
MAX_CHILD_WAIT = 300      # seconds to wait for a video child to finish
POLL = 10


def _get(path, params=None):
    p = dict(params or {}); p["access_token"] = TOKEN
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(p)}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def _post(path, params, timeout=180):
    p = dict(params); p["access_token"] = TOKEN
    req = urllib.request.Request(f"{GRAPH}/{path}",
                                 data=urllib.parse.urlencode(p).encode(),
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def ig_user_id():
    return CFG["igUserId"]


def asset_id(aid):
    # matches run_statics.asset_id: a cycle suffix reuses the same creative
    m = re.fullmatch(r"(.+?)c\d+", aid)
    return m.group(1) if m else aid


def image_url(sid): return f"{STATIC_BASE}/{asset_id(sid)}.jpg"


def video_url(vid): return f"{VIDEO_BASE}/{asset_id(vid)}.mp4"


def child(ig, slide, kind):
    """One carousel item container. Returns its id."""
    if kind == "video":
        p = {"media_type": "VIDEO", "video_url": video_url(slide),
             "is_carousel_item": "true"}
    else:
        p = {"image_url": image_url(slide), "is_carousel_item": "true"}
    return _post(f"{ig}/media", p)["id"]


def wait_ready(cid):
    """Video children transcode asynchronously; a parent referencing an
    unfinished child is rejected, so block until FINISHED or give up loudly."""
    deadline = time.time() + MAX_CHILD_WAIT
    while time.time() < deadline:
        st = _get(cid, {"fields": "status_code"}).get("status_code")
        if st == "FINISHED":
            return True
        if st == "ERROR":
            raise RuntimeError(f"child {cid} failed to process")
        time.sleep(POLL)
    raise RuntimeError(f"child {cid} still processing after {MAX_CHILD_WAIT}s")


def publish(ig, car, caption):
    kids = []
    for slide in car["slides"]:
        cid = child(ig, slide, car["kind"])
        kids.append(cid)
    if car["kind"] == "video":
        for cid in kids:
            wait_ready(cid)
    parent = _post(f"{ig}/media", {"media_type": "CAROUSEL",
                                   "children": ",".join(kids),
                                   "caption": caption})["id"]
    if car["kind"] == "video":
        wait_ready(parent)
    return _post(f"{ig}/media_publish", {"creation_id": parent})["id"]


def main():
    cars = json.load(open("carousels.json"))
    caps = json.load(open("carousel_captions.json"))
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    now = datetime.datetime.now(datetime.timezone.utc)
    stamp = now.strftime("%Y-%m-%d %H:%M")

    due = [c for c in cars
           if c["iso"] <= now.strftime("%Y-%m-%dT%H:%M:%SZ")
           and not state.get(c["carousel"], {}).get("ig")]
    if not due:
        print(f"[{stamp}] no carousels due")
        return

    ig = ig_user_id()
    failures = 0
    for c in due:
        cid = c["carousel"]
        try:
            mid = publish(ig, c, caps[cid])
            state.setdefault(cid, {})["ig"] = mid
            print(f"[{stamp}] {cid} -> ig {mid}")
        except urllib.error.HTTPError as e:
            failures += 1
            print(f"[{stamp}] {cid} FAILED {e.code}: {e.read().decode()[:300]}")
        except Exception as e:
            failures += 1
            print(f"[{stamp}] {cid} FAILED: {e}")

    with open(STATE, "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
