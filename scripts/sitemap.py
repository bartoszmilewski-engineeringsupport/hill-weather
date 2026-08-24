#!/usr/bin/env python3
"""
Generate sitemap.xml and robots.txt.

    python scripts/sitemap.py

Pages are discovered from web/*.html and their URLs are read from each page's
own <link rel="canonical">, so the sitemap cannot drift from what the pages
claim about themselves. A page with no canonical is skipped loudly rather than
guessed at.

lastmod is honest rather than flattering. Search engines demote sites that
claim everything changed today, so a page's date is the last time its content
actually moved: the forecast generation time for the two pages that render the
forecast, and the file's own git commit date for the ones that do not.

robots.txt deliberately allows /data/. The forecast is rendered in the browser
from those JSON files, so a crawler blocked from them would render an empty
page and index a site with no content on it. Only /api/, which is the contact
handler and has nothing to index, is disallowed.
"""

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
SITE = "https://hillweather.co.uk"

# Deliberately not in the sitemap: it carries noindex and exists to be served
# with a 404 status, so listing it would be a contradiction.
EXCLUDE = {"404.html"}

# Pages whose visible content is the forecast, so their freshness is the
# forecast's freshness rather than the HTML file's.
DATA_DRIVEN = {"index.html", "week.html"}

# Roughly how often the content changes, and how each page ranks against the
# others. The forecast is the site; everything else supports it.
PRIORITY = {"index.html": ("1.0", "daily"),
            "week.html": ("0.8", "daily"),
            "how-to-read.html": ("0.5", "monthly"),
            "contact.html": ("0.3", "yearly")}


def canonical(html):
    m = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', html)
    return m.group(1) if m else None


def git_date(path):
    """When this file's content last changed, from git."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(path)],
            cwd=ROOT, capture_output=True, text=True, timeout=15)
        stamp = out.stdout.strip()
        if stamp:
            return stamp[:10]
    except Exception:
        pass
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date().isoformat()


def forecast_date():
    """When the forecast was last built, if there is one to ask."""
    index = WEB / "data" / "index.json"
    if not index.exists():
        return None
    import json
    try:
        regions = json.loads(index.read_text(encoding="utf-8"))["regions"]
        stamps = [r.get("generated_utc") for r in regions if r.get("generated_utc")]
        return max(stamps)[:10] if stamps else None
    except Exception:
        return None


def main():
    built = forecast_date()
    entries, skipped = [], []

    for page in sorted(WEB.glob("*.html")):
        if page.name in EXCLUDE:
            continue
        html = page.read_text(encoding="utf-8")
        url = canonical(html)
        if not url:
            skipped.append(page.name)
            continue
        when = built if (page.name in DATA_DRIVEN and built) else git_date(page)
        priority, freq = PRIORITY.get(page.name, ("0.5", "monthly"))
        entries.append((url, when, freq, priority))

    # One entry per hill. These are the reason the sitemap exists: without
    # them the site offers search engines four pages for 546 hills. They are
    # rebuilt with every forecast, so their lastmod is the build date.
    hill_pages = sorted((ROOT / "web" / "hill").rglob("*.html"))
    for page in hill_pages:
        url = canonical(page.read_text(encoding="utf-8"))
        if url:
            entries.append((url, built or git_date(page), "daily", "0.6"))
    if hill_pages:
        print(f"   plus {len(hill_pages)} hill pages")

    entries.sort(key=lambda e: (-float(e[3]), e[0]))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, when, freq, priority in entries:
        lines += ["  <url>",
                  f"    <loc>{url}</loc>",
                  f"    <lastmod>{when}</lastmod>",
                  f"    <changefreq>{freq}</changefreq>",
                  f"    <priority>{priority}</priority>",
                  "  </url>"]
    lines.append("</urlset>")
    (WEB / "sitemap.xml").write_text("\n".join(lines) + "\n",
                                     encoding="utf-8", newline="\n")

    robots = f"""# Hill Weather

User-agent: *
Allow: /

# The contact handler. Nothing to index, and no reason to crawl it.
Disallow: /api/

# /data/ is deliberately NOT blocked. The forecast is rendered in the browser
# from those JSON files, so a crawler shut out of them would render an empty
# page and index a site with no content on it.

Sitemap: {SITE}/sitemap.xml
"""
    (WEB / "robots.txt").write_text(robots, encoding="utf-8", newline="\n")

    print(f"sitemap.xml: {len(entries)} pages"
          + (f", forecast dated {built}" if built else ", no forecast data present"))
    for url, when, freq, priority in entries[:6]:
        print(f"   {priority}  {when}  {freq:8} {url}")
    if len(entries) > 6:
        print(f"   ... and {len(entries) - 6} more")
    if skipped:
        print(f"\n  SKIPPED, no <link rel=canonical>: {', '.join(skipped)}")
    print("robots.txt: written")


if __name__ == "__main__":
    main()
