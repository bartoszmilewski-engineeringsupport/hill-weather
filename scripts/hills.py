#!/usr/bin/env python3
"""
Hill lists, loaded from the Database of British and Irish Hills.

Two different lists, for two different jobs:

  FULL       - every Munro (282) and Wainwright (214). What the app forecasts.
               Fetched live at build time, never accumulated on disk.
  VALIDATION - ~40 hills chosen because we can get ground truth for them
               (webcams, and the Lake District Fell Top Assessor on Helvellyn).
               Archived daily and kept forever. Small enough to live in git.

Keeping those separate is what stops the archive turning into a gigabyte of
git history a year while still letting us score the forecast honestly.

Data: DoBIH v18.5, CC-BY-4.0.
Attribution required wherever this is displayed:
  The Database of British and Irish Hills v18.5
  https://www.hill-bagging.co.uk/dobih
"""

import csv
import io
import re
import zipfile
from collections import namedtuple
from pathlib import Path

Hill = namedtuple("Hill", "name region lat lon height alt prominence area "
                          "lists county country grid_ref map50 feature url")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DOBIH_CSV = DATA_DIR / "DoBIH_v18_5.csv"
DOBIH_ZIP = DATA_DIR / "hillcsv.zip"
DOBIH_VERSION = "v18.5"

# DoBIH marks list membership with a 1 in a single-letter column.
#
# `bands` groups hills by height for display. Without this the ranked list is
# topped by whichever fells are small enough to sit below the cloud, which is
# arithmetically correct and useless: nobody drives to the Lakes for a 335m
# fell. Banding tells the real story instead, which is usually "the tops are
# in cloud but the low fells are clear".
#
# Thresholds differ by region because the lists do. Every Munro is above 914m,
# so Scotland bands the big hills against each other; Wainwrights run from
# 290m to 978m, which is where the problem actually shows up.
#
# `area_column` is the geographic grouping. DoBIH fills different columns for
# the two lists: Munros carry SMC section names in Region, Wainwrights carry
# Wainwright's own fell groups in Area.
# `order` sets which region leads on the site. Scotland first because it is
# where most of the hills are and where the forecast matters most; the site
# then remembers whichever the reader last chose.
REGIONS = {
    "scotland": {
        "label": "Scottish Highlands", "short": "Highlands",
        "column": "M", "list_name": "Munros",
        "order": 1,
        "area_column": "Region",
        # Vertical scale for the elevation glyph, from the design handoff.
        "scale": 1600,
        "bands": [(1200, "Over 1200m"), (1100, "1100 to 1200m"),
                  (1000, "1000 to 1100m"), (0, "Under 1000m")],
    },
    "lakes": {
        "label": "Lake District", "short": "Lakes",
        "column": "W", "list_name": "Wainwrights",
        "order": 2,
        "area_column": "Area",
        "scale": 1200,
        # Finer than the old 800/600/400 split, per board 2a: with cloud base
        # usually somewhere between 700 and 1000 m, those are the boundaries
        # that actually decide whether a Lakeland top is in it.
        "bands": [(900, "Over 900m"), (800, "800 to 900m"),
                  (700, "700 to 800m"), (0, "Under 700m")],
    },
    "snowdonia": {
        "label": "Snowdonia", "short": "Snowdonia",
        "column": "Hew", "list_name": "Hewitts",
        "order": 3,
        # DoBIH fills Area for Welsh hills with the range: Snowdon, The
        # Carneddau, The Glyders, The Moelwyns, Moel Hebog. Five groups over
        # fifty hills, which is close to ideal for the band headings.
        "area_column": "Area",
        # Yr Wyddfa is 1085 m, so the glyphs scale against 1100 rather than the
        # Highland 1600: on a Highland scale every Welsh hill would draw as a
        # low bump and the cloud line would sit off the top of the frame.
        "scale": 1100,
        "bands": [(900, "Over 900m"), (800, "800 to 900m"),
                  (700, "700 to 800m"), (0, "Under 700m")],
        # Hewitts run the length of England and Wales, so list membership alone
        # would pull in the Pennines and the Lakes as well. Region 30B is
        # DoBIH's own Snowdonia section.
        "where": lambda row: (row.get("Country") == "W"
                              and (row.get("Region") or "").startswith("30B")),
    },
}


