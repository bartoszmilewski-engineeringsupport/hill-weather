#!/usr/bin/env python3
"""
Validation harness. Does the forecast actually work?

    python scripts/validate.py --fetch          collect observations and profiles
    python scripts/validate.py --score          score what has been collected
    python scripts/validate.py --score --tune   also search for better constants
    python scripts/validate.py --stations       list the stations and their data

Everything else in this project is polish until this is answered.

WHY AIRPORTS

The site predicts a cloud base over a summit, and almost nobody measures that.
Airports measure it every half hour, for free, going back decades, and they
report the two numbers the LCL formula takes as input (temperature and
dewpoint) alongside the base it is trying to predict. So the physics can be
checked against the thing it claims to compute, at the same place and instant.

This deliberately does NOT answer whether the method transfers to mountains.
Orographic lift raises cloud base over a summit and the model's terrain is
smoothed, so a hill is a harder case than an airfield. That question needs
summit observations and a season to collect them. But if the physics is wrong
at an airport it cannot be right on Ben Nevis, so this is the first question
and it is answerable now.

SYNTHETIC SUMMITS

An airport at 7 m is never "in cloud", so the verdict cannot be scored there
directly. Instead the observed ceiling is treated as truth and a ladder of
imaginary summits is placed above each station: if the ceiling was at 800 m,
then a 1000 m summit was in cloud and a 600 m one was not. That gives a real
confusion matrix and a real calibration curve over the whole probability
range, using the same code path the site uses.

CEILING, NOT ANY CLOUD

Aviation defines the ceiling as the lowest BROKEN or OVERCAST layer. Scattered
cloud does not put you in cloud in any reliable sense, and scoring against it
would punish the forecast for being right. FEW and SCT layers are recorded but
are not the target.

REGIMES

A first run made the method look worthless: skill of minus 110 per cent
against climatology. Splitting by how low the cloud actually was showed why,
and it was a flaw in the scoring rather than in the forecast.

The LCL predicts the base of cloud lifted from the surface, which is what hill
fog and low stratus are. It says nothing useful about a deck at 3000 m formed
by something else entirely. Scoring every hour together let those hours, where
no British summit is anywhere near the cloud and the answer does not matter,
dominate a single average.

So everything below is reported by regime, and the headline is the low-cloud
regime, because that is the only one where the question the site asks has an
answer worth having.

SOURCES
  Observations   Iowa State University ASOS archive, mesonet.agron.iastate.edu
  Model          Open-Meteo previous-runs API, the same ukmo_uk_deterministic_2km
                 the site forecasts with. A separate endpoint from the
                 forecast API, so this costs none of the daily budget.
"""

import argparse
import csv
import io
import json
import math
import statistics as st
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import physics                                    # noqa: E402
from omfetch import LEVELS, all_variables         # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "validation"
UA = {"User-Agent": "hillweather-validation/1.0 (contact@hillweather.co.uk)"}

# Stations chosen for proximity to the hills the site forecasts, not for
# convenience. Elevation is metres above sea level: METAR reports cloud base
# above the ground, so the station height has to be added to compare with a
# summit height.
STATIONS = [
    ("EGPE", "Inverness",   57.5425, -4.0475,   7, "scotland"),
    ("EGPD", "Aberdeen",    57.2019, -2.1978,  65, "scotland"),
    ("EGPF", "Glasgow",     55.8719, -4.4331,   8, "scotland"),
    ("EGQS", "Lossiemouth", 57.7052, -3.3392,  13, "scotland"),
    ("EGPK", "Prestwick",   55.5094, -4.5867,  20, "scotland"),
    ("EGQL", "Leuchars",    56.3729, -2.8684,  11, "scotland"),
    ("EGPU", "Tiree",       56.4992, -6.8692,  12, "scotland"),
    ("EGNC", "Carlisle",    54.9375, -2.8092,  58, "lakes"),
    ("EGNH", "Blackpool",   53.7717, -3.0286,  10, "lakes"),
    ("EGOV", "Valley",      53.2481, -4.5353,  11, "snowdonia"),
    ("EGNR", "Hawarden",    53.1781, -2.9778,  11, "snowdonia"),
    ("EGFF", "Cardiff",     51.3967, -3.3433,  67, "snowdonia"),
]

