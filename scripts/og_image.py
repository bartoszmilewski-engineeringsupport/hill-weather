#!/usr/bin/env python3
"""
Generate the link preview image.

Pasting the site into a walking group is the entire growth model, so what
appears in that message matters as much as the page itself. Without this, a
link is a bare URL.

    python scripts/og_image.py

Boards 3b and 3c of the design handoff. The card reports the real forecast for
the first day in the build, so a link pasted into a group chat previews the
actual answer rather than a logo. It picks the inversion layout when a summit
is confidently above the cloud top, using exactly the test the front page uses,
and the ordinary layout otherwise. With no built data present it falls back to
a generic card, so a fresh clone still produces something.

The URL stays /og.png rather than gaining a hash. Link scrapers cache hard and
a changing URL would make every previously shared link re-scrape; the card
carries its own date, so a stale preview is out of date but never wrong about
which day it describes.

1200x630 is the size every platform crops from. Everything important stays well
inside the middle, because Twitter, WhatsApp and Slack all crop differently and
none of them tell you how.
"""

import json
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
OUT = WEB / "og.png"

W, H = 1200, 630
PAD_X, PAD_TOP, PAD_BOT = 56, 40, 34

PAPER = (251, 247, 240)
INK = (42, 37, 33)
OCHRE = (168, 118, 63)
MUTED = (107, 97, 86)
FAINT = (140, 129, 117)
RULE = (220, 210, 192)
RELIEF = (243, 236, 223)
DECK = (231, 221, 200)

# Georgia is the closest thing on hand to Newsreader: a warm serif with real
# weight. The face only has to feel like the site, not match it exactly.
#
# Where to look, in order. The last two cover a Linux box that has DejaVu but
# no Microsoft fonts, which is the usual case on a server.
FONT_DIRS = [Path("C:/Windows/Fonts"),
             Path("/usr/share/fonts/truetype/msttcorefonts"),
             Path("/usr/share/fonts/truetype/dejavu"),
             Path("/usr/share/fonts/TTF"),
             Path("/usr/share/fonts")]
ALIASES = {
    "georgia.ttf": ["georgia.ttf", "DejaVuSerif.ttf", "LiberationSerif-Regular.ttf"],
    "georgiab.ttf": ["georgiab.ttf", "DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf"],
    "georgiai.ttf": ["georgiai.ttf", "DejaVuSerif-Italic.ttf", "LiberationSerif-Italic.ttf"],
}


def find(name):
    for candidate in ALIASES.get(name, [name]):
        for directory in FONT_DIRS:
            hit = directory / candidate
            if hit.exists():
                return hit
            if directory.is_dir():
                found = next(directory.rglob(candidate), None)
                if found:
                    return found
    return None


def font(name, size):
    hit = find(name)
    if hit is None:
        # Falling back to the bitmap default would overwrite a perfectly good
        # committed card with an unreadable one, which is worse than not
        # regenerating at all. main() checks for this before drawing anything.
        raise LookupError(name)
    return ImageFont.truetype(str(hit), size)


