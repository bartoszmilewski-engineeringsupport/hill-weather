#!/usr/bin/env python3
"""
Stamp a content hash onto the stylesheet and script URLs.

Run after changing any CSS or JS, then commit the result.

    python scripts/version_assets.py

Why this exists. Caching a stylesheet for hours is correct; serving an OLD
stylesheet against NEW markup is not, and that is what happens when the two
ship together under one filename. It produced a site with giant icons, an
unstyled search box and a collapsed nav, all of which looked like code bugs
and were not.

The usual advice is to tell the CDN to respect the origin's cache headers, but
that setting is not available on every plan, and depending on a dashboard
toggle to keep the site correct is fragile. Changing the URL when the content
changes needs no cooperation from anyone: every cache in the chain, browser,
CDN and proxy alike, treats it as a new file because it is one.
"""

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
ASSETS = ["style.css", "glyph.js", "theme.js", "share.js"]
PAGES = ["index.html", "how-to-read.html", "contact.html"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def main():
    versions = {}
    for name in ASSETS:
        p = WEB / name
        if p.exists():
            versions[name] = digest(p)
        else:
            print(f"  {name}: missing, skipped")

    changed = 0
    for page in PAGES:
        p = WEB / page
        if not p.exists():
            continue
        text = original = p.read_text(encoding="utf-8")
        for name, ver in versions.items():
            stem = re.escape(name)
            # Match the bare name or an existing stamp, so re-running is safe.
            text = re.sub(rf'(["\'/]){stem}(\?v=[0-9a-f]+)?(["\'])',
                          rf'\g<1>{name}?v={ver}\g<3>', text)
        if text != original:
            # Explicit LF. This script runs on Windows and rewrites files that
            # are committed, so the platform default would leave every page
            # showing as modified after a run that changed nothing.
            p.write_text(text, encoding="utf-8", newline=chr(10))
            changed += 1
        print(f"  {page}: {'updated' if text != original else 'already current'}")

    print()
    for name, ver in versions.items():
        print(f"  {name:12} -> ?v={ver}")
    print(f"\n{changed} page(s) rewritten")


if __name__ == "__main__":
    main()