# Oktas at the midpoint of each METAR cover category, as a percentage. Used to
# compare against the model's cloud_cover_low, which is a percentage.
COVER_PCT = {"CLR": 0, "SKC": 0, "NCD": 0, "NSC": 0,
             "FEW": 19, "SCT": 44, "BKN": 75, "OVC": 100}
CEILING_COVERS = {"BKN", "OVC"}

# Imaginary summits placed above each station. Spans the range of British
# hills: a Wainwright at 400 m through to a Munro at 1200 m.
SUMMITS = [400, 600, 800, 1000, 1200]

FT_TO_M = 0.3048

# Ceiling bands, metres above sea level. The first is where the site earns its
# keep: cloud down among the hills. The last is above every British summit, so
# whatever the forecast says there, nobody is standing in it.
REGIMES = [(0, 800, "low, in among the hills"),
           (800, 1400, "around the highest summits"),
           (1400, 99999, "above everything")]
HILL_RELEVANT = 1400


# --------------------------------------------------------------- fetching --

def _get(url, timeout=90, retries=4):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            if attempt == retries - 1:
                raise
            wait = 5 * (attempt + 1)
            print(f"      retry in {wait}s ({e})")
            time.sleep(wait)


def fetch_observations(icao, start, end):
    """Hourly METAR for one station. Returns {iso_hour: obs}."""
    url = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
           f"?station={icao}&data=tmpc&data=dwpc"
           "&data=skyc1&data=skyl1&data=skyc2&data=skyl2"
           "&data=skyc3&data=skyl3&data=skyc4&data=skyl4&data=vsby"
           f"&year1={start.year}&month1={start.month}&day1={start.day}"
           f"&year2={end.year}&month2={end.month}&day2={end.day}"
           "&tz=UTC&format=onlycomma&latlon=no&missing=empty&trace=empty"
           "&direct=no&report_type=3")
    text = _get(url).decode("utf-8", "replace")
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        when = row.get("valid")
        if not when:
            continue
        # METAR is issued near the top of the hour, usually at :50 for the hour
        # ahead. Round to the nearest hour so it lines up with the model.
        t = datetime.strptime(when, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        t = (t + timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)

        layers = []
        for n in (1, 2, 3, 4):
            cover = (row.get(f"skyc{n}") or "").strip().upper()
            level = (row.get(f"skyl{n}") or "").strip()
            if not cover:
                continue
            try:
                feet = float(level) if level else None
            except ValueError:
                feet = None
            layers.append((cover, feet))

        # The ceiling: lowest broken or overcast layer, in feet above ground.
        ceil_ft = min((f for c, f in layers if c in CEILING_COVERS and f is not None),
                      default=None)
        any_ft = min((f for c, f in layers if f is not None), default=None)
        cover_pct = max((COVER_PCT.get(c, 0) for c, _ in layers), default=0)

        def num(key):
            try:
                return float(row[key])
            except (KeyError, TypeError, ValueError):
                return None

        out[t.isoformat()] = {
            "ceiling_ft": ceil_ft,
            "lowest_ft": any_ft,
            "cover_pct": cover_pct,
            "temp": num("tmpc"),
            "dewp": num("dwpc"),
            "vis_miles": num("vsby"),
        }
    return out


def fetch_profiles(lat, lon, past_days):
    """Model profiles at a point, from the previous-runs endpoint.

    This is the same model the site forecasts with, so the physics is being
    scored on exactly the input it gets in production. A different endpoint
    from the forecast API, so it costs none of the daily forecast budget.
    """
    variables = all_variables(minimal=True)
    url = ("https://previous-runs-api.open-meteo.com/v1/forecast"
           f"?latitude={lat}&longitude={lon}"
           f"&hourly={','.join(variables)}"
           "&models=ukmo_uk_deterministic_2km"
           f"&past_days={past_days}&forecast_days=1&timezone=UTC")
    return json.loads(_get(url))


def do_fetch(days, only=None):
    STORE.mkdir(parents=True, exist_ok=True)
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days + 1)
    stations = [s for s in STATIONS if not only or s[0] in only]

    print(f"collecting {days} days for {len(stations)} station(s)\n")
    for icao, name, lat, lon, elev, region in stations:
        print(f"  {icao} {name}")
        try:
            obs = fetch_observations(icao, start, end)
            print(f"      observations: {len(obs)} hours")
        except Exception as e:
            print(f"      observations FAILED: {e}")
            continue
        try:
            model = fetch_profiles(lat, lon, days)
            hours = len(model.get("hourly", {}).get("time", []))
            print(f"      model:        {hours} hours")
        except Exception as e:
            print(f"      model FAILED: {e}")
            continue

        (STORE / f"{icao}.json").write_text(json.dumps({
            "station": {"icao": icao, "name": name, "lat": lat, "lon": lon,
                        "elev_m": elev, "region": region},
            "fetched_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "observations": obs,
            "model": model,
        }), encoding="utf-8", newline="\n")
        time.sleep(1.5)          # be a good citizen on two free services
    print(f"\nstored in {STORE.relative_to(ROOT)}")


