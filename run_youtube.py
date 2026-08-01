"""Wasilah YouTube Shorts auto-publisher.

Reuses reels.json / reel_captions.json (same queue as IG + FB) and uploads each
due reel to the Wasilah channel as a Short. Self-healing: state lives in
posted_youtube.json, so a failed or skipped reel is simply retried next run.

Secrets: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.

Quota note: a video insert costs 1600 units against a 10,000/day default, so at
most 6 uploads a day are possible. MAX_PER_RUN caps below that and any deferred
reels are logged explicitly, never dropped silently.
"""
import datetime, json, os, re, ssl, urllib.error, urllib.parse, urllib.request

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = ("https://www.googleapis.com/upload/youtube/v3/videos"
              "?uploadType=resumable&part=snippet,status")
CFG = json.load(open("config.json"))
CAPS = json.load(open("reel_captions.json"))
VIDEO_BASE = CFG["videoBase"]
MAX_PER_RUN = int(os.environ.get("YT_MAX_PER_RUN", "5"))
CATEGORY_ID = "22"          # People & Blogs
PRIVACY = os.environ.get("YT_PRIVACY", "public")


def access_token():
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=30).read())["access_token"]


def asset_id(rid):
    # matches run_reels.asset_id: a cycle suffix reuses the same file
    m = re.fullmatch(r"(.+?)c\d+", rid)
    return m.group(1) if m else rid


def video_url(reel):
    return f"{VIDEO_BASE}/{asset_id(reel)}.mp4"


def title_for(cap):
    """First English sentence, trimmed to a safe length, marked as a Short."""
    first = cap.strip().split("\n")[0]
    sentence = re.split(r"(?<=[.!?…])\s", first)[0]
    t = sentence.strip().strip(".… ").replace("<", "").replace(">", "")
    if len(t) > 80:
        t = t[:77].rsplit(" ", 1)[0] + "..."
    return f"{t} #Shorts"


def tags_for(cap):
    return re.findall(r"#(\w+)", cap)[:15]


def fetch_video(reel):
    url = video_url(reel)
    with urllib.request.urlopen(url, timeout=180) as r:
        if r.status != 200:
            raise RuntimeError(f"asset fetch {r.status} for {url}")
        return r.read()


def upload(token, reel, blob):
    cap = CAPS[reel]
    meta = {
        "snippet": {
            "title": title_for(cap),
            "description": cap,
            "tags": tags_for(cap),
            "categoryId": CATEGORY_ID,
        },
        "status": {
            "privacyStatus": PRIVACY,
            "selfDeclaredMadeForKids": False,
        },
    }
    # Step 1: open a resumable session.
    req = urllib.request.Request(
        UPLOAD_URL, data=json.dumps(meta).encode(), method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(len(blob)),
            "X-Upload-Content-Type": "video/mp4",
        })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            session = r.headers.get("Location")
    except urllib.error.HTTPError as e:
        return False, f"session error {e.code}: {e.read()[:200].decode(errors='replace')}"
    if not session:
        return False, "no resumable session URL returned"

    # Step 2: send the bytes in one PUT (reels are single-digit MB).
    put = urllib.request.Request(
        session, data=blob, method="PUT",
        headers={"Content-Type": "video/mp4", "Content-Length": str(len(blob))})
    try:
        with urllib.request.urlopen(put, timeout=600) as r:
            res = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return False, f"upload error {e.code}: {e.read()[:200].decode(errors='replace')}"
    vid = res.get("id")
    if not vid:
        return False, f"no video id in response: {str(res)[:200]}"
    return True, vid


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    reels = json.load(open("reels.json"))
    state = json.load(open("posted_youtube.json")) if os.path.exists("posted_youtube.json") else {}
    now = datetime.datetime.now(datetime.timezone.utc)

    due = [r for r in reels
           if datetime.datetime.fromisoformat(r["iso"].replace("Z", "+00:00")) <= now
           and not state.get(r["reel"])]
    if not due:
        print(f"[{stamp}] no YouTube uploads due")
        return

    batch, deferred = due[:MAX_PER_RUN], due[MAX_PER_RUN:]
    if deferred:
        print(f"[{stamp}] quota cap: uploading {len(batch)}, deferring "
              f"{len(deferred)} to later runs ({', '.join(r['reel'] for r in deferred[:8])}"
              f"{'...' if len(deferred) > 8 else ''})")

    token = access_token()
    for r in batch:
        reel = r["reel"]
        if reel not in CAPS:
            print(f"[{stamp}] YT {reel}: no caption, skipped")
            continue
        try:
            blob = fetch_video(reel)
        except Exception as e:
            print(f"[{stamp}] YT {reel}: asset fetch failed, {e}")
            continue
        ok, info = upload(token, reel, blob)
        if ok:
            state[reel] = info
            print(f"[{stamp}] YT {reel}: published https://youtu.be/{info}")
        else:
            print(f"[{stamp}] YT {reel}: {info}")

    json.dump(state, open("posted_youtube.json", "w"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