def _area(row, column):
    """Tidy the geographic grouping into something readable.

    Munros arrive as '04A: Fort William to Loch Treig & Loch Leven' and
    Wainwrights as 'Lake District - Northern Fells'.
    """
    v = (row.get(column) or "").strip()
    if not v:
        return None
    if ":" in v:
        v = v.split(":", 1)[1].strip()          # drop the SMC section code
    if " - " in v:
        v = v.split(" - ", 1)[1].strip()        # drop the 'Lake District' prefix
    return v or None

# Chosen for ground truth, not popularity. Names must match DoBIH exactly
# after bracket-stripping - load_validation() asserts that they all resolve.
VALIDATION_NAMES = {
    "scotland": [
        "Ben Nevis", "Aonach Mor", "Aonach Beag", "Carn Mor Dearg",
        "Ben Macdui", "Braeriach", "Cairn Gorm", "Cairn Toul",
        "Meall a' Bhuiridh", "Creise", "Bidean nam Bian",
        "Buachaille Etive Mor - Stob Dearg",
        "Ben Lawers", "Ben More", "Ben Lomond", "Ben Cruachan",
        "Schiehallion", "An Teallach - Bidein a' Ghlas Thuill",
        "Ben Wyvis - Glas Leathad Mor", "Sgurr Alasdair",
    ],
    "lakes": [
        "Scafell Pike", "Scafell", "Helvellyn", "Skiddaw", "Great End",
        "Bowfell", "Great Gable", "Pillar", "Fairfield",
        "Blencathra - Hallsfell Top", "Crinkle Crags - Long Top",
        "Great Dodd", "Grasmoor", "St Sunday Crag",
        "High Street", "High Stile", "The Old Man of Coniston", "Kirk Fell",
        "Lingmell", "Haystacks", "Cat Bells", "Loughrigg Fell",
    ],
    # No ground truth source is wired up for Wales yet, unlike Helvellyn's Fell
    # Top Assessor or the Scottish webcams. These are archived anyway: the
    # archive stores raw API responses, never derived answers, so once a Welsh
    # observation source does exist the whole history can be scored
    # retroactively. Waiting would throw away data that cannot be re-fetched.
    "snowdonia": [
        "Snowdon - Yr Wyddfa", "Crib y Ddysgl", "Carnedd Llewelyn",
        "Carnedd Dafydd", "Glyder Fawr", "Glyder Fach", "Pen yr Ole Wen",
        "Y Garn", "Elidir Fawr", "Crib Goch", "Tryfan", "Y Lliwedd",
        "Moel Siabod", "Moel Hebog", "Moelwyn Mawr", "Cnicht",
        "Moel Eilio", "Yr Aran",
    ],
}

_BRACKETS = re.compile(r"\s*[\[\(].*?[\]\)]\s*")

# DoBIH records list membership as comma-separated codes. Only the lists people
# actually bag are worth showing; the rest are cartographic bookkeeping.
LIST_NAMES = {
    "M": "Munro", "MT": "Munro Top", "C": "Corbett", "CT": "Corbett Top",
    "G": "Graham", "D": "Donald", "DT": "Donald Top", "Hew": "Hewitt",
    "N": "Nuttall", "W": "Wainwright", "B": "Birkett", "Ma": "Marilyn",
    "Fel": "Fellranger",
}
COUNTRIES = {"S": "Scotland", "E": "England", "W": "Wales", "I": "Ireland"}


def _lists(value):
    out = [LIST_NAMES[c.strip()] for c in (value or "").split(",")
           if c.strip() in LIST_NAMES]
    # Order them the way a bagger would rank them, biggest list first.
    rank = list(LIST_NAMES.values())
    return sorted(set(out), key=rank.index)


