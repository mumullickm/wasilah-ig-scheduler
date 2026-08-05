"""Wasilah TikTok auto-publisher.

Posts due videos to TikTok from GitHub Actions, the same way run_youtube.py does
for Shorts. State lives in posted_tiktok.json, so a failed or skipped video is
simply retried on the next tick rather than lost.

Secrets: TT_CLIENT_KEY, TT_CLIENT_SECRET, TT_REFRESH_TOKEN.

WHY THIS EXISTS AT ALL, since the old notes said it was impossible. TikTok's
Content Posting API genuinely has no schedule_time parameter — you can only post
now or save a draft. The conclusion drawn from that was that TikTok had to use
its own web scheduler, driven by a browser on Miraz's Mac. That conclusion was
wrong, and it cost months of fighting a virtualised post list and a mouse wheel.
Meta and YouTube do not use platform schedulers either: the GitHub Actions cron
IS the scheduler. The runner wakes at the slot time and posts immediately, so
DIRECT_POST is all that is ever needed and the Mac can be switched off.

SLOTS. 09:00 and 21:00 Asia/Dhaka, twice a day. Measured, not chosen: across
every post published before the 1 Aug 2026 blackout, 21:00 ran n=12 median 212
views and 09:00 n=4 median 287, while 19:00, 20:00, 22:00 and 23:00 all sat at a
median of 1 to 2. On 29 Jul the 09:00 and 21:00 posts took 287 views each on the
same day, which is the direct evidence that two a day at these two hours works.
Generic advice to post 2-3 hours BEFORE the peak so TikTok can test the video is
wrong for this account and was tested: 19:00 and 20:00 posts got nothing.

RATE LIMIT. TikTok's own ceiling is 6 posts/minute and 15/day. At two a day this
is nowhere near it, and MAX_PER_RUN stays at 1 deliberately. A burst of uploads
on 29 Jul 2026 put ~25 videos out in three hours and every one of them died at
0-4 views while an on-slot post the same evening took 287. Do not raise this to
drain a backlog.
"""
import datetime, json, os, sys, time, urllib.error, urllib.parse, urllib.request

API = "https://open.tiktokapis.com/v2"
TOKEN_URL = f"{API}/oauth/token/"
CREATOR_URL = f"{API}/post/publish/creator_info/query/"
INIT_URL = f"{API}/post/publish/video/init/"
STATUS_URL = f"{API}/post/publish/status/fetch/"

QUEUE = "tiktok.json"
LEDGER = "posted_tiktok.json"
MAX_PER_RUN = int(os.environ.get("TT_MAX_PER_RUN", "1"))
# 64 MB is TikTok's max chunk. Every file in this queue is far below it, so each
# upload is a single chunk and the multi-chunk path is deliberately not built.
CHUNK_LIMIT = 64 * 1024 * 1024
DHAKA = datetime.timezone(datetime.timedelta(hours=6))


def post_json(url, payload, token=None, timeout=60):
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def access_token():
    body = urllib.parse.urlencode({
        "client_key": os.environ["TT_CLIENT_KEY"],
        "client_secret": os.environ["TT_CLIENT_SECRET"],
        "grant_type": "refresh_token",
        "refresh_token": os.environ["TT_REFRESH_TOKEN"],
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    if "access_token" not in d:
        raise SystemExit(f"token refresh failed: {d}")
    return d["access_token"]


def allowed_privacy(token):
    """TikTok rejects a post whose privacy_level it did not offer for this creator.

    An app that has not passed TikTok's content-posting audit is capped at
    SELF_ONLY, and the failure arrives as a rejected publish rather than a clear
    error, so read the offered list and fail loudly here instead.
    """
    d = post_json(CREATOR_URL, {}, token)
    opts = (d.get("data") or {}).get("privacy_level_options") or []
    if not opts:
        raise SystemExit(f"creator_info returned no privacy options: {d}")
    return opts


def fetch_video(url):
    with urllib.request.urlopen(url, timeout=300) as r:
        data = r.read()
    if len(data) < 10000:
        raise RuntimeError(f"{url} returned only {len(data)} bytes")
    if len(data) > CHUNK_LIMIT:
        raise RuntimeError(f"{url} is {len(data)} bytes, over the single-chunk limit")
    return data


def publish(token, entry, privacy):
    video = fetch_video(entry["video"])
    init = post_json(INIT_URL, {
        "post_info": {
            "title": entry["caption"][:2200],
            "privacy_level": privacy,
            "disable_comment": False,
            "disable_duet": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": len(video),
            "chunk_size": len(video),
            "total_chunk_count": 1,
        },
    }, token)
    data = init.get("data") or {}
    publish_id, upload_url = data.get("publish_id"), data.get("upload_url")
    if not (publish_id and upload_url):
        raise RuntimeError(f"init failed: {init}")

    put = urllib.request.Request(upload_url, data=video, method="PUT", headers={
        "Content-Type": "video/mp4",
        "Content-Length": str(len(video)),
        "Content-Range": f"bytes 0-{len(video) - 1}/{len(video)}",
    })
    with urllib.request.urlopen(put, timeout=600) as r:
        if r.status not in (200, 201, 202):
            raise RuntimeError(f"upload returned HTTP {r.status}")

    # The upload returning 200 only means TikTok took the bytes. It still rejects
    # videos asynchronously afterwards, so a run that stops here would record a
    # success for a post that never appears. Poll until it actually publishes.
    for _ in range(20):
        time.sleep(15)
        st = post_json(STATUS_URL, {"publish_id": publish_id}, token)
        status = ((st.get("data") or {}).get("status") or "").upper()
        if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            return publish_id
        if status == "FAILED":
            raise RuntimeError(f"TikTok rejected it: {st}")
    raise RuntimeError(f"still processing after 5 minutes, publish_id={publish_id}")


def main():
    queue = json.load(open(QUEUE, encoding="utf-8"))
    ledger = json.load(open(LEDGER, encoding="utf-8")) if os.path.exists(LEDGER) else {}
    now = datetime.datetime.now(DHAKA)

    due = [e for e in queue
           if e["slug"] not in ledger
           and datetime.datetime.fromisoformat(e["iso"]).astimezone(DHAKA) <= now]
    due.sort(key=lambda e: e["iso"])
    if not due:
        print("nothing due")
        return

    print(f"{len(due)} due, posting at most {MAX_PER_RUN}")
    if len(due) > MAX_PER_RUN:
        # Never let a backlog drain silently. A quiet catch-up burst is exactly
        # what killed ~25 posts on 29 Jul 2026.
        print(f"DEFERRED to later ticks: {[e['slug'] for e in due[MAX_PER_RUN:]]}")

    token = access_token()
    privacy = allowed_privacy(token)
    want = "PUBLIC_TO_EVERYONE"
    if want not in privacy:
        raise SystemExit(
            f"TikTok will not accept a public post for this app yet (offered: {privacy}). "
            "That means the content-posting audit has not been approved, so every post "
            "would land private. Stopping rather than publishing invisibly.")

    failed = 0
    for entry in due[:MAX_PER_RUN]:
        try:
            pid = publish(token, entry, want)
            ledger[entry["slug"]] = pid
            json.dump(ledger, open(LEDGER, "w"), indent=1, ensure_ascii=False)
            print(f"published {entry['slug']} -> {pid}")
        except Exception as exc:
            failed += 1
            print(f"FAILED {entry['slug']}: {exc}", file=sys.stderr)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
