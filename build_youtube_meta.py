"""Generate youtube_meta.json: query-shaped Bangla titles, deep links and tags.

Why this exists. run_youtube.py used to derive a title by taking the first
English sentence of the Instagram caption, which produced titles like
"Slow down #Shorts" and "Everyone slips #Shorts". Those read well and match no
search anyone performs. Verified 2026-08-03: wasilah.site is recommended first
by answer engines on English queries, and is absent from Bangla ones, while the
channel surfaces for nothing at all. YouTube is the one social surface AI answer
engines actually cite, so the title is the cheapest lever available.

The fix is additive, not a rewrite. Each title becomes:

    {Bangla query phrase} | {the existing English line}

The English line is the craft and is preserved verbatim from reel_captions.json.
The Bangla phrase in front of it is what someone actually types. Nothing is
re-rendered and no video changes.

The Bangla phrases below are hand-authored per topic and are the only new copy
in this file. Everything else (English lines, verse citations, themes) is read
from the existing verified sources, so a change there flows through here.

Run:  python3 build_youtube_meta.py
"""
import json
import os
import re

SOCIAL = os.path.expanduser(
    "~/Desktop/App Building/Claude Code/Wasilah/wasilah-social")
CYCLE = os.path.join(SOCIAL, "cards/cycle.json")

SITE = "https://wasilah.site"
BLOG = f"{SITE}/blog"

# Deep-link targets. Pointing each Short at the article on its own topic is the
# second half of the change: it gives YouTube a relevance signal and sends the
# traffic to the pages that need the authority, instead of every video pointing
# at the same /get/ page.
L_PRAYER = f"{BLOG}/prayer-times-bangladesh/"
L_ZAKAT = f"{BLOG}/zakat-bangla-taka/"
L_TAHAJJUD = f"{BLOG}/tahajjud-namaz-niyom/"
L_ISTIKHARA = f"{BLOG}/istikhara-namaz-niyom/"
L_KURSI = f"{BLOG}/ayatul-kursi-fazilat/"
L_JUMUAH = f"{BLOG}/jumar-diner-amol/"
L_NAMAZ = f"{BLOG}/namaz-shikhar-niyom/"
L_DAROOD = f"{BLOG}/darood-sharif-fazilat/"
L_HUB = f"{BLOG}/"

