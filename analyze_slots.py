"""Which hour actually works on the Wasilah Facebook Page.

Reads the Page's own published history (every id in the posted_* ledgers),
pulls each post's real created_time plus whatever performance data the token is
allowed to see, and groups by Dhaka hour. Manual tool, never on a cron.

Insights (post_impressions_unique, post_engaged_users) need `read_insights` on
the token. If that scope is missing the call fails per-post and the run falls
back to public engagement counts (reactions + comments + shares), which only
need pages_read_engagement. The fallback is a weaker signal but it is real
data from this Page rather than a guess.

Secret: META_PAGE_TOKEN.
"""
import datetime, json, os, statistics, urllib.error, urllib.parse, urllib.request

GRAPH = "https://graph.facebook.com/v21.0"
TOKEN = os.environ["META_PAGE_TOKEN"]
BD = datetime.timezone(datetime.timedelta(hours=6))
LEDGERS = ["posted_statics.json", "posted_reels.json", "posted_links.json"]
FIELDS = ("created_time,shares,"
          "reactions.summary(true).limit(0),comments.summary(true).limit(0),"
          "insights.metric(post_impressions_unique,post_engaged_users)")


def _get(path, params):
    p = dict(params); p["access_token"] = TOKEN
    try:
        return json.loads(urllib.request.urlopen(
            f"{GRAPH}/{path}?" + urllib.parse.urlencode(p), timeout=60).read())
    except urllib.error.HTTPError as e:
        return {"_error": json.loads(e.read().decode()).get("error", {})}


def ids():
    out = []
    for f in LEDGERS:
        if not os.path.exists(f):
            continue
        for slug, pid in json.load(open(f)).items():
            if isinstance(pid, str) and "_" in pid:
                out.append((f, slug, pid))
    return out


def main():
    rows, denied, missing = [], 0, 0
    batch = ids()
    print(f"{len(batch)} post ids across {len(LEDGERS)} ledgers")

    for i in range(0, len(batch), 25):
        chunk = batch[i:i + 25]
        r = _get("", {"ids": ",".join(p for _, _, p in chunk), "fields": FIELDS})
        if "_error" in r:
            print("batch error", r["_error"]); continue
        for src, slug, pid in chunk:
            d = r.get(pid)
            if not isinstance(d, dict) or "created_time" not in d:
                missing += 1
                continue
            t = datetime.datetime.fromisoformat(
                d["created_time"].replace("+0000", "+00:00")).astimezone(BD)
            eng = (d.get("reactions", {}).get("summary", {}).get("total_count", 0)
                   + d.get("comments", {}).get("summary", {}).get("total_count", 0)
                   + d.get("shares", {}).get("count", 0))
            reach = None
            ins = d.get("insights")
            if isinstance(ins, dict) and ins.get("data"):
                for m in ins["data"]:
                    if m["name"] == "post_impressions_unique" and m["values"]:
                        reach = m["values"][0].get("value")
            elif ins is None:
                denied += 1
            rows.append({"src": src, "slug": slug, "hour": t.hour,
                         "date": t.date().isoformat(), "eng": eng, "reach": reach})

    print(f"usable {len(rows)}, no created_time {missing}, no insights payload {denied}")
    json.dump(rows, open("slot_data.json", "w"), indent=1)

    have_reach = [r for r in rows if r["reach"] is not None]
    print(f"\nposts with reach: {len(have_reach)} of {len(rows)}")

    def table(key, sel):
        by = {}
        for r in sel:
            by.setdefault(r["hour"], []).append(r[key])
        print(f"\n{key} by Dhaka hour")
        print(f"{'hour':>5} {'n':>4} {'median':>8} {'mean':>8} {'max':>7}")
        for h in sorted(by):
            v = by[h]
            print(f"{h:>5} {len(v):>4} {statistics.median(v):>8.1f} "
                  f"{statistics.mean(v):>8.1f} {max(v):>7}")

    if have_reach:
        table("reach", have_reach)
    table("eng", rows)


if __name__ == "__main__":
    main()