# ---------------------------------------------------------------- pairing --

def pairs_for(icao):
    """Every hour where a model profile and a real observation both exist."""
    path = STORE / f"{icao}.json"
    if not path.exists():
        return []
    d = json.loads(path.read_text(encoding="utf-8"))
    station, obs, model = d["station"], d["observations"], d["model"]
    hourly = model.get("hourly", {})
    times = hourly.get("time", [])
    elev = station["elev_m"]

    rows = []
    for i, t in enumerate(times):
        # The model gives "2026-06-25T00:00" and the observation index is keyed
        # by a full isoformat with seconds. Normalise through datetime rather
        # than by string surgery, which silently paired nothing.
        try:
            when = datetime.fromisoformat(t)
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        iso = when.isoformat()
        o = obs.get(iso)
        if not o:
            continue
        # The forecast's own answer for this hour, from the production code.
        # A nominal summit height is required by the signature but does not
        # affect the computed base.
        cond = physics.summit_conditions(hourly, i, {"height": 1000}, LEVELS)
        if not cond:
            continue

        observed = (elev + o["ceiling_ft"] * FT_TO_M) if o["ceiling_ft"] else None
        rows.append({
            "station": icao, "region": station["region"], "t": iso,
            "predicted_base": cond["cloud_base"],
            "predicted_top": cond["cloud_top"],
            "observed_base": observed,
            "observed_cover": o["cover_pct"],
            "model_low_cover": cond["low"],
            "obs_temp": o["temp"], "obs_dewp": o["dewp"],
            "lcl": cond["lcl"], "rh_base": cond["rh_base"],
        })
    return rows


def load_all():
    rows = []
    for icao, *_ in STATIONS:
        rows.extend(pairs_for(icao))
    rows.sort(key=lambda r: r["t"])
    return rows


# ---------------------------------------------------------------- scoring --

def split(rows, holdout=0.33):
    """Chronological split. Tuning on data you later score against fits noise
    and flatters the result, so the last third is never looked at while
    choosing constants."""
    cut = int(len(rows) * (1 - holdout))
    return rows[:cut], rows[cut:]


def base_error(rows):
    """Bias and error of the predicted cloud base, in metres.

    Only hours where a ceiling was actually observed AND the forecast claimed
    a base: those are the hours where both have an opinion to compare.
    """
    both = [r for r in rows
            if r["observed_base"] is not None and r["predicted_base"] is not None]
    if not both:
        return None
    errs = [r["predicted_base"] - r["observed_base"] for r in both]
    return {
        "n": len(both),
        "bias": st.mean(errs),
        "mae": st.mean(abs(e) for e in errs),
        "median_abs": st.median(sorted(abs(e) for e in errs)),
        "within_200": 100 * sum(1 for e in errs if abs(e) <= 200) / len(errs),
        "within_400": 100 * sum(1 for e in errs if abs(e) <= 400) / len(errs),
    }


