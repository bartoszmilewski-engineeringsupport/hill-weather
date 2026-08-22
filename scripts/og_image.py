#!/usr/bin/env python3
"""
Generate the link preview image.

Pasting the site into a walking group is the entire growth model, so what
appears in that message matters as much as the page itself. Without this, a
link is a bare URL.

Run once, or after a design change; the result is committed.

    python scripts/og_image.py

1200x630 is the size every platform crops from. Everything important stays
well inside the middle, because Twitter, WhatsApp and Slack all crop
differently and none of them tell you how.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "og.png"

W, H = 1200, 630
PAPER = (251, 247, 240)
INK = (42, 37, 33)
OCHRE = (168, 118, 63)
MUTED = (107, 97, 86)
RELIEF = (237, 229, 215)
RELIEF_LINE = (201, 188, 163)
CLOUD = (185, 174, 153)

# Georgia is the closest thing on hand to Newsreader: a warm serif with real
# weight. The face only has to feel like the site, not match it exactly.
FONTS = Path("C:/Windows/Fonts")


def font(name, size):
    for candidate in (FONTS / name, Path("/usr/share/fonts/truetype/msttcorefonts") / name):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default(size)


def tracked(draw, xy, text, fnt, fill, spacing=0, centre_width=None):
    """Draw text with letter spacing, which PIL has no notion of."""
    widths = [draw.textlength(c, font=fnt) for c in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x, y = xy
    if centre_width:
        x = (centre_width - total) / 2
    for c, w in zip(text, widths):
        draw.text((x, y), c, font=fnt, fill=fill)
        x += w + spacing
    return total


def centre(draw, y, text, fnt, fill):
    w = draw.textlength(text, font=fnt)
    draw.text(((W - w) / 2, y), text, font=fnt, fill=fill)


def main():
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    pad = 84
    d.rectangle([pad, 74, W - pad, 78], fill=INK)

    centre(d, 108, "Hill Weather", font("georgia.ttf", 104), INK)

    tracked(d, (0, 246), "CLOUD BASE & INVERSIONS FOR BRITISH HILLS",
            font("georgia.ttf", 25), OCHRE, spacing=5.5, centre_width=W)

    d.rectangle([pad, 300, W - pad, 302], fill=INK)

    # One line rather than two: it leaves the glyph room to breathe, and the
    # glyph is doing more work here than a second line of text would.
    centre(d, 338, "Will the summit be in cloud, above it, or clear?",
           font("georgia.ttf", 42), INK)

    # The glyph from the site: a hill in section with the cloud layer across
    # it, drawn in the good case, standing clear above the deck.
    cx, ground, half = W // 2, 508, 168
    hill = [(cx - half, ground), (cx - 62, ground - 62), (cx - 12, ground - 26),
            (cx + 56, ground - 88), (cx + half, ground)]
    d.polygon(hill, fill=RELIEF, outline=RELIEF_LINE)

    # Cloud sits BELOW the higher summit, which is the whole point of the site.
    top, bottom = ground - 54, ground - 8
    band = Image.new("RGBA", (half * 2, bottom - top), CLOUD + (108,))
    box = (cx - half, top, cx + half, bottom)
    img.paste(Image.alpha_composite(
        img.crop(box).convert("RGBA"), band).convert("RGB"), (cx - half, top))
    for x in range(cx - half, cx + half, 11):
        d.line([(x, top), (x + 5, top)], fill=(140, 129, 117), width=2)

    d.rectangle([pad, H - 96, W - pad, H - 93], fill=INK)
    centre(d, H - 78, "hillweather.co.uk", font("georgiab.ttf", 32), INK)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} kB, {W}x{H})")


if __name__ == "__main__":
    main()
