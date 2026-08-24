#!/usr/bin/env python3
"""
Build the static forecast files the website reads.

Two sources, same code path:

  live (default)  fetch all 496 Munros and Wainwrights. This is production.
  --file          rebuild from an archived day. This is the backtest harness -
                  once the constants in physics.py are tuned, every archived
                  day can be re-scored without refetching anything.

    python scripts/build.py                        # live, all regions
    python scripts/build.py --region lakes
    python scripts/build.py --file archive/lakes/2026-08-22T08Z.json.gz

Writes data/<region>.json and data/index.json. Those are the only files the
website needs - phones never call the weather API, which is what keeps this
inside the free tier however many users it has.
"""

import argparse
import gzip
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import omfetch                                  # noqa: E402
import solar                                    # noqa: E402
from physics import summit_conditions           # noqa: E402
from hills import REGIONS, DOBIH_VERSION, load_hills   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "sources.json"
# Output lives inside the web root so the path is identical in dev and
# production: the site always fetches "data/...", never "../data/...".
DATA = ROOT / "web" / "data"
ALGORITHM_VERSION = 1
FORECAST_DAYS = 3


def from_archive(path):
    with gzip.open(path, "rb") as f:
        p = json.loads(f.read())
    return p["meta"], p["hills"], p["responses"]


def from_live(region):
    hills = load_hills(region)
    responses = omfetch.fetch_hills(
        hills, forecast_days=FORECAST_DAYS,
        variables=omfetch.all_variables(minimal=True), pause=3.0)
    meta = {
        "fetched_utc": datetime.now(timezone.utc).replace(
            microsecond=0).isoformat(),
        "region": region,
        "label": REGIONS[region]["label"],
        "subset": "full",
        "model": omfetch.MODEL,
        "levels_hpa": omfetch.LEVELS,
        "dobih_version": DOBIH_VERSION,
        "attribution": omfetch.ATTRIBUTION,
    }
    return meta, [h._asdict() for h in hills], responses


def load_sources():
    """Wikipedia extracts and Walkhighlands links, cached by scripts/sources.py.

    Read from disk rather than fetched: mountains do not change, and the
    twice-daily build has no business hitting either site.
    """
    if not SOURCES.exists():
        return {}
    try:
        return json.loads(SOURCES.read_text(encoding="utf-8")).get("hills", {})
    except ValueError:
        return {}


def enrich(hill_defs, region):
    """Fill in static hill facts from the current DoBIH.

    Grid references, county and list membership do not change with the weather,
    so they are joined at build time rather than frozen into the archive. That
    also means an archive written before a field existed still rebuilds into a
    complete page, which matters for backtests.
    """
    try:
        current = {h.name: h._asdict() for h in load_hills(region)}
    except Exception:                              # noqa: BLE001
        return hill_defs
    out = []
    for hill in hill_defs:
        ref = current.get(hill["name"])
        if ref:
            hill = {**ref, **{k: v for k, v in hill.items() if v is not None}}
        out.append(hill)
    return out


