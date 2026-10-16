"""One-off promo publisher: IG Reel + IG Story + FB Reel + FB Story + YouTube Short.
Manual only (publish-promo.yml). Idempotent per target via posted_promo.json."""
import json, os, time, urllib.error, urllib.parse, urllib.request

GRAPH = "https://graph.facebook.com/v21.0"
CFG = json.load(open("config.json"))
PROMO = json.load(open("promo.json", encoding="utf-8"))
STATE_FILE = "posted_promo.json"
TARGETS = [t.strip() for t in os.environ.get("PROMO_TARGETS", "ig_reel,ig_story,fb_reel,fb_story,youtube").split(",") if t.strip()]


def _get(path, params=None):
    p = dict(params or {}); p["access_token"] = os.environ["META_PAGE_TOKEN"]
    return json.loads(urllib.request.urlopen(f"{GRAPH}/{path}?" + urllib.parse.urlencode(p), timeout=30).read())


def _post(path, params, timeout=180):
    p = dict(params); p["access_token"] = os.environ["META_PAGE_TOKEN"]
    req = urllib.request.Request(f"{GRAPH}/{path}", data=urllib.parse.urlencode(p).encode(), method="POST")
    try:
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except urllib.error.HTTPError as e:
        return {"_error": json.loads(e.read().decode()).get("error", {})}


def ig_user_id():
    if CFG.get("igUserId"):
        return CFG["igUserId"]
    return _get("me", {"fields": "instagram_business_account"}).get("instagram_business_account", {}).get("id")


def ig_publish(ig, params):
    cont = _post(f"{ig}/media", params)
    if "id" not in cont:
        return False, f"IG container error {cont.get('_error')}"
    cid = cont["id"]
    for _ in range(40):
        st = _get(cid, {"fields": "status_code"}).get("status_code")
        if st == "FINISHED": break
        if st == "ERROR": return False, "IG container ERROR"
        time.sleep(15)
    pub = _post(f"{ig}/media_publish", {"creation_id": cid})
    return ("id" in pub), (pub.get("id") or f"IG publish error {str(pub.get('_error'))[:160]}")


def fb_hosted(page_id, edge, url, finish):
    start = _post(f"{page_id}/{edge}", {"upload_phase": "start"})
    vid, up = start.get("video_id"), start.get("upload_url")
    if not (vid and up):
        return False, f"FB {edge} start error {start.get('_error')}"
    req = urllib.request.Request(up, data=b"", method="POST",
                                 headers={"Authorization": f"OAuth {os.environ['META_PAGE_TOKEN']}", "file_url": url})
    try:
        urllib.request.urlopen(req, timeout=180).read()
    except urllib.error.HTTPError as e:
        return False, f"FB {edge} upload error {e.read()[:160].decode(errors='replace')}"
    fin = _post(f"{page_id}/{edge}", dict(finish, upload_phase="finish", video_id=vid))
    ok = fin.get("success") or fin.get("post_id") or fin.get("id")
    return bool(ok), (str(fin.get("post_id") or vid) if ok else f"FB {edge} finish error {fin.get('_error')}")


def youtube():
    data = urllib.parse.urlencode({"client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
                                   "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}).encode()
    token = json.loads(urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST"), timeout=30).read())["access_token"]
    blob = urllib.request.urlopen(PROMO["video916"], timeout=180).read()
    meta = {"snippet": {"title": PROMO["youtubeTitle"], "description": PROMO["caption"], "tags": PROMO["tags"],
                        "categoryId": "22", "defaultLanguage": "bn", "defaultAudioLanguage": "bn"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    req = urllib.request.Request("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                                 data=json.dumps(meta).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                                          "X-Upload-Content-Length": str(len(blob)), "X-Upload-Content-Type": "video/mp4"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            session = r.headers.get("Location")
        put = urllib.request.Request(session, data=blob, method="PUT", headers={"Content-Type": "video/mp4", "Content-Length": str(len(blob))})
        with urllib.request.urlopen(put, timeout=600) as r:
            vid = json.loads(r.read()).get("id")
    except urllib.error.HTTPError as e:
        return False, f"YouTube error {e.code}: {e.read()[:200].decode(errors='replace')}"
    return bool(vid), vid or "no video id"


def main():
    state = json.load(open(STATE_FILE)) if os.path.exists(STATE_FILE) else {}
    done = state.setdefault(PROMO["id"], {})
    page_id = ig = None
    if any(t.startswith(("ig_", "fb_")) for t in TARGETS):
        page_id = _get("me").get("id"); ig = ig_user_id()
    jobs = {
        "ig_reel": lambda: ig_publish(ig, {"media_type": "REELS", "video_url": PROMO["video45"], "caption": PROMO["caption"], "share_to_feed": "true"}),
        "ig_story": lambda: ig_publish(ig, {"media_type": "STORIES", "video_url": PROMO["video916"]}),
        "fb_reel": lambda: fb_hosted(page_id, "video_reels", PROMO["video45"], {"video_state": "PUBLISHED", "description": PROMO["caption"]}),
        "fb_story": lambda: fb_hosted(page_id, "video_stories", PROMO["video916"], {}),
        "youtube": youtube,
    }
    failed = False
    for t in TARGETS:
        if done.get(t):
            print(f"{t}: already posted ({done[t]})"); continue
        ok, info = jobs[t]()
        print(f"{t}: {'OK' if ok else 'FAILED'} {info}")
        if ok: done[t] = info
        else: failed = True
        json.dump(state, open(STATE_FILE, "w"), ensure_ascii=False, indent=2)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