def _clean(name):
    """'Ben Nevis [Beinn Nibheis]' -> ('Ben Nevis', 'Beinn Nibheis')."""
    alt = None
    m = re.search(r"[\[\(](.+?)[\]\)]", name)
    if m:
        alt = m.group(1).strip()
    return _BRACKETS.sub(" ", name).strip(), alt


def _open_source():
    """The extracted CSV if present, otherwise straight out of the zip.

    The zip is committed (CC-BY permits redistribution with attribution) so a
    fresh clone on any machine runs with no download step - which matters when
    the same project is worked on from both a laptop and a desktop.
    """
    if DOBIH_CSV.exists():
        return open(DOBIH_CSV, encoding="utf-8-sig", newline="")
    if DOBIH_ZIP.exists():
        zf = zipfile.ZipFile(DOBIH_ZIP)
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        return io.TextIOWrapper(zf.open(name), encoding="utf-8-sig", newline="")
    raise FileNotFoundError(
        f"No hill data. Expected {DOBIH_CSV.name} or {DOBIH_ZIP.name} in "
        f"{DOBIH_CSV.parent}. Download from "
        "https://www.hill-bagging.co.uk/dobih-downloads/hillcsv.zip")


def _rows():
    with _open_source() as f:
        for row in csv.DictReader(f):
            yield {k.strip(): (v.strip() if isinstance(v, str) else v)
                   for k, v in row.items() if k}


def load_hills(region=None, validation=False):
    """Hills for one region, or all regions. See module docstring."""
    if region is None:
        out = []
        for r in REGIONS:
            out.extend(load_hills(r, validation))
        return out
    if region not in REGIONS:
        raise ValueError(f"unknown region {region!r}; have {sorted(REGIONS)}")

    col = REGIONS[region]["column"]
    where = REGIONS[region].get("where")
    hills = []
    for row in _rows():
        if row.get(col) != "1":
            continue
        # Some lists span more than one region, so membership is necessary but
        # not always sufficient.
        if where and not where(row):
            continue
        name, alt = _clean(row["Name"])
        try:
            # Prominence. A better measure of "worth climbing" than raw height:
            # a 600m hill with 500m of drop is a proper day out, a 900m bump on
            # a ridge is not.
            prominence = round(float(row.get("Drop") or 0))
        except ValueError:
            prominence = None
        hills.append(Hill(
            name=name, region=region,
            lat=round(float(row["Latitude"]), 5),
            lon=round(float(row["Longitude"]), 5),
            height=round(float(row["Metres"])),
            alt=alt,
            prominence=prominence,
            area=_area(row, REGIONS[region]["area_column"]),
            lists=_lists(row.get("Classification")),
            county=row.get("County") or None,
            country=COUNTRIES.get(row.get("Country"), None),
            grid_ref=row.get("Grid ref") or None,
            # "51 52" means the summit falls on two Landranger sheets.
            map50=(row.get("Map 1:50k") or "").replace(" ", ", ") or None,
            # What actually marks the top: a trig point, a cairn, a shelter.
            feature=row.get("Feature") or None,
            url=row.get("Hill-bagging") or None,
        ))
    hills.sort(key=lambda h: -h.height)

    if not validation:
        return hills

    wanted = VALIDATION_NAMES[region]
    by_name = {}
    for h in hills:
        # Several DoBIH names repeat across regions (there are many Ben Mores);
        # within one list the highest wins, which is the one people mean.
        by_name.setdefault(h.name, h)
    picked, missing = [], []
    for w in wanted:
        if w in by_name:
            picked.append(by_name[w])
        else:
            missing.append(w)
    if missing:
        raise ValueError(f"{region}: validation hills not found in DoBIH: {missing}")
    return sorted(picked, key=lambda h: -h.height)


if __name__ == "__main__":
    for region, meta in REGIONS.items():
        full = load_hills(region)
        val = load_hills(region, validation=True)
        print(f"{region:9} {meta['list_name']:13} full {len(full):4}   "
              f"validation {len(val):3}   "
              f"{min(h.height for h in full)}-{max(h.height for h in full)}m")
    print(f"{'TOTAL':9} {'':13} full {len(load_hills()):4}   "
          f"validation {len(load_hills(validation=True)):3}")
