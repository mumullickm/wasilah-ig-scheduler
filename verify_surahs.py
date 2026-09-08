"""Read back what the Wasilah Page actually holds for the surah series.

The ledger records what the API answered. This asks Facebook what is really
sitting in its scheduler: the caption, the minute, and whether it has published
yet. Anything that does not match surahs.json is printed and the run exits
non-zero, so a silent drift shows up red instead of green.

Secret: META_PAGE_TOKEN.
"""
import datetime, json, os, sys, urllib.error, urllib.parse, urllib.request

GRAPH = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["META_PAGE_TOKEN"]
BD = datetime.timezone(datetime.timedelta(hours=6))


def _get(path, params):
    p = dict(params); p["access_token"] = TOKEN
    try:
        return json.loads(urllib.request.urlopen(
            f"{GRAPH}/{path}?" + urllib.parse.urlencode(p), timeout=30).read())
    except urllib.error.HTTPError as e:
        return {"_error": json.loads(e.read().decode()).get("error", {})}


def main():
    want = {s["slug"]: s for s in json.load(open("surahs.json"))}
    state = json.load(open("posted_surahs.json"))
    bad = 0
    for slug, pid in sorted(state.items()):
        if not isinstance(pid, str):
            print(f"{slug}: ledger says failed"); bad += 1; continue
        r = _get(pid, {"fields": "message,scheduled_publish_time,is_published,created_time"})
        if "_error" in r:
            print(f"{slug}: {r['_error'].get('message')}"); bad += 1; continue
        w = want[slug]
        msg_ok = r.get("message") == w["message"]
        t = r.get("scheduled_publish_time")
        # A post that has already gone out has no scheduled_publish_time left,
        # so for those the caption is the whole check.
        if r.get("is_published"):
            when_ok = True
        else:
            when_ok = (t is not None and
                       datetime.datetime.fromtimestamp(int(t), datetime.timezone.utc)
                       == datetime.datetime.fromisoformat(w["iso"].replace("Z", "+00:00")))
        local = (datetime.datetime.fromtimestamp(int(t), BD).strftime("%Y-%m-%d %H:%M BD")
                 if t else datetime.datetime.fromisoformat(
                     r.get("created_time", "").replace("+0000", "+00:00")
                 ).astimezone(BD).strftime("%Y-%m-%d %H:%M BD, live"))
        flag = "ok " if (msg_ok and when_ok) else "BAD"
        if flag == "BAD":
            bad += 1
            if not msg_ok:
                print(f"  caption differs for {slug}")
            if not when_ok:
                print(f"  time differs for {slug}: page says {local}")
        print(f"{flag} {slug}  {local}  published={r.get('is_published')}")
    print(f"\n{len(state)} checked, {bad} wrong")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
