#!/usr/bin/env python3
"""
Regenerate the README screenshots from the live site.

    python scripts/screenshots.py                 # live site
    python scripts/screenshots.py --url http://localhost:8000

Uses headless Chrome, which is on any Windows or Mac dev machine and is a
package away on Linux. Nothing here runs in production: the screenshots are
documentation, committed so GitHub has something to show without a build step.

Two things make this work where a naive --screenshot does not:

  --virtual-time-budget waits for the page to fetch its data and draw. The
  forecast is rendered in the browser, so a plain screenshot catches the
  "Loading the forecast..." state instead of the site.

  --blink-settings=preferredColorScheme pins light or dark. The site follows
  the device by design and stores an override in localStorage, neither of
  which a command line can reach, but the Blink setting underneath both can
  be set directly.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"

CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "chromium", "chromium-browser",
]

LIGHT, DARK = 1, 2

#  file                 path              width height scheme
SHOTS = [
    ("forecast-light.png", "/",                 1360, 1180, LIGHT),
    ("forecast-dark.png",  "/",                 1360, 1180, DARK),
    ("week-light.png",     "/week.html",        1360, 1000, LIGHT),
    ("guide-light.png",    "/how-to-read.html", 1360, 1150, LIGHT),
    ("phone-light.png",    "/",                  390,  844, LIGHT),
    ("phone-dark.png",     "/",                  390,  844, DARK),
]


def find_browser():
    for c in CANDIDATES:
        if Path(c).exists():
            return c
        found = shutil.which(c)
        if found:
            return found
    sys.exit("No Chrome or Edge found. Install one, or pass --browser.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://hillweather.co.uk",
                    help="site to capture (default: the live site)")
    ap.add_argument("--browser", default=None)
    ap.add_argument("--wait", type=int, default=15000,
                    help="virtual time budget in ms, for data fetch and paint")
    args = ap.parse_args()

    browser = args.browser or find_browser()
    base = args.url.rstrip("/")
    OUT.mkdir(parents=True, exist_ok=True)
    # A throwaway profile: a real one may carry a stored theme, which would
    # silently override the scheme being asked for.
    profile = OUT / ".chrome-profile"

    failures = 0
    print(f"{browser}\n{base}\n")
    for name, path, w, h, scheme in SHOTS:
        dest = OUT / name
        cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
               f"--user-data-dir={profile}",
               f"--window-size={w},{h}",
               f"--blink-settings=preferredColorScheme={scheme}",
               f"--virtual-time-budget={args.wait}",
               f"--screenshot={dest}", base + path]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            print(f"  {name:22} TIMED OUT")
            failures += 1
            continue
        size = dest.stat().st_size if dest.exists() else 0
        theme = "light" if scheme == LIGHT else "dark"
        print(f"  {name:22} {w}x{h:<5} {theme:5} {size // 1024:>4} kB"
              + ("" if size else "   FAILED"))
        if not size:
            failures += 1
            print("     ", (r.stderr or r.stdout)[-300:])

    shutil.rmtree(profile, ignore_errors=True)
    if failures:
        sys.exit(f"\n{failures} screenshot(s) failed")
    print(f"\n{len(SHOTS)} written to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