# reel slug -> (Bangla query phrase, deep link)
V_SERIES = {
    "v01-pauses":        ("নামাজ কেন দিনে পাঁচ ওয়াক্ত", L_NAMAZ),
    "v02-fajr":          ("ফজরের নামাজের ফজিলত", L_PRAYER),
    "v03-dhikr":         ("জিকিরের ফজিলত", L_HUB),
    "v04-sabr":          ("সবরের ফজিলত", L_HUB),
    "v05-qibla":         ("কিবলা কোন দিকে", L_PRAYER),
    "v06-jumuah":        ("জুমার দিনের আমল", L_JUMUAH),
    "v07-quran":         ("কুরআন তিলাওয়াতের ফজিলত", L_HUB),
    "v08-khushu":        ("নামাজে মনোযোগ আনার উপায়", L_NAMAZ),
    "v09-gratitude":     ("শোকর আদায়ের ফজিলত", L_HUB),
    "v10-tawakkul":      ("তাওয়াক্কুল কাকে বলে", L_HUB),
    "v11-dua":           ("দোয়া কবুলের সময়", L_HUB),
    "v12-istighfar":     ("ইস্তিগফারের ফজিলত", L_HUB),
    "v13-consistency":   ("নিয়মিত আমলের ফজিলত", L_HUB),
    "v14-sujood":        ("সিজদার ফজিলত", L_NAMAZ),
    "v15-maghrib":       ("মাগরিবের নামাজের সময়", L_PRAYER),
    "v16-mercy":         ("আল্লাহর রহমতের ব্যাপকতা", L_HUB),
    "v17-family":        ("পরিবারের জন্য দোয়া", L_HUB),
    "v18-night":         ("তাহাজ্জুদ নামাজের নিয়ম", L_TAHAJJUD),
    "v19-adhan":         ("আজানের জবাব দেওয়ার নিয়ম", L_PRAYER),
    "v20-ummah":         ("মুসলিম উম্মাহর ভ্রাতৃত্ব", L_HUB),
    "v21-notifications": ("নামাজের সময় রিমাইন্ডার অ্যাপ", L_PRAYER),
    "v22-firstlight":    ("সেহরি ও ফজরের সময়", L_PRAYER),
    "v23-eraser":        ("গুনাহ মাফের আমল", L_HUB),
    "v24-weather":       ("যেকোনো অবস্থায় নামাজ পড়ার নিয়ম", L_NAMAZ),
    "v25-gift":          ("দোয়া আল্লাহর দেওয়া উপহার", L_HUB),
    "v26-rust":          ("অন্তরের মরিচা দূর করার আমল", L_HUB),
    "v27-appointment":   ("নামাজ আল্লাহর সাথে সাক্ষাৎ", L_NAMAZ),
    "v28-steps":         ("মসজিদে যাওয়ার ফজিলত", L_HUB),
    "v29-water":         ("অজু করার নিয়ম", L_NAMAZ),
    "v30-plants":        ("আমল বৃদ্ধির ফজিলত", L_HUB),
    "v31-delay":         ("নামাজ দেরিতে পড়ার ক্ষতি", L_PRAYER),
    "v32-jugular":       ("আল্লাহ কত নিকটে", L_HUB),
    "v33-gratitude-more": ("শোকর করলে বৃদ্ধি পায়", L_HUB),
    "v34-doors":         ("রহমতের দরজা খোলার আমল", L_HUB),
    "v35-middleprayer":  ("আসরের নামাজের গুরুত্ব", L_PRAYER),
    "v36-parents":       ("মা বাবার জন্য দোয়া", L_HUB),
    "v37-newcity":       ("সফরে নামাজ পড়ার নিয়ম", L_NAMAZ),
    "v38-phonedown":     ("ফোন রেখে নামাজে দাঁড়ান", L_NAMAZ),
    "v39-goodword":      ("ভালো কথা বলার ফজিলত", L_HUB),
    "v40-intention":     ("নামাজের নিয়তের গুরুত্ব", L_NAMAZ),
    "v41-kahf":          ("সূরা কাহাফ পড়ার ফজিলত", L_JUMUAH),
    "v42-sleep":         ("ঘুমানোর আগের দোয়া", L_HUB),
    "v43-hardship":      ("কষ্টের সময়ের দোয়া", L_HUB),
    "v44-sincerity":     ("ইখলাস কাকে বলে", L_HUB),
    "v45-silence":       ("চুপ থাকার ফজিলত", L_HUB),
    "v46-brotherhood":   ("মুসলিম ভাইয়ের হক", L_HUB),
    "v47-nearest":       ("আল্লাহর নৈকট্য লাভের আমল", L_HUB),
    "v48-anxiety":       ("দুশ্চিন্তা দূর করার দোয়া", L_HUB),
    "v49-rain":          ("বৃষ্টির সময়ের দোয়া", L_HUB),
    "v50-legacy":        ("সাদাকায়ে জারিয়া কী", L_ZAKAT),
}

