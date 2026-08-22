#!/usr/bin/env python3
"""
Forecast archiver - the validation clock.

Stores the RAW Open-Meteo response, unmodified. This is deliberate: if we
archived our own derived answers ("Ben Nevis, in cloud, base 632m") then every
change to RH_MOIST or CLEAR_MARGIN would invalidate the whole archive. Keeping
raw model output means any future version of the algorithm can be re-scored
against every day we have ever collected.

Archives the VALIDATION SUBSET only - about 40 hills we can get ground truth
for. The full 496-hill forecast is fetched live by build.py and never
accumulated, which keeps a year of archive at ~70MB instead of ~840MB.

    python scripts/archive.py            # every region
    python scripts/archive.py scotland   # one region
    python scripts/archive.py --status   # what has been collected so far

Data: Open-Meteo (https://open-meteo.com), UK Met Office 2km deterministic model.
"""

import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import omfetch                                          # noqa: E402
from hills import REGIONS, DOBIH_VERSION, load_hills    # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "archive"
FORECAST_DAYS = 3


def archive_region(region, force=False):
    hills = load_hills(region, validation=True)
    now = datetime.now(timezone.utc)
    out_dir = ARCHIVE / region
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{now:%Y-%m-%dT%H}Z.json.gz"

    if path.exists() and not force:
        print(f"  {region:9} already archived this hour -> {path.name}")
        return path

    responses = omfetch.fetch_hills(hills, forecast_days=FORECAST_DAYS)

    payload = {
        "meta": {
            "fetched_utc": now.isoformat(),
            "region": region,
            "label": REGIONS[region]["label"],
            "subset": "validation",
            "model": omfetch.MODEL,
            "forecast_days": FORECAST_DAYS,
            "levels_hpa": omfetch.LEVELS,
            "variables": omfetch.all_variables(),
            "dobih_version": DOBIH_VERSION,
            "attribution": omfetch.ATTRIBUTION,
            "schema": 1,
        },
        # The hill list travels with the data so the archive stays readable
        # even after the list changes.
        "hills": [h._asdict() for h in hills],
        "responses": responses,
    }

    raw = json.dumps(payload, separators=(",", ":")).encode()
    with gzip.open(path, "wb", compresslevel=9) as f:
        f.write(raw)

    print(f"  {region:9} {len(hills):3} hills  "
          f"{len(raw) / 1e6:5.1f} MB raw -> {path.stat().st_size / 1e6:4.2f} MB gz  "
          f"{path.name}")
    return path


def status():
    if not ARCHIVE.exists():
        print("no archive yet")
        return
    all_days, total_files, total_bytes = set(), 0, 0
    for region in sorted(REGIONS):
        d = ARCHIVE / region
        files = sorted(d.glob("*.json.gz")) if d.exists() else []
        size = sum(f.stat().st_size for f in files)
        days = {f.name[:10] for f in files}
        all_days |= days
        total_files += len(files)
        total_bytes += size
        span = f"{files[0].name[:10]} .. {files[-1].name[:10]}" if files else "-"
        print(f"  {region:9} {len(files):4} runs  {len(days):3} days  "
              f"{size / 1e6:6.1f} MB   {span}")
    print(f"  {'TOTAL':9} {total_files:4} runs  {len(all_days):3} days  "
          f"{total_bytes / 1e6:6.1f} MB")
    if all_days:
        per_day = total_bytes / len(all_days)
        print(f"\n  ~{per_day / 1e6:.2f} MB/day -> ~{per_day * 365 / 1e6:.0f} MB/year")


def main():
    args = sys.argv[1:]
    if "--status" in args:
        status()
        return
    force = "--force" in args
    wanted = [a for a in args if not a.startswith("-")] or sorted(REGIONS)
    print(f"archiving {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC  "
          f"model={omfetch.MODEL}")
    for region in wanted:
        archive_region(region, force=force)


if __name__ == "__main__":
    main()