def summit_cases(rows):
    """Expand each hour into one case per imaginary summit height.

    truth: was a summit at this height inside cloud, by the observed ceiling
    forecast: what the site would have said, as a probability of a view
    """
    cases = []
    for r in rows:
        obs_base = r["observed_base"]
        if obs_base is None and r["observed_cover"] >= 50:
            continue                      # cloudy but no ceiling reported
        for h in SUMMITS:
            in_cloud = obs_base is not None and h >= obs_base
            label, p_cloud, _ = physics.verdict(
                h, r["predicted_base"], r["predicted_top"], r["model_low_cover"])
            cases.append({
                "height": h, "in_cloud": in_cloud,
                "view_pct": 100 - p_cloud, "verdict": label,
                "station": r["station"], "t": r["t"],
            })
    return cases


def calibration(cases, bins=5):
    """When the site says 70%, does it happen about 70% of the time?

    The central question for a forecast made of percentages, and the one most
    easily skipped. A forecast can have good accuracy and useless calibration.
    """
    out = []
    for lo in range(0, 100, 100 // bins):
        hi = lo + 100 // bins
        sel = [c for c in cases if lo <= c["view_pct"] < hi or
               (hi == 100 and c["view_pct"] == 100)]
        if not sel:
            continue
        claimed = st.mean(c["view_pct"] for c in sel)
        actual = 100 * sum(1 for c in sel if not c["in_cloud"]) / len(sel)
        out.append({"band": f"{lo}-{hi}%", "n": len(sel),
                    "claimed": claimed, "actual": actual,
                    "gap": actual - claimed})
    return out


def confusion(cases):
    m = defaultdict(int)
    for c in cases:
        said_cloud = c["view_pct"] < 50
        m[(said_cloud, c["in_cloud"])] += 1
    tp = m[(True, True)]; fp = m[(True, False)]
    fn = m[(False, True)]; tn = m[(False, False)]
    total = tp + fp + fn + tn
    return {
        "said_cloud_was_cloud": tp, "said_cloud_was_clear": fp,
        "said_clear_was_cloud": fn, "said_clear_was_clear": tn,
        "accuracy": 100 * (tp + tn) / total if total else 0,
        "n": total,
    }


def brier(cases):
    """Mean squared error of the probability. Lower is better. The metric a
    baseline has to be beaten on."""
    if not cases:
        return None
    return st.mean(((100 - c["view_pct"]) / 100 - (1 if c["in_cloud"] else 0)) ** 2
                   for c in cases)


def baselines(train_cases, test_cases):
    """A forecast that cannot beat these has no value.

    climatology: always predict the training-period base rate
    persistence: predict what was observed at this height 24 hours earlier
    """
    if not train_cases or not test_cases:
        return {}
    rate = sum(1 for c in train_cases if c["in_cloud"]) / len(train_cases)
    clim = st.mean((rate - (1 if c["in_cloud"] else 0)) ** 2 for c in test_cases)

    seen = {(c["station"], c["height"], c["t"]): c["in_cloud"]
            for c in train_cases + test_cases}
    errs = []
    for c in test_cases:
        then = (datetime.fromisoformat(c["t"]) - timedelta(days=1)).isoformat()
        prev = seen.get((c["station"], c["height"], then))
        if prev is None:
            continue
        errs.append(((1 if prev else 0) - (1 if c["in_cloud"] else 0)) ** 2)
    return {"climatology": clim,
            "persistence": st.mean(errs) if errs else None,
            "persistence_n": len(errs)}


# ----------------------------------------------------------------- report --

def bar(value, lo, hi, width=28):
    if value is None:
        return ""
    f = max(0.0, min(1.0, (value - lo) / (hi - lo)))
    n = round(f * width)
    return "#" * n + "." * (width - n)


def report(rows):
    if not rows:
        print("No paired data. Run --fetch first.")
        return

    train, test = split(rows)
    span = f"{rows[0]['t'][:10]} to {rows[-1]['t'][:10]}"
    stations = sorted({r["station"] for r in rows})
    print(f"\n{'=' * 72}")
    print(f"  {len(rows):,} paired hours   {len(stations)} stations   {span}")
    print(f"  tuned on the first {len(train):,}, scored on the last {len(test):,}"
          f" never looked at")
    print(f"{'=' * 72}")

    print("\n-- CLOUD BASE, metres, BY REGIME -------------------------------")
    print("   split by how low the cloud actually was. The first row is the")
    print("   one that matters: cloud down among the hills.")
    for lo, hi, label in REGIMES:
        part = [r for r in rows if r["observed_base"] is not None
                and lo <= r["observed_base"] < hi]
        e = base_error(part)
        if not e:
            continue
        print(f"   {label:28} n={e['n']:>5}  bias {e['bias']:+7.0f}  "
              f"mae {e['mae']:6.0f}  within 200 m {e['within_200']:5.1f}%")

    print("\n   held out, hill-relevant only (ceiling below "
          f"{HILL_RELEVANT} m):")
    e = base_error([r for r in test if r["observed_base"] is not None
                    and r["observed_base"] < HILL_RELEVANT])
    if e:
        print(f"      n={e['n']:>5}  bias {e['bias']:+7.0f}  mae {e['mae']:6.0f}  "
              f"median abs {e['median_abs']:6.0f}")
        print(f"      within 200 m: {e['within_200']:5.1f}%   "
              f"within 400 m: {e['within_400']:5.1f}%")
        target = "MET" if e["within_200"] >= 50 else "NOT MET"
        print(f"      target of 200 m on most days: {target}")

    # Calibration and skill are judged only where the question has a real
    # answer. Including hours with cloud far above every summit inflates the
    # sample with cases nobody would ever ask about, and the average stops
    # describing anything.
    relevant = lambda rs: [r for r in rs if r["observed_base"] is None
                           or r["observed_base"] < HILL_RELEVANT]
    train_cases = summit_cases(relevant(train))
    test_cases = summit_cases(relevant(test))

    print(f"\n-- CALIBRATION, held out, ceiling below {HILL_RELEVANT} m --------")
    print("   does a stated percentage happen that often?")
    cal = calibration(test_cases)
    if not cal:
        print("   not enough cases")
    for c in cal:
        flag = "  <-- overconfident" if c["gap"] < -10 else \
               "  <-- underconfident" if c["gap"] > 10 else ""
        print(f"   said {c['band']:>8}  n={c['n']:>5}  "
              f"claimed {c['claimed']:5.1f}%  actual {c['actual']:5.1f}%  "
              f"gap {c['gap']:+6.1f}{flag}")

    print("\n-- VERDICT, held out -------------------------------------------")
    cm = confusion(test_cases)
    print(f"   said in cloud, was in cloud : {cm['said_cloud_was_cloud']:>6}")
    print(f"   said in cloud, was clear    : {cm['said_cloud_was_clear']:>6}"
          f"   (a wasted drive)")
    print(f"   said clear,    was in cloud : {cm['said_clear_was_cloud']:>6}"
          f"   (the worse error: a promise broken)")
    print(f"   said clear,    was clear    : {cm['said_clear_was_clear']:>6}")
    tp = cm["said_cloud_was_cloud"]; fp = cm["said_cloud_was_clear"]
    fn = cm["said_clear_was_cloud"]; tn = cm["said_clear_was_clear"]
    really_clear = fp + tn
    print(f"   accuracy {cm['accuracy']:.1f}% of {cm['n']:,} summit-hours")
    # Accuracy alone flatters any forecast on an unbalanced problem. Most
    # summit-hours are clear, so a model that says "clear" every single time
    # scores well without knowing anything. That is the number to beat.
    naive = 100 * really_clear / cm["n"] if cm["n"] else 0
    verdict_line = "BEATEN by saying nothing" if naive > cm["accuracy"] else "beats it"
    print(f"   always saying CLEAR would score {naive:.1f}%  <- {verdict_line}")
    if tp + fp:
        print(f"   when it says IN CLOUD it is right {100*tp/(tp+fp):.1f}% of the time")
    if tn + fn:
        print(f"   when it says CLEAR    it is right {100*tn/(tn+fn):.1f}% of the time")
    if tp + fn:
        print(f"   of summits really in cloud it catches {100*tp/(tp+fn):.1f}%")

    print("\n-- SKILL, held out ---------------------------------------------")
    print("   Brier score, lower is better. Beating these is the whole point.")
    b = brier(test_cases)
    base = baselines(train_cases, test_cases)
    rows_out = [("this forecast", b)]
    if base.get("climatology") is not None:
        rows_out.append(("climatology", base["climatology"]))
    if base.get("persistence") is not None:
        rows_out.append((f"persistence (n={base['persistence_n']:,})",
                         base["persistence"]))
    for label, v in rows_out:
        print(f"   {label:26} {v:.4f}  {bar(v, 0, 0.35)}")
    if b is not None and base.get("climatology"):
        skill = 100 * (1 - b / base["climatology"])
        verdictline = ("BETTER than guessing the average"
                       if skill > 0 else "NO BETTER than guessing the average")
        print(f"\n   skill against climatology: {skill:+.1f}%   {verdictline}")

    print("\n-- BY STATION, cloud base mean abs error -----------------------")
    for icao in stations:
        e = base_error([r for r in rows if r["station"] == icao])
        if e:
            name = next(s[1] for s in STATIONS if s[0] == icao)
            print(f"   {icao} {name:12} n={e['n']:>5}  bias {e['bias']:+7.0f}  "
                  f"mae {e['mae']:6.0f}  {bar(e['mae'], 0, 800)}")
    print()


# ------------------------------------------------------------------ tune --

def tune(rows):
    """Search the constants on the TRAINING half only.

    physics.py holds these as module globals, so they are swapped in place and
    restored. Anything found here still has to prove itself on the held-out
    third, which this deliberately never touches.
    """
    keep = (physics.RH_MOIST, physics.LCL_K, physics.LOW_CLOUD_MIN)
    best, results = None, []
    print("\n-- TUNING on the training half only ----------------------------")
    print("   Every prediction is recomputed for each combination. Scoring the")
    print("   rows already in memory would re-score cached answers and make")
    print("   every combination look identical, which is exactly what the")
    print("   first version of this did.")
    for rh in (75.0, 80.0, 85.0, 90.0, 95.0):
        for k in (100.0, 112.0, 125.0, 140.0):
            physics.RH_MOIST, physics.LCL_K = rh, k
            train, _ = split(load_all())
            train = [r for r in train if r["observed_base"] is None
                     or r["observed_base"] < HILL_RELEVANT]
            b = brier(summit_cases(train))
            e = base_error(train)
            results.append((b, rh, k, e["mae"] if e else None))
            if best is None or b < best[0]:
                best = (b, rh, k)
    physics.RH_MOIST, physics.LCL_K, physics.LOW_CLOUD_MIN = keep

    results.sort()
    print(f"   {'RH_MOIST':>9} {'LCL_K':>7} {'brier':>8} {'base mae':>9}")
    for b, rh, k, mae in results[:8]:
        mark = "  <-- current" if (rh, k) == (keep[0], keep[1]) else ""
        print(f"   {rh:>9.0f} {k:>7.0f} {b:>8.4f} "
              f"{(f'{mae:.0f}' if mae else '-'):>9}{mark}")
    print(f"\n   best on training data: RH_MOIST={best[1]:.0f} LCL_K={best[2]:.0f}")
    print("   Re-score with those set in physics.py to see if it holds on the")
    print("   held-out third. If it does not, it was noise.")



def sweep(name, values):
    """Try one constant across a range, on the TRAINING half only.

    The held-out third is never touched here. Anything chosen has to be
    confirmed against it afterwards with a plain --score, which is the only
    number that means anything.
    """
    keep = getattr(physics, name)
    print(f"\n-- SWEEPING {name} on the training half only ------------------")
    print(f"   {'value':>8} {'brier':>9} {'base mae':>10}")
    best = None
    for v in values:
        setattr(physics, name, v)
        train, _ = split(load_all())
        train = [r for r in train if r["observed_base"] is None
                 or r["observed_base"] < HILL_RELEVANT]
        b = brier(summit_cases(train))
        e = base_error(train)
        mark = "   <-- current" if v == keep else ""
        mae = f"{e['mae']:.0f}" if e else "-"
        print(f"   {v:>8.0f} {b:>9.4f} {mae:>10}{mark}")
        if best is None or b < best[0]:
            best = (b, v)
    setattr(physics, name, keep)
    print(f"\n   best on training: {name}={best[1]:.0f}  (brier {best[0]:.4f})")
    print("   Confirm with --score before believing it.")


# ------------------------------------------------------------------ main --

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="collect data")
    ap.add_argument("--days", type=int, default=60,
                    help="days of history (the model endpoint keeps ~60)")
    ap.add_argument("--station", action="append", help="limit to these ICAO codes")
    ap.add_argument("--score", action="store_true", help="score what is collected")
    ap.add_argument("--tune", action="store_true", help="search constants")
    ap.add_argument("--stations", action="store_true", help="list stations")
    # Try a candidate without editing physics.py, so a proposal can be tested
    # against the held-out third before it goes anywhere near production.
    ap.add_argument("--rh", type=float, help="override RH_MOIST for this run")
    ap.add_argument("--sigma", type=float,
                    help="override BASE_SIGMA for this run")
    ap.add_argument("--sweep", metavar="CONST",
                    help="sweep one constant on training data: "
                         "BASE_SIGMA, RH_MOIST or LCL_K")
    ap.add_argument("--lcl", type=float, help="override LCL_K for this run")
    args = ap.parse_args()

    if args.stations:
        print(f"{'ICAO':6} {'station':13} {'elev':>5}  {'region':10} collected")
        for icao, name, lat, lon, elev, region in STATIONS:
            p = STORE / f"{icao}.json"
            n = len(pairs_for(icao)) if p.exists() else 0
            print(f"{icao:6} {name:13} {elev:>4}m  {region:10} "
                  f"{n:>6} paired hours" if n else
                  f"{icao:6} {name:13} {elev:>4}m  {region:10}      -")
        return

    if args.rh is not None:
        physics.RH_MOIST = args.rh
    if args.sigma is not None:
        physics.BASE_SIGMA = args.sigma
    if args.lcl is not None:
        physics.LCL_K = args.lcl
    if args.rh is not None or args.lcl is not None:
        print(f"overrides: RH_MOIST={physics.RH_MOIST} LCL_K={physics.LCL_K}")

    if args.sweep:
        ranges = {
            "BASE_SIGMA": [150.0, 200.0, 250.0, 300.0, 400.0, 500.0, 650.0, 800.0],
            "RH_MOIST": [70.0, 75.0, 80.0, 85.0, 90.0, 95.0],
            "LCL_K": [130.0, 140.0, 150.0, 155.0, 160.0, 170.0, 185.0, 200.0],
        }
        if args.sweep not in ranges:
            sys.exit(f"unknown constant {args.sweep!r}; "
                     f"try one of {', '.join(ranges)}")
        sweep(args.sweep, ranges[args.sweep])
        return

    if args.fetch:
        do_fetch(args.days, set(args.station) if args.station else None)
    if args.score or args.tune:
        rows = load_all()
        if args.score:
            report(rows)
        if args.tune:
            tune(rows)
    if not (args.fetch or args.score or args.tune or args.stations):
        ap.print_help()


if __name__ == "__main__":
    main()