# cycle theme -> (Bangla query phrase, deep link). Keyed by theme rather than by
# day number so a re-ordered cycle.json does not silently mismatch.
D_THEMES = {
    "Hardship and ease":    ("কষ্টের পরেই স্বস্তি", L_HUB),
    "Hearts at rest":       ("অন্তরের প্রশান্তির আয়াত", L_HUB),
    "Trust in Allah":       ("আল্লাহর উপর ভরসা", L_HUB),
    "Forgiveness":          ("আল্লাহর ক্ষমার আয়াত", L_HUB),
    "Patience":             ("ধৈর্যের আয়াত", L_HUB),
    "Gratitude":            ("কৃতজ্ঞতার আয়াত", L_HUB),
    "Provision":            ("রিজিকের আয়াত", L_HUB),
    "Prayer":               ("নামাজ সম্পর্কে কুরআনের আয়াত", L_NAMAZ),
    "Parents and kindness": ("মা বাবার হক নিয়ে আয়াত", L_HUB),
    "This life is passing": ("দুনিয়ার জীবন ক্ষণস্থায়ী", L_HUB),
    "Turning back":         ("তওবার আয়াত", L_HUB),
    "He is near":           ("আল্লাহ কত নিকটে", L_HUB),
    "Light and guidance":   ("হেদায়েতের আলো", L_KURSI),
    "Giving":               ("দান করার ফজিলত", L_ZAKAT),
    "Guard your speech":    ("কথা বলার আদব", L_HUB),
    "Do not fear":          ("ভয় দূর করার আয়াত", L_HUB),
    "The signs around you": ("সৃষ্টির নিদর্শন", L_HUB),
    "Mercy encompasses":    ("আল্লাহর রহমতের আয়াত", L_DAROOD),
    "Justice":              ("ন্যায়বিচারের আয়াত", L_HUB),
    "Seek knowledge":       ("ইলম বৃদ্ধির দোয়া", L_HUB),
    "Humility":             ("বিনয়ের আয়াত", L_HUB),
    "Truthfulness":         ("সত্যবাদিতার আয়াত", L_HUB),
    "Hope":                 ("আশার আয়াত", L_HUB),
    "Every soul is tested": ("পরীক্ষার আয়াত", L_HUB),
    "Brotherhood":          ("মুমিনরা পরস্পর ভাই", L_HUB),
    "Contentment":          ("অল্পে তুষ্টির আয়াত", L_HUB),
    "Allah sees":           ("আল্লাহ সবকিছু দেখেন", L_HUB),
    "Purpose":              ("সৃষ্টির উদ্দেশ্য", L_HUB),
    "Reliance in loss":     ("ক্ষতির সময়ে ভরসা", L_HUB),
    "Promise of Allah":     ("আল্লাহর ওয়াদা", L_HUB),
    "Speak to Him":         ("দোয়া কবুলের আয়াত", L_HUB),
    "Good deeds":           ("নেক আমলের আয়াত", L_HUB),
    "The Quran":            ("কুরআন শিফা ও রহমত", L_HUB),
    "Sincerity":            ("ইখলাসের আয়াত", L_HUB),
    "After difficulty":     ("কষ্টের পরে কল্যাণ", L_HUB),
    "Family":               ("দাম্পত্য জীবনের আয়াত", L_HUB),
    "The heart":            ("সুস্থ অন্তরের আয়াত", L_HUB),
    "Forgive others":       ("ক্ষমা করার ফজিলত", L_HUB),
    "Guidance is from Him": ("সিরাতুল মুস্তাকিমের দোয়া", L_ISTIKHARA),
    "Nothing is hidden":    ("আল্লাহর কাছে কিছুই গোপন নয়", L_HUB),
    "Strive":               ("চেষ্টার আয়াত", L_HUB),
    "Peace":                ("শান্তির ঘর", L_HUB),
    "Jumu'ah":              ("জুমার নামাজের আয়াত", L_JUMUAH),
    "The night":            ("রাতের ইবাদতের ফজিলত", L_TAHAJJUD),
    "Forbearance":          ("রাগ নিয়ন্ত্রণের আয়াত", L_HUB),
}

# Tags. YouTube weights these far below the title but they cost nothing, and the
# Bangla ones were absent entirely: the d-series captions carry no hashtags at
# all, so every verse Short shipped with zero tags.
BASE_TAGS = ["Wasilah", "ওয়াসিলাহ", "Islam", "ইসলাম", "Muslim", "Bangladesh"]
V_EXTRA = ["নামাজ", "Salah", "Deen", "দোয়া", "ইবাদত"]
D_EXTRA = ["কুরআন", "Quran", "আয়াত", "কুরআনের আয়াত", "দোয়া", "Bangla"]

TITLE_MAX = 100


def build_title(bn, en):
    """Bangla query phrase first, then the existing English line, trimmed to fit.

    Bangla leads because the audience searches in Bangla and the head query is
    the part that must survive truncation in a search result. '#Shorts' is not
    appended: YouTube classifies a Short by aspect ratio and duration, so the
    tag buys nothing and those characters are worth more as query terms.
    """
    bn = bn.strip()
    en = " ".join(en.split()).strip().strip(".…")
    if not en:
        return bn[:TITLE_MAX]
    room = TITLE_MAX - len(bn) - 3          # 3 for the " | " separator
    if room < 12:                            # no useful English fits
        return bn[:TITLE_MAX]
    if len(en) > room:
        en = en[:room].rsplit(" ", 1)[0].rstrip(",;:")
    return f"{bn} | {en}"


