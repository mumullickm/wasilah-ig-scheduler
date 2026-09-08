# -*- coding: utf-8 -*-
"""Build surahs.json: one Facebook link post per surah, 1 to 114, one a day.

Each post links to that surah's video on the Wasilah YouTube channel. Facebook
scrapes the URL and renders YouTube's own thumbnail, which is the 1280x720
surah card rendered by wasilah-quran-video (`thumbs/NNN.jpg`), so the card is
what appears on the Page without uploading any media here.

Video ids come from the render repo's own ledger, never hand-typed:
    ~/Developer/wasilah-quran-video/state/uploaded.json

Usage:  python3 build_surahs.py --start 2026-09-09 --write
"""
import argparse, datetime, json, os

LEDGER = os.path.expanduser("~/Developer/wasilah-quran-video/state/uploaded.json")
CHAPTERS = os.path.expanduser("~/Developer/wasilah-quran-video/data/chapters.json")
OUT = "surahs.json"
HOUR_UTC = 13  # 19:00 Dhaka. Every other Wasilah slot is taken, see the hour
               # histogram in statics/reels/carousels/daily.

BN = {
 1:"আল-ফাতিহা",2:"আল-বাকারা",3:"আলে ইমরান",4:"আন-নিসা",5:"আল-মায়িদা",6:"আল-আনআম",
 7:"আল-আরাফ",8:"আল-আনফাল",9:"আত-তাওবা",10:"ইউনুস",11:"হুদ",12:"ইউসুফ",13:"আর-রাদ",
 14:"ইবরাহিম",15:"আল-হিজর",16:"আন-নাহল",17:"আল-ইসরা",18:"আল-কাহফ",19:"মারইয়াম",
 20:"ত্বহা",21:"আল-আম্বিয়া",22:"আল-হজ্জ",23:"আল-মুমিনুন",24:"আন-নূর",25:"আল-ফুরকান",
 26:"আশ-শুআরা",27:"আন-নামল",28:"আল-কাসাস",29:"আল-আনকাবুত",30:"আর-রুম",31:"লুকমান",
 32:"আস-সাজদা",33:"আল-আহযাব",34:"সাবা",35:"ফাতির",36:"ইয়াসিন",37:"আস-সাফফাত",
 38:"সোয়াদ",39:"আয-যুমার",40:"গাফির",41:"ফুসসিলাত",42:"আশ-শুরা",43:"আয-যুখরুফ",
 44:"আদ-দুখান",45:"আল-জাসিয়া",46:"আল-আহকাফ",47:"মুহাম্মদ",48:"আল-ফাতহ",
 49:"আল-হুজুরাত",50:"কাফ",51:"আয-যারিয়াত",52:"আত-তুর",53:"আন-নাজম",54:"আল-কামার",
 55:"আর-রহমান",56:"আল-ওয়াকিয়া",57:"আল-হাদিদ",58:"আল-মুজাদালা",59:"আল-হাশর",
 60:"আল-মুমতাহিনা",61:"আস-সফ",62:"আল-জুমুআ",63:"আল-মুনাফিকুন",64:"আত-তাগাবুন",
 65:"আত-তালাক",66:"আত-তাহরিম",67:"আল-মুলক",68:"আল-কলম",69:"আল-হাক্কাহ",
 70:"আল-মাআরিজ",71:"নূহ",72:"আল-জিন",73:"আল-মুযযাম্মিল",74:"আল-মুদ্দাসসির",
 75:"আল-কিয়ামাহ",76:"আল-ইনসান",77:"আল-মুরসালাত",78:"আন-নাবা",79:"আন-নাযিআত",
 80:"আবাসা",81:"আত-তাকভির",82:"আল-ইনফিতার",83:"আল-মুতাফফিফিন",84:"আল-ইনশিকাক",
 85:"আল-বুরুজ",86:"আত-তারিক",87:"আল-আলা",88:"আল-গাশিয়াহ",89:"আল-ফজর",90:"আল-বালাদ",
 91:"আশ-শামস",92:"আল-লাইল",93:"আদ-দুহা",94:"আশ-শারহ",95:"আত-তীন",96:"আল-আলাক",
 97:"আল-কদর",98:"আল-বাইয়িনাহ",99:"আয-যিলযাল",100:"আল-আদিয়াত",101:"আল-কারিআহ",
 102:"আত-তাকাসুর",103:"আল-আসর",104:"আল-হুমাযাহ",105:"আল-ফীল",106:"কুরাইশ",
 107:"আল-মাউন",108:"আল-কাওসার",109:"আল-কাফিরুন",110:"আন-নাসর",111:"আল-লাহাব",
 112:"আল-ইখলাস",113:"আল-ফালাক",114:"আন-নাস",
}

