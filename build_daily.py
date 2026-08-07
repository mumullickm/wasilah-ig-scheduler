"""Build daily.json, the ONE queue that TikTok and YouTube Shorts both publish.

WHY THIS EXISTS. Until 2026-08-07 the two channels ran on different queues with
different content and different cadences: YouTube drained reels.json at six a day
ignoring the schedule, while TikTok worked through its own tiktok.json of
quran60/P-series videos that were not on YouTube at all. Nothing lined up. Miraz's
instruction, 2026-08-07: the same post goes out on every platform, and no day is
missed. One queue is the only way that stays true, because two queues drift the
moment either is topped up.

WHAT ONE ENTRY IS. A distinct video asset, one per day, at 21:00 Asia/Dhaka. Both
workers read this file, key their ledger by the same slug, and take their words
from youtube_meta.json, so the video, the date and the copy are identical by
construction rather than by anyone remembering to mirror an edit.

WHY 21:00 DHAKA. Measured on the TikTok account, not chosen: 21:00 ran n=12 median
212 views against a median of 1 to 2 at 19:00, 20:00, 22:00 and 23:00. YouTube has
no equivalent evidence, so it follows TikTok's proven slot rather than the reverse.

WHY ONE A DAY. TikTok's ceiling, again measured: a 25-video burst on 29 Jul 2026
died at 0 to 4 views each while an on-slot post the same evening took 287. YouTube
could do six (1600 quota units against 10,000/day), but six on one channel and one
on the other is exactly the drift this file removes.

ASSETS ALREADY ON YOUTUBE ARE EXCLUDED. Thirty-four went up during the drain, and
YouTube treats a re-upload of the same file as competing with itself. So parity
starts from the next unpublished asset. TikTok therefore never receives those 34
unless they are queued deliberately, which is Miraz's call, not a default.

Regenerate with:  python3 build_daily.py --start 2026-08-07 --write
Without --write it prints the plan and touches nothing.
"""
import argparse, datetime, json, os, re

CFG = json.load(open("config.json", encoding="utf-8"))
VIDEO_BASE = CFG["videoBase916"]
DHAKA = datetime.timezone(datetime.timedelta(hours=6))
SLOT_HOUR = 21
OUT = "daily.json"


def asset_id(rid):
    """A cycle suffix reuses the same mp4: v01-pausesc2 is v01-pauses."""
    m = re.fullmatch(r"(.+?)c\d+", rid)
    return m.group(1) if m else rid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="first posting date, YYYY-MM-DD")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    reels = json.load(open("reels.json", encoding="utf-8"))
    caps = json.load(open("reel_captions.json", encoding="utf-8"))
    meta = json.load(open("youtube_meta.json", encoding="utf-8"))
    yt = json.load(open("posted_youtube.json", encoding="utf-8")) \
        if os.path.exists("posted_youtube.json") else {}

    # reels.json order is the editorial order and is preserved. Repeats collapse to
    # their first appearance, so the queue is distinct assets in broadcast order.
    seen, assets = set(), []
    for r in reels:
        a = asset_id(r["reel"])
        if a in seen or a in yt:
            continue
        seen.add(a)
        assets.append(a)

    missing = [a for a in assets if a not in caps or a not in meta]
    if missing:
        raise SystemExit(f"no caption or youtube_meta for: {missing}")

    day = datetime.date.fromisoformat(args.start)
    queue = []
    for a in assets:
        iso = datetime.datetime.combine(
            day, datetime.time(SLOT_HOUR, 0), tzinfo=DHAKA).isoformat()
        queue.append({"slug": a, "iso": iso, "video": f"{VIDEO_BASE}/{a}.mp4"})
        day += datetime.timedelta(days=1)

    print(f"{len(queue)} posts, {queue[0]['iso'][:10]} to {queue[-1]['iso'][:10]}, "
          f"one a day at {SLOT_HOUR:02d}:00 Dhaka")
    for e in queue[:3]:
        print(f"  {e['iso'][:10]}  {e['slug']}")
    print("  ...")
    if args.write:
        json.dump(queue, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"wrote {OUT}")
    else:
        print("dry run, nothing written (pass --write)")


if __name__ == "__main__":
    main()