def tracked(draw, xy, text, fnt, fill, spacing=0, right=None):
    """Draw text with letter spacing, which PIL has no notion of."""
    widths = [draw.textlength(c, font=fnt) for c in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x, y = xy
    if right is not None:
        x = right - total
    for c, w in zip(text, widths):
        draw.text((x, y), c, font=fnt, fill=fill)
        x += w + spacing
    return total


def wrap(draw, text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


# ------------------------------------------------------------------- data --

def load():
    """The first forecast day, from whichever region makes the better card.

    A confident inversion anywhere beats a merely clear day, because that is
    the thing worth putting in front of someone. Otherwise the region with more
    tops out of cloud wins.
    """
    index_path = WEB / "data" / "index.json"
    if not index_path.exists():
        return None

    best = None
    for entry in json.loads(index_path.read_text(encoding="utf-8"))["regions"]:
        path = WEB / "data" / entry["summary"]
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        hills = data.get("hills") or []
        if not hills:
            continue
        day = sorted(hills[0].get("daily", {}))[0] if hills[0].get("daily") else None
        if not day:
            continue

        rows = [(h, h["daily"][day]) for h in hills if day in h.get("daily", {})]
        if not rows:
            continue

        # The same test the page uses: physics.py only says ABOVE CLOUD once the
        # summit clears the modelled cloud top by more than its own margin.
        above = [(h, s) for h, s in rows if s.get("verdict") == "ABOVE CLOUD"]
        clear = [s for _, s in rows if s.get("view_pct", 0) >= 70]
        tops = sorted(s["cloud_top"] for _, s in (above or rows)
                      if s.get("cloud_top") is not None)

        card = {
            "label": data["meta"]["label"],
            "day": day,
            "total": len(rows),
            "above": len(above),
            "clear": len(clear),
            "deck": tops[len(tops) // 2] if tops else None,
            "score": max((s.get("inversion") or 0) for _, s in rows),
            "named": [h["name"] for h, _ in
                      sorted(above or [r for r in rows if r[1].get("view_pct", 0) >= 70]
                             or rows, key=lambda r: -r[0]["height"])[:2]],
            "bases": sorted(s["cloud_base"] for _, s in rows
                            if s.get("cloud_base") is not None),
            "highest": max(h["height"] for h, _ in rows),
            "best": max(rows, key=lambda r: r[1].get("view_pct", 0)),
            "sunrise": (hills[0].get("sunrise") or {}).get(day),
        }
        rank = (1 if above else 0, len(clear) / len(rows))
        if best is None or rank > best[0]:
            best = (rank, card)

    return best[1] if best else None


def metres(v):
    return f"{v:,} m".replace(",", ",") if v is not None else None


# ------------------------------------------------------------------ scene --

# The ridge from the handoff hero, in its own 1112 x 216 space.
RIDGE = [(0, 206), (55, 192), (130, 120), (195, 152), (258, 86), (320, 142),
         (400, 58), (468, 132), (540, 96), (610, 150), (676, 66), (748, 138),
         (820, 104), (888, 158), (958, 88), (1030, 148), (1112, 196),
         (1112, 208), (0, 208)]
PEAKS = [(400, 58), (676, 66), (958, 88)]

# Every summit in the drawing, tallest first. The deck is placed against these
# rather than against a height in metres: see deck_line.
SUMMITS = sorted([120, 86, 58, 96, 66, 104, 88])


def deck_line(fraction):
    """Where to draw the cloud deck so the picture tells the truth.

    The ridge is a fixed engraving with its own distribution of heights, so
    putting the deck at the day's cloud base in metres draws whatever that
    distribution happens to give: on a Lakeland day with three tops in
    twenty-two clear, a literal section showed four of the seven drawn peaks
    standing proud, over the headline "the tops are in cloud".

    So the deck is placed by proportion instead. If a seventh of the hills are
    out of the cloud, a seventh of the drawn peaks stand above the line, and the
    picture summarises the day rather than contradicting it.
    """
    n = round(len(SUMMITS) * max(0.0, min(1.0, fraction)))
    if n <= 0:
        return SUMMITS[0] - 14           # everything buried
    if n >= len(SUMMITS):
        return SUMMITS[-1] + 24          # everything clear
    return (SUMMITS[n - 1] + SUMMITS[n]) / 2


def scene(img, draw, x0, y0, width, deck_y, labels, sun):
    """The section drawing: ridge, cloud deck, dashed line, labelled peaks.

    Static, per the handoff: a share card has no animation to fall back from.
    """
    k = width / 1112
    px = lambda p: (x0 + p[0] * k, y0 + p[1] * k)

    draw.polygon([px(p) for p in RIDGE], fill=RELIEF, outline=INK)

    # The deck, drawn over the ridge so summits above it stay visible and
    # summits below it are swallowed, which is the whole idea of the site.
    dy = y0 + deck_y * k
    bottom = y0 + 206 * k
    if bottom > dy:
        # Size the overlay from the crop box rather than from the floats, or the
        # two disagree by a pixel and alpha_composite refuses them.
        box = (int(x0), int(dy), int(x0 + width), int(bottom))
        band = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), DECK + (240,))
        img.paste(Image.alpha_composite(
            img.crop(box).convert("RGBA"), band).convert("RGB"), box[:2])

    for x in range(int(x0), int(x0 + width), 11):
        draw.line([(x, dy), (x + 5, dy)], fill=FAINT, width=2)

    if sun:
        draw.ellipse([x0 + 59 * k, y0 + 21 * k, x0 + 85 * k, y0 + 47 * k],
                     outline=OCHRE, width=2)

    small = font("georgia.ttf", 17)
    for (peak, name) in zip(PEAKS, labels):
        lx, ly = px(peak)
        tracked(draw, (lx - 12, ly - 26), name.upper(), small, INK, spacing=1.5)


# ------------------------------------------------------------------- card --

def main():
    if find("georgia.ttf") is None:
        print("no serif font found; keeping the existing card.\n"
              "  Install one (apt: fonts-dejavu-core, apk: font-dejavu) to let "
              "this run on the server.")
        return
    card = load()
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    right = W - PAD_X
    inversion = bool(card and card["above"])

    # Masthead bar and the double rule.
    tracked(d, (PAD_X, PAD_TOP), "HILL WEATHER", font("georgiab.ttf", 19), INK,
            spacing=4)
    if card:
        # %-d is not portable to Windows, so the leading zero comes off by hand.
        stamp = datetime.fromisoformat(card["day"])
        when = f'{stamp.strftime("%A")} {stamp.day} {stamp.strftime("%B")}'
        tracked(d, (0, PAD_TOP + 2), f"{card['label'].upper()}  {when.upper()}",
                font("georgia.ttf", 18), MUTED, spacing=3.6, right=right)
    y = PAD_TOP + 34
    d.rectangle([PAD_X, y, right, y + 2], fill=INK)
    d.rectangle([PAD_X, y + 5, right, y + 6], fill=INK)

    y += 28
    if inversion:
        tracked(d, (PAD_X, y), f"CLOUD INVERSION  SCORE {card['score']} OF 100",
                font("georgiab.ttf", 18), OCHRE, spacing=4.2)
        y += 34

    head = font("georgiai.ttf", 66)
    if not card:
        headline = "Will the summit be in cloud, above it, or clear?"
    elif inversion:
        headline = "Above the cloud."
    elif card["clear"] == 0:
        headline = "In cloud everywhere."
    elif card["clear"] / card["total"] >= 0.7:
        headline = "Clear on almost every top."
    else:
        headline = "The tops are in cloud."

    for line in wrap(d, headline, head, right - PAD_X):
        d.text((PAD_X, y), line, font=head, fill=INK)
        y += 74

    y += 6
    body = font("georgia.ttf", 21)
    if not card:
        standfirst = ("A free cloud base and inversion forecast for every Munro "
                      "and every Wainwright.")
    elif inversion:
        deck = metres(card["deck"])
        standfirst = (f"{card['above']} of {card['total']} tops stand clear above a "
                      f"white sea" + (f", cloud top about {deck}." if deck else "."))
    elif card["bases"]:
        lo, hi = card["bases"][0], card["bases"][-1]
        standfirst = (f"{card['clear']} of {card['total']} tops should stay out of "
                      f"the cloud. Base runs {metres(lo)} to {metres(hi)}.")
    else:
        standfirst = f"{card['clear']} of {card['total']} tops should stay out of the cloud."

    for line in wrap(d, standfirst, body, 820):
        d.text((PAD_X, y), line, font=body, fill=MUTED)
        y += 30

    # The key stats row from the handoff. It fills the space the headline leaves
    # and, more usefully, puts a named hill on the card: "3 of 22" tells you the
    # shape of the day, "Haystacks 78%" tells you where to go.
    if card:
        best_hill, best_day = card["best"]
        stats = ([("TOPS ABOVE CLOUD", f"{card['above']} of {card['total']}", True),
                  ("CLOUD TOP", metres(card["deck"]) or "not resolved", False)]
                 if inversion else
                 [("TOPS CLEAR", f"{card['clear']} of {card['total']}", False),
                  ("CLOUD BASE",
                   f"{metres(card['bases'][0])} to {metres(card['bases'][-1])}"
                   if card["bases"] else "little about", False)])
        stats.append(("BEST OF THEM",
                      f"{best_hill['name']} {best_day.get('view_pct', 0)}%", False))
        if card["sunrise"]:
            stats.append(("SUNRISE", card["sunrise"][11:16], False))

        y += 22
        cap, val = font("georgia.ttf", 15), font("georgia.ttf", 27)
        col = (right - PAD_X) / len(stats)
        for i, (k, v, ochre) in enumerate(stats):
            x = PAD_X + i * col
            if i:
                d.rectangle([x - 20, y + 2, x - 19, y + 46], fill=RULE)
            tracked(d, (x, y), k, cap, FAINT, spacing=3)
            d.text((x, y + 22), v, font=val, fill=OCHRE if ochre else INK)
        y += 52

    # The drawing sits on the footer rule, whatever the copy above it did.
    foot_rule = H - PAD_BOT - 46
    scene_w = right - PAD_X
    scene_h = scene_w * 216 / 1112
    scene_y = foot_rule - 16 - scene_h

    if card:
        clear = card["above"] if inversion else card["clear"]
        deck_y = deck_line(clear / card["total"])
    else:
        deck_y = deck_line(2 / 7)

    scene(img, d, PAD_X, scene_y, scene_w, deck_y,
          (card["named"] if card else [])[:2], sun=inversion)

    d.rectangle([PAD_X, foot_rule, right, foot_rule + 1], fill=RULE)
    tracked(d, (PAD_X, foot_rule + 14), "HILLWEATHER.CO.UK",
            font("georgiab.ttf", 21), OCHRE, spacing=3.4)
    tracked(d, (0, foot_rule + 17), "free \u00b7 no accounts \u00b7 a chance, not a promise",
            font("georgiai.ttf", 18), FAINT, spacing=0, right=right)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    kind = "inversion" if inversion else ("forecast" if card else "generic")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} kB, {W}x{H}, {kind})")


if __name__ == "__main__":
    main()
