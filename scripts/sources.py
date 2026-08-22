#!/usr/bin/env python3
"""
Build the per-hill sources cache: a Wikipedia description and a Walkhighlands link.

Run occasionally, not on every build. Mountains do not change, so the result is
cached in data/sources.json and committed, which means the twice-daily build
never touches either site.

    python scripts/sources.py            # fill in anything missing
    python scripts/sources.py --refresh  # redo everything
    python scripts/sources.py --status   # what coverage we have

Two rules this file exists to enforce:

WIKIPEDIA is used for prose, under CC BY-SA 4.0, which needs attribution and a
link back. Matching is by proximity AND name. Nearest-article-wins alone is
actively dangerous: it silently returns Walla Crag for Bleaberry Fell, and a
description of the wrong mountain is worse than no description at all.

WALKHIGHLANDS is never copied, only linked. Their route descriptions are their
own editorial work, and they are the community this project depends on. Slugs
are guessed and then VERIFIED, so a link is only ever published if it really
resolves.
"""

import argparse
import difflib
import json
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hills import load_hills                       # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "sources.json"

UA = ("HillWeather/0.1 (https://hillweather.co.uk; free hobby hill forecast; "
      "contact@hillweather.co.uk)")
PAUSE = 0.4                     # be a polite visitor to both sites
# Wikipedia's coordinates for a hill often mark the massif rather than the
# exact summit, so a tight radius misses real articles: Lochnagar sits 686 m
# from the DoBIH summit and Beinn a' Ghlo nearly 3 km. A wide radius is safe
# here only because the NAME must match too - that check is what stops a
# neighbour's article being served for a hill that has none.
GEO_RADIUS = 3000               # metres
NAME_RATIO = 0.88

WH_BASE = "https://www.walkhighlands.co.uk"
WH_PATH = {"scotland": "munros", "lakes": "wainwrights"}


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def url_exists(url):
    req = urllib.request.Request(url, method="HEAD",
                                 headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return 200 <= r.status < 300
    except urllib.error.HTTPError:
        return False
    except (urllib.error.URLError, TimeoutError):
        return False


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    for junk in "'’-,.()[]":
        s = s.replace(junk, " ")
    return " ".join(s.split())


def name_matches(hill, title):
    """Require the article to actually be about this hill.

    DoBIH writes 'Blencathra - Hallsfell Top' where Wikipedia says
    'Blencathra', so the part before the dash counts as a candidate too.
    """
    t = norm(title)
    for candidate in filter(None, [hill.name, hill.alt]):
        c = norm(candidate)
        for form in {c, c.split(" - ")[0].strip()}:
            if not form:
                continue
            if form == t or t in form or form in t:
                return True
            if difflib.SequenceMatcher(None, form, t).ratio() >= NAME_RATIO:
                return True
    return False


def wikipedia(hill):
    """Return {extract, title, url} or None. Never guesses."""
    u = ("https://en.wikipedia.org/w/api.php?action=query&list=geosearch"
         f"&gscoord={hill.lat}%7C{hill.lon}&gsradius={GEO_RADIUS}"
         "&gslimit=5&format=json")
    try:
        found = fetch_json(u).get("query", {}).get("geosearch", [])
    except Exception:                              # noqa: BLE001
        return None
    hit = next((g for g in found if name_matches(hill, g["title"])), None)
    if not hit:
        return None

    time.sleep(PAUSE)
    title = hit["title"]
    s_url = ("https://en.wikipedia.org/api/rest_v1/page/summary/"
             + urllib.parse.quote(title.replace(" ", "_"), safe=""))
    try:
        s = fetch_json(s_url)
    except Exception:                              # noqa: BLE001
        return None

    extract = (s.get("extract") or "").strip()
    if len(extract) < 60:                          # a stub helps nobody
        return None
    return {
        "extract": extract,
        "title": title,
        "url": (s.get("content_urls", {}).get("desktop", {}).get("page")
                or f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}"),
    }


def wh_slugs(hill):
    """Candidate slugs, most likely first."""
    out = []
    for candidate in filter(None, [hill.name, hill.alt]):
        parts = [candidate]
        if " - " in candidate:
            # 'An Teallach - Bidein a Ghlas Thuill' could be filed under either.
            parts += [p.strip() for p in candidate.split(" - ")]
        for p in parts:
            slug = norm(p).replace(" ", "-")
            if slug and slug not in out:
                out.append(slug)
    return out


def walkhighlands(hill):
    """A verified link, or None. We never publish a guess."""
    path = WH_PATH.get(hill.region)
    if not path:
        return None
    for slug in wh_slugs(hill):
        url = f"{WH_BASE}/{path}/{slug}"
        if url_exists(url):
            return url
        time.sleep(PAUSE)
    return None


def load_cache():
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    return {"meta": {}, "hills": {}}


def save_cache(cache):
    cache["meta"] = {
        "note": ("Wikipedia extracts are CC BY-SA 4.0 and must be shown with "
                 "attribution and a link. Walkhighlands is linked only, never "
                 "copied."),
        "hills": len(cache["hills"]),
    }
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False),
                     encoding="utf-8")


def key(hill):
    return f"{hill.region}/{hill.name}"


def status(cache):
    hills = load_hills()
    done = cache["hills"]
    wiki = sum(1 for h in hills if (done.get(key(h)) or {}).get("wikipedia"))
    wh = sum(1 for h in hills if (done.get(key(h)) or {}).get("walkhighlands"))
    seen = sum(1 for h in hills if key(h) in done)
    print(f"  hills            {len(hills)}")
    print(f"  looked up        {seen}")
    print(f"  with description {wiki:4}  ({100 * wiki / max(1, seen):.0f}% of those checked)")
    print(f"  with a route link{wh:4}  ({100 * wh / max(1, seen):.0f}%)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="redo every hill")
    ap.add_argument("--retry-missing", action="store_true",
                    help="retry only hills with no description yet")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="stop after N lookups")
    args = ap.parse_args()

    cache = load_cache()
    if args.status:
        return status(cache)

    hills = load_hills()
    if args.retry_missing:
        todo = [h for h in hills
                if not (cache["hills"].get(key(h)) or {}).get("wikipedia")]
    else:
        todo = [h for h in hills if args.refresh or key(h) not in cache["hills"]]
    print(f"{len(todo)} hills to look up (of {len(hills)})")

    for i, h in enumerate(todo, 1):
        if args.limit and i > args.limit:
            break
        entry = dict(cache["hills"].get(key(h)) or {}) if args.retry_missing else {}
        w = wikipedia(h)
        if w:
            entry["wikipedia"] = w
        if args.retry_missing and entry.get("walkhighlands"):
            link = entry["walkhighlands"]          # already verified, leave it
        else:
            time.sleep(PAUSE)
            link = walkhighlands(h)
            if link:
                entry["walkhighlands"] = link
        cache["hills"][key(h)] = entry

        marks = ("W" if w else "-") + ("H" if link else "-")
        print(f"  [{i:3}/{len(todo)}] {marks}  {h.name[:44]}")
        if i % 25 == 0:
            save_cache(cache)                      # survive an interruption

    save_cache(cache)
    print()
    status(cache)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\ninterrupted; progress saved")