# A true line about the surah, only where there is something real to say.
NOTE = {
 1:"নামাজের প্রতি রাকাতে যে সূরা পড়তে হয়। কোরআনের শুরু এখান থেকেই।",
 2:"কোরআনের দীর্ঘতম সূরা। আয়াতুল কুরসি আর শেষ দুই আয়াত এই সূরাতেই।",
 3:"ইমরানের পরিবার, মারইয়াম আর ঈসা (আ.)-এর কথা এসেছে এখানে।",
 4:"পরিবার, উত্তরাধিকার আর নারীর অধিকার নিয়ে বিধান এই সূরায়।",
 12:"ইউসুফ (আ.)-এর পুরো জীবনকাহিনি, এক সূরায় শুরু থেকে শেষ।",
 18:"জুমার দিনে পড়ার সূরা। গুহার সঙ্গীদের ঘটনা এখানেই।",
 19:"মারইয়াম (আ.)-এর কথা, তাঁর নামেই এই সূরা।",
 24:"নূরের আয়াত এই সূরায়। আলো আর পর্দার বিধান একসাথে।",
 36:"কোরআনের হৃদয় বলা হয় এই সূরাকে।",
 55:"যে সূরায় বারবার প্রশ্ন আসে, তোমরা রবের কোন নিয়ামত অস্বীকার করবে।",
 56:"কেয়ামতের দিন মানুষ তিন দলে ভাগ হবে, সেই বর্ণনা এই সূরায়।",
 62:"জুমার সূরা। শুক্রবারের আজানের পর ব্যবসা ছেড়ে ছুটে যাওয়ার নির্দেশ এখানে।",
 67:"রাতে ঘুমানোর আগে পড়ার সূরা, তাবারাকা।",
 71:"নূহ (আ.) সাড়ে নয়শো বছর ডেকেছিলেন। সেই ডাকের কথা।",
 78:"আম্মা পারার শুরু। কেয়ামতের সংবাদ নিয়ে।",
 93:"যখন মনে হয় সব থেমে গেছে, এই সূরা নাজিল হয়েছিল ঠিক সেই সময়েই।",
 94:"কষ্টের সাথেই স্বস্তি আছে। দুইবার বলা হয়েছে এখানে।",
 97:"লাইলাতুল কদর, হাজার মাসের চেয়ে উত্তম এক রাত।",
 103:"সময়ের কসম। মানুষ ক্ষতির মধ্যে আছে, ব্যতিক্রম চারটি জিনিস।",
 105:"হাতির বাহিনী আর আবাবিল পাখির ঘটনা।",
 108:"কোরআনের সবচেয়ে ছোট সূরা, মাত্র তিন আয়াত।",
 112:"এক তৃতীয়াংশ কোরআনের সমান বলা হয়েছে এই সূরাকে।",
 113:"আশ্রয় চাওয়ার সূরা। ঘুমের আগে আর সকাল-সন্ধ্যায়।",
 114:"কোরআনের শেষ সূরা। মানুষের রব, মানুষের বাদশাহর কাছে আশ্রয়।",
}

# Honest generic frames for the rest. Keyed by surah number so the same frame
# never lands two days running.
FRAME_MAKKI = [
 "মক্কায় নাজিল হওয়া সূরা, {n} আয়াত।",
 "{n} আয়াতের মক্কি সূরা। বসে একবার পুরোটা শুনে নিন।",
 "মক্কি সূরা, {n} আয়াত। তিলাওয়াতের সাথে অর্থটাও চোখের সামনে থাকে।",
]
FRAME_MADANI = [
 "মদিনায় নাজিল হওয়া সূরা, {n} আয়াত।",
 "{n} আয়াতের মাদানি সূরা। বসে একবার পুরোটা শুনে নিন।",
 "মাদানি সূরা, {n} আয়াত। তিলাওয়াতের সাথে অর্থটাও চোখের সামনে থাকে।",
]

TAIL = ("তিলাওয়াতে ইয়াসির আল-দোসারি, সাথে ইংরেজি অনুবাদ।\n"
        "পুরো কোরআন, ১১৪ সূরা, একটি প্লেলিস্টে: https://www.youtube.com/playlist?list={pl}")


def bn_num(x):
    """Bangla digits. A Bangla caption never carries ASCII numerals."""
    return str(x).translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))


def message(n, ch, playlist):
    note = NOTE.get(n)
    if not note:
        frames = FRAME_MAKKI if ch["revelation_place"] == "makkah" else FRAME_MADANI
        note = frames[n % len(frames)].format(n=bn_num(ch["verses_count"]))
    return f"সূরা {BN[n]}।\n{note}\n\n" + TAIL.format(pl=playlist)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM-DD, the day surah 1 posts")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    led = json.load(open(LEDGER))
    chapters = {c["id"]: c for c in json.load(open(CHAPTERS))}
    playlist = led["_playlist"]
    d0 = datetime.date.fromisoformat(a.start)

    out = []
    for n in range(1, 115):
        e = led.get(str(n))
        if not e or not e.get("id"):
            raise SystemExit(f"surah {n} has no video id in the ledger")
        if e.get("privacy") != "public":
            raise SystemExit(f"surah {n} is not public ({e.get('privacy')})")
        when = datetime.datetime.combine(
            d0 + datetime.timedelta(days=n - 1),
            datetime.time(HOUR_UTC, 0), datetime.timezone.utc)
        out.append({
            "slug": f"surah-{n:03d}",
            "iso": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "message": message(n, chapters[n], playlist),
            "link": f"https://www.youtube.com/watch?v={e['id']}",
        })

    if a.write:
        json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=2)
        print(f"wrote {OUT}: {len(out)} posts, {out[0]['iso']} to {out[-1]['iso']}")
    else:
        print(json.dumps(out[:2], ensure_ascii=False, indent=2))
        print(f"...{len(out)} posts, {out[0]['iso']} to {out[-1]['iso']}")


if __name__ == "__main__":
    main()