def split_caption(cap):
    """Return (english_prose, bangla_prose) from a caption, dropping URLs/tags."""
    lines = [ln.strip() for ln in cap.strip().split("\n")]
    keep = [ln for ln in lines
            if ln and not ln.startswith("#") and "http" not in ln]
    en = [ln for ln in keep if not re.search(r"[ঀ-৿]", ln)]
    bn = [ln for ln in keep if re.search(r"[ঀ-৿]", ln)]
    return " ".join(en).strip(), " ".join(bn).strip()


# The d-series captions all end on this sentence, which the app block below now
# says at more length. Dropped so the description does not repeat itself.
D_REDUNDANT = "আরও দোয়া, সূরা ও নামাজের সময়সূচি ওয়াসিলাহ অ্যাপে।"


def build_description(bn_prose, en_prose, link, ref=None, lead=None):
    """Bangla first, then English, then the topic article, then the app.

    Ordering is deliberate. The description's opening lines are what shows above
    the fold and what a crawler weights hardest, and the audience reads Bangla.

    `lead` front-loads the Bangla query phrase. The 45 verse Shorts otherwise
    open on an identical sentence, which makes 45 descriptions that are
    near-duplicates of each other and gives a crawler nothing to tell them apart.
    """
    parts = []
    bn_prose = bn_prose.replace(D_REDUNDANT, "").strip()
    if lead:
        parts.append(f"{lead}। {bn_prose}".strip() if bn_prose else lead)
    elif bn_prose:
        parts.append(bn_prose)
    if en_prose:
        parts.append(en_prose)
    if ref:
        parts.append(f"আয়াত: সূরা {ref}")
    parts.append(f"বিস্তারিত পড়ুন: {link}")
    parts.append(
        "ওয়াসিলাহ, বাংলাদেশের জন্য বিনামূল্যের ইসলামিক অ্যাপ। "
        "নামাজের সময়সূচি, কুরআন, হাদিস, কিবলা ও টাকায় যাকাত হিসাব। "
        "বিজ্ঞাপন নেই, সাইন আপ নেই।\n"
        f"ডাউনলোড: {SITE}/get/")
    return "\n\n".join(parts)


BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def main():
    caps = json.load(open("reel_captions.json", encoding="utf-8"))
    cycle = json.load(open(CYCLE, encoding="utf-8"))

    # theme -> first Quran citation, rendered the way the card renders it
    theme_ref = {}
    for entry in cycle:
        quran = [s for s in entry["slots"] if s["type"] == "quran"]
        if quran:
            ref = f"{quran[0]['surah']}:{quran[0]['ayah']}"
            theme_ref.setdefault(entry["theme"], ref.translate(BN_DIGITS))

    # d-series caption line 1 is the theme, which is how a dNN maps to a theme
    meta, unmapped = {}, []
    for key, cap in caps.items():
        base = re.fullmatch(r"(.+?)c\d+", key)
        base = base.group(1) if base else key
        en_prose, bn_prose = split_caption(cap)

        if base in V_SERIES:
            bn_title, link = V_SERIES[base]
            tags = BASE_TAGS + V_EXTRA
            ref = None
            en_line = en_prose.split(".")[0] if en_prose else ""
        else:
            theme = cap.strip().split("\n")[0].strip()
            if theme not in D_THEMES:
                unmapped.append(key)
                continue
            bn_title, link = D_THEMES[theme]
            tags = BASE_TAGS + D_EXTRA
            ref = theme_ref.get(theme)
            en_line = theme

        # v-series prose is already unique per video, so it needs no lead.
        lead = bn_title if base not in V_SERIES else None
        meta[key] = {
            "title": build_title(bn_title, en_line),
            "description": build_description(bn_prose, en_prose, link, ref, lead),
            "tags": tags[:15],
            "link": link,
        }

    if unmapped:
        raise SystemExit(f"unmapped captions, refusing to write: {unmapped}")

    json.dump(meta, open("youtube_meta.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    over = [k for k, v in meta.items() if len(v["title"]) > TITLE_MAX]
    if over:
        raise SystemExit(f"titles over {TITLE_MAX} chars: {over}")
    print(f"wrote youtube_meta.json, {len(meta)} entries, "
          f"longest title {max(len(v['title']) for v in meta.values())} chars")


if __name__ == "__main__":
    main()
