# -*- coding: utf-8 -*-
"""Build surahs.json: one Facebook link post per surah, 1 to 114, one a day.

Captions are hand-written, one per surah, in surah_captions.py. Nothing here is
templated.

Each post links to that surah's video on the Wasilah YouTube channel. Facebook
scrapes the URL and renders its og:image, which is the 1280x720 surah card from
wasilah-quran-video/thumbs, so the card appears on the Page with no media
uploaded from here.

Video ids come from the render repo's own ledger, never hand-typed:
    ~/Developer/wasilah-quran-video/state/uploaded.json

Usage:  python3 build_surahs.py --start 2026-09-09 --write
"""
import argparse, datetime, json, os

from surah_captions import CAPTIONS

LEDGER = os.path.expanduser("~/Developer/wasilah-quran-video/state/uploaded.json")
OUT = "surahs.json"

# 20:00 Dhaka. Miraz's call, 2026-09-08, over the 09:00 the data pointed at.
# It is the one free hour left in his evening window: 21:00, 21:30, 21:45,
# 22:00 and 22:30 BD are taken every day by statics, reels and carousels, and
# 20:00 has never been used on this Page. The engagement data that argued for
# the morning was weak anyway (medians of 3 against 2, on counts of 0 to 7,
# with post-level reach not measurable at all in Graph v21). See
# analyze_slots.py.
HOUR_UTC = 14

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


def bn_num(x):
    """Bangla digits. A Bangla caption never carries ASCII numerals."""
    return str(x).translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))


def message(n, playlist):
    hook, body = CAPTIONS[n]
    return (f"{hook}\n{body}\n\n"
            f"সূরা {BN[n]}। তিলাওয়াতে ইয়াসির আল-দোসারি, ইংরেজি অনুবাদসহ। কোরআন সিরিজ {bn_num(n)} / ১১৪।\n"
            f"পুরো কোরআন এক প্লেলিস্টে: https://www.youtube.com/playlist?list={playlist}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM-DD, the day surah 1 posts")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    led = json.load(open(LEDGER))
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
        # Surah 1 carries a "&t=0s" tail. Facebook pins its cached preview
        # image to the exact url string, and it had already cached the old card
        # for the bare watch url before the 2026-09-08 re-render. A distinct url
        # is the only thing that made it fetch the new card. YouTube treats it
        # as the same video. Do not "tidy" this away.
        link = f"https://www.youtube.com/watch?v={e['id']}" + ("&t=0s" if n == 1 else "")
        out.append({
            "slug": f"surah-{n:03d}",
            "iso": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "message": message(n, playlist),
            "link": link,
        })

    if a.write:
        json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=2)
        print(f"wrote {OUT}: {len(out)} posts, {out[0]['iso']} to {out[-1]['iso']}")
    else:
        print(json.dumps(out[:2], ensure_ascii=False, indent=2))
        print(f"...{len(out)} posts, {out[0]['iso']} to {out[-1]['iso']}")


if __name__ == "__main__":
    main()
