#!/usr/bin/env python3
"""One-off: set a custom thumbnail on every reel already published to YouTube.

run_youtube.py never set one before 2026-09-05, so 64 uploads carry an
auto-grabbed frame. This walks posted_youtube.json and fixes them in place.
The video, its URL, views and comments are all untouched; only the still
changes.

Reads the JPGs from the local render (wasilah-social/cards/out-thumbs) so it
does not wait on GitHub Pages. Resumable: state in thumbs_set.json, so a
quota stop or a network drop just means running it again.

    python3 backfill_thumbs.py           # everything outstanding
    python3 backfill_thumbs.py --limit 20

Quota: thumbnails.set costs 50 units each against 10,000/day. 64 is 3,200,
which coexists with the day's two 1,600-unit uploads. --limit is there for the
days it does not.
"""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

HOME = os.path.expanduser("~")
THUMBS = os.path.join(HOME, "Desktop/App Building/Claude Code/Wasilah",
                      "wasilah-social/cards/out-thumbs")
STATE = "thumbs_set.json"
SET_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"


def rd(name):
    with open(os.path.join(HOME, name)) as f:
        return f.read().strip()


def access_token():
    data = urllib.parse.urlencode({
        "client_id": os.environ.get("YT_CLIENT_ID") or rd(".wasilah_youtube_client_id"),
        "client_secret": os.environ.get("YT_CLIENT_SECRET") or rd(".wasilah_youtube_client_secret"),
        "refresh_token": os.environ.get("YT_REFRESH_TOKEN") or rd(".wasilah_youtube_refresh_token"),
        "grant_type": "refresh_token",
    }).encode()
    return json.load(urllib.request.urlopen(TOKEN_URL, data))["access_token"]


TOKEN_URL = "https://oauth2.googleapis.com/token"


def asset_id(rid):
    m = re.fullmatch(r"(.+?)c\d+", rid)
    return m.group(1) if m else rid


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    posted = json.load(open("posted_youtube.json"))
    done = json.load(open(STATE)) if os.path.exists(STATE) else {}
    todo = [(slug, vid) for slug, vid in posted.items()
            if isinstance(vid, str) and slug not in done]
    if limit:
        todo = todo[:limit]
    print(f"{len(todo)} to set, {len(done)} already done")

    token = access_token()
    ok = fail = 0
    for slug, vid in todo:
        path = os.path.join(THUMBS, f"{asset_id(slug)}.jpg")
        if not os.path.exists(path):
            print(f"  {slug}: no thumbnail rendered, skipped")
            fail += 1
            continue
        img = open(path, "rb").read()
        req = urllib.request.Request(
            f"{SET_URL}?videoId={vid}", data=img, method="POST",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "image/jpeg",
                     "Content-Length": str(len(img))})
        for attempt in range(3):
            try:
                urllib.request.urlopen(req, timeout=120).read()
                done[slug] = vid
                json.dump(done, open(STATE, "w"), indent=2, sort_keys=True)
                print(f"  {slug} -> {vid}")
                ok += 1
                break
            except urllib.error.HTTPError as e:
                body = e.read()[:140].decode(errors="replace")
                if attempt == 2:
                    print(f"  {slug}: HTTP {e.code} {body}")
                    fail += 1
                # quotaExceeded is terminal for the day, stop rather than burn retries
                if e.code == 403 and "quota" in body.lower():
                    print("  quota exhausted, stopping. Run again tomorrow.")
                    print(f"\n{ok} set, {fail} failed")
                    return
                time.sleep(4)
            except Exception as e:
                if attempt == 2:
                    print(f"  {slug}: {e}")
                    fail += 1
                time.sleep(4)
        time.sleep(0.6)
    print(f"\n{ok} set, {fail} failed")


if __name__ == "__main__":
    main()