def build(meta, hill_defs, responses, source):
    levels = meta["levels_hpa"]
    hill_defs = enrich(hill_defs, meta["region"])
    sources = load_sources()
    hills_out = []

    for hill, resp in zip(hill_defs, responses):
        hourly = resp.get("hourly")
        if not hourly:
            continue

        hours = [c for c in
                 (summit_conditions(hourly, i, hill, levels)
                  for i in range(len(hourly["time"])))
                 if c]
        if not hours:
            continue

        dates = sorted({h["t"][:10] for h in hours})
        sun = {d: solar.day_summary(datetime.fromisoformat(d).date(),
                                    hill["lat"], hill["lon"])
               for d in dates}

        entry = {
            "name": hill["name"],
            "lat": hill["lat"], "lon": hill["lon"], "height": hill["height"],
            "sun": sun,
            "hours": hours,
        }
        # Optional and read with .get() so archives written before these fields
        # existed still rebuild cleanly.
        for extra in ("alt", "prominence", "area", "lists", "county",
                      "country", "grid_ref", "map50", "feature", "url"):
            if hill.get(extra) is not None:
                entry[extra] = hill[extra]

        src = sources.get(f"{meta['region']}/{hill['name']}") or {}
        if src.get("wikipedia"):
            entry["wikipedia"] = src["wikipedia"]
        if src.get("walkhighlands"):
            entry["walkhighlands"] = src["walkhighlands"]
        hills_out.append(entry)

    # Per-day summary so the front page can rank without walking every hour.
    #
    # Light quality is only meaningful near sunrise and sunset - a good score at
    # midday means nothing - so it is sampled at those hours rather than maxed
    # across the day. Dawn and dusk are separate because they routinely differ.
    for h in hills_out:
        by_hour = {hr["t"]: hr for hr in h["hours"]}
        daily = {}
        for date, sun in h["sun"].items():
            day_hours = [hr for hr in h["hours"] if hr["t"][:10] == date]
            if not day_hours:
                continue
            daylight = [hr for hr in day_hours if 6 <= int(hr["t"][11:13]) <= 20]

            def at(iso_time):
                if not iso_time:
                    return None
                return by_hour.get(f"{iso_time[:13]}:00")

            dawn, dusk = at(sun["sunrise"]), at(sun["sunset"])

            # The headline number is the AVERAGE across the hours people are
            # actually on the tops, not the day's luckiest hour. Taking the max
            # made a hill that sits in cloud all day read as 95%.
            walking = [hr for hr in day_hours if 9 <= int(hr["t"][11:13]) <= 17]
            views = [hr["view_pct"] for hr in walking] or \
                    [hr["view_pct"] for hr in daylight]
            # A representative midday snapshot so the ranked list can describe
            # the day without pulling the hill's full hourly file.
            midday = by_hour.get(f"{date}T12:00") or day_hours[len(day_hours) // 2]

            # Wind and rain over the same walking hours as the view figure.
            #
            # These are fetched and stored per hour but were never carried into
            # the summary, so the ranked list could not show or sort by them and
            # a walker had to open a hill to discover it was blowing. Gust is
            # the max rather than the mean: what turns a party back is the worst
            # gust on the ridge, not the average of a comfortable afternoon.
            # Measured across ten Scottish summits on one day, peak gust ran
            # from 17 to 36 mph, so this genuinely separates hills.
            def over(field, hours):
                vals = [hr.get(field) for hr in hours if hr.get(field) is not None]
                return vals

            wind_hours = walking or daylight
            gusts = over("gust", wind_hours)
            winds = over("wind", wind_hours)
            rain = over("precip", wind_hours)

            daily[date] = {
                "view_pct": round(sum(views) / len(views)) if views else 0,
                "view_best": max(views, default=0),
                "view_worst": min(views, default=0),
                "verdict": midday["verdict"],
                "cloud_base": midday["cloud_base"],
                "cloud_top": midday["cloud_top"],
                # Carried in the summary so the front page can write its own
                # opening paragraph without pulling any hill's hourly file.
                "freezing_level": midday["freezing_level"],
                "inversion": max((hr["inversion"] for hr in daylight), default=0),
                "inversion_dawn": dawn["inversion"] if dawn else None,
                "light_dawn": dawn["light"] if dawn else None,
                "light_dusk": dusk["light"] if dusk else None,
                "gust_max": max(gusts) if gusts else None,
                "wind_avg": round(sum(winds) / len(winds)) if winds else None,
                "wind_dir": midday.get("wind_dir"),
                "precip_mm": round(sum(rain), 1) if rain else 0,
            }
        h["daily"] = daily

    hills_out.sort(key=lambda h: -h["height"])

    return {
        "meta": {
            "generated_utc": datetime.now(timezone.utc).replace(
                microsecond=0).isoformat(),
            "forecast_fetched_utc": meta["fetched_utc"],
            "region": meta["region"],
            "label": meta["label"],
            "subset": meta.get("subset", "full"),
            "model": meta["model"],
            "algorithm_version": ALGORITHM_VERSION,
            "source": source,
            "attribution": {
                **meta.get("attribution", omfetch.ATTRIBUTION),
                "descriptions": ("Wikipedia, CC BY-SA 4.0"),
                "routes": ("Walkhighlands, linked only "
                           "- https://www.walkhighlands.co.uk"),
            },
            "disclaimer": ("Planning aid only. Not a substitute for MWIS "
                           "(mwis.org.uk) or, in winter, SAIS (sais.gov.uk)."),
            # Height bands for display, defined per region in hills.py. Sent
            # with the data so the page does not need its own copy to drift.
            "bands": REGIONS.get(meta["region"], {}).get("bands", []),
            # Nav label for narrow screens, where the full one will not fit.
            "short": REGIONS.get(meta["region"], {}).get("short")
                     or meta["label"],
            # Vertical scale the elevation glyph draws against.
            "scale": REGIONS.get(meta["region"], {}).get("scale", 1600),
        },
        "hills": hills_out,
    }


def slugify(name, seen):
    """URL-safe filename, unique within a region.

    DoBIH has genuine duplicates - there are two Munros called Ben More - so
    collisions get the height appended rather than silently overwriting.
    """
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if s in seen:
        s = f"{s}-{seen[s]}"
    seen[s] = seen.get(s, 0) + 1
    return s


def write_region(out, out_dir):
    """Split into a small summary plus one file per hill.

    A single 5MB file is unusable on one bar of signal in a car park. The
    summary is everything the ranked list needs and nothing else; hourly detail
    is fetched only when someone actually taps a hill.
    """
    region = out["meta"]["region"]
    region_dir = out_dir / region
    hills_dir = region_dir / "hills"
    hills_dir.mkdir(parents=True, exist_ok=True)

    seen, summary_hills = {}, []
    for h in out["hills"]:
        slug = slugify(h["name"], seen)

        detail = dict(h, slug=slug, meta=out["meta"])
        (hills_dir / f"{slug}.json").write_text(
            json.dumps(detail, separators=(",", ":")), encoding="utf-8")

        # Only what the list renders: name, height, and the day summaries.
        summary_hills.append({
            "slug": slug, "name": h["name"], "height": h["height"],
            # Carried so search can find a hill by its Gaelic name:
            # "Beinn Nibheis" should return Ben Nevis.
            "alt": h.get("alt"),
            "lat": h["lat"], "lon": h["lon"],
            "prominence": h.get("prominence"),
            "area": h.get("area"),
            "daily": h["daily"],
            "sunrise": {d: s["sunrise"] for d, s in h["sun"].items()},
        })

    summary = {"meta": out["meta"], "hills": summary_hills}
    text = json.dumps(summary, separators=(",", ":"))
    (region_dir / "summary.json").write_text(text, encoding="utf-8")

    detail_bytes = sum(f.stat().st_size for f in hills_dir.glob("*.json"))
    return len(text), detail_bytes, len(summary_hills)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", action="append", help="region(s) to build")
    ap.add_argument("--file", help="rebuild from an archived file (backtest)")
    ap.add_argument("--out", default=None, help="output directory")
    args = ap.parse_args()

    out_dir = Path(args.out) if args.out else DATA
    out_dir.mkdir(parents=True, exist_ok=True)
    built = []

    if args.file:
        path = Path(args.file)
        jobs = [(from_archive(path), f"archive:{path.name}")]
    else:
        jobs = [(from_live(r), "live")
                for r in (args.region or sorted(REGIONS))]

    for (meta, hill_defs, responses), source in jobs:
        out = build(meta, hill_defs, responses, source)
        region = out["meta"]["region"]
        summary_bytes, detail_bytes, n = write_region(out, out_dir)
        n_hours = len(out["hills"][0]["hours"]) if out["hills"] else 0
        print(f"  {region:9} {n:4} hills  {n_hours:3} hours   "
              f"summary {summary_bytes / 1e3:6.1f} kB   "
              f"detail {detail_bytes / 1e6:5.2f} MB across {n} files")
        built.append({
            "region": region,
            "label": out["meta"]["label"],
            "summary": f"{region}/summary.json",
            "hills": n,
            "generated_utc": out["meta"]["generated_utc"],
        })

    if built:
        # Merge rather than overwrite: building one region at a time (which the
        # backtest path does) must not drop the others from the index.
        index_path = out_dir / "index.json"
        existing = {}
        if index_path.exists():
            try:
                existing = {r["region"]: r for r in
                            json.loads(index_path.read_text())["regions"]}
            except (ValueError, KeyError):
                pass
        existing.update({r["region"]: r for r in built})
        # Site order, not alphabetical: Scotland leads. The page then remembers
        # whichever region the reader last chose.
        regions = sorted(existing.values(),
                         key=lambda r: (REGIONS.get(r["region"], {}).get("order", 99),
                                        r["region"]))
        index_path.write_text(json.dumps({"regions": regions}, indent=2),
                              encoding="utf-8")
        print(f"  {'index':9} -> {index_path.name} "
              f"({', '.join(r['region'] for r in regions)})")


if __name__ == "__main__":
    main()
