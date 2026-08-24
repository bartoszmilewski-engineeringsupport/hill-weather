#!/usr/bin/env python3
"""
Cloud base, inversion and light-quality calculations.

The one idea this whole project rests on: forecast models smooth terrain badly.
A 2km model shaves ~60m off Ben Nevis and far more off sharper hills, so the
model's own surface values describe a mountain that does not exist. We take the
pressure-level profile instead and interpolate it to the TRUE summit height.

Cloud base is estimated two ways and cross-checked:
  LCL  - lift a glen-level parcel, the classic 125*(T-Td) rule. Right physics
         for orographic hill fog and finely resolved.
  RH   - lowest height where humidity crosses a moist threshold. Better for
         layer cloud, but limited by 215-466m spacing between model levels.

Every constant below is a tuning knob. They are guesses until the archive has
enough days to score them against observations - that is what Phase 2 is for.
"""

import math

# Grid-box mean RH is diluted: a 2km cell is never uniformly saturated, so a
# textbook 95% threshold finds no cloud on days that are obviously cloudy.
RH_MOIST = 85.0
# Below this low-cloud cover we call it cloud-free regardless of what the
# humidity profile says. An LCL tells you where cloud WOULD form if air is
# lifted - not that any cloud exists.
LOW_CLOUD_MIN = 15.0
# Model levels are 215-466m apart, so a summit poking just above an estimated
# cloud top is inside the error bars. Demand real clearance before calling it.
CLEAR_MARGIN = 150.0

# How well the modelled cloud base is actually known, in metres.
#
# Measured, not guessed: scripts/validate.py scores the modelled base against
# observed ceilings and gives a mean absolute error near 300 m across the
# hill-relevant range, and about 190 m when cloud is genuinely low. The value
# used here is larger than that, at 500 m, because it absorbs more than the
# base error alone: it also carries the fact that modelled cloud cover over a
# grid box is not the same thing as cloud at one point on one summit. Chosen by
# sweeping the TRAINING half only. The held-out third preferred an even larger
# value, and that was deliberately not taken: choosing a constant because the
# held-out data likes it is how a holdout stops being a holdout.
#
# This is the single most important number in the file. The verdict used to
# treat the base as exact, with a hard cliff at 50 m either side, which made a
# hill 51 m below the base a 90% chance of a view and one 49 m below a 5%
# chance. On an input known to a few hundred metres that is false precision,
# and because the cliff always fell the pessimistic way it made the whole
# forecast cry wolf: it said IN CLOUD and the summit was clear 54% of the time.
BASE_SIGMA = 500.0
PARCEL_LEVEL = 975          # ~350m, representative of glen-level air
# Metres of lift per degC of dewpoint depression. Espy's rule gives 125; this
# is 145, chosen by sweeping the TRAINING half and reading the CLOUD BASE ERROR
# rather than the Brier score. That distinction matters: Brier kept improving
# all the way to 200, but base error bottomed at 140 to 150 and then climbed to
# 300 m. Past the optimum, a larger value simply makes every forecast more
# optimistic, which pays on a problem where 83% of summit-hours are clear
# without being any more accurate. Brier alone will happily walk a forecast
# into the majority class.
LCL_K = 145.0
GRID = 25                   # m, vertical resolution of the interpolated profile


def dewpoint(t, rh):
    """Magnus formula. t in degC, rh in %."""
    if t is None or rh is None or rh <= 0:
        return None
    a, b = 17.625, 243.04
    alpha = math.log(rh / 100.0) + (a * t) / (b + t)
    return (b * alpha) / (a - alpha)


def build_profile(hourly, i, levels):
    """[(height_m, temp, rh, wind, dirn, gust_proxy), ...] sorted by height."""
    pts = []
    for lv in levels:
        h = hourly.get(f"geopotential_height_{lv}hPa", [None])[i]
        t = hourly.get(f"temperature_{lv}hPa", [None])[i]
        rh = hourly.get(f"relative_humidity_{lv}hPa", [None])[i]
        ws = hourly.get(f"wind_speed_{lv}hPa", [None])[i]
        wd = hourly.get(f"wind_direction_{lv}hPa", [None])[i]
        if h is None or t is None or rh is None:
            continue
        pts.append((h, t, rh, ws, wd))
    return sorted(pts)


def interp(prof, height, idx):
    """Linear interpolation of profile field `idx` to `height`."""
    vals = [(p[0], p[idx]) for p in prof if p[idx] is not None]
    if not vals:
        return None
    if height <= vals[0][0]:
        return vals[0][1]
    if height >= vals[-1][0]:
        return vals[-1][1]
    for (h0, v0), (h1, v1) in zip(vals, vals[1:]):
        if h0 <= height <= h1:
            f = (height - h0) / (h1 - h0) if h1 != h0 else 0
            return v0 + f * (v1 - v0)
    return None


def lcl_base(hourly, i):
    """Lift a glen-level parcel. Height above sea level, or None."""
    t = hourly.get(f"temperature_{PARCEL_LEVEL}hPa", [None])[i]
    rh = hourly.get(f"relative_humidity_{PARCEL_LEVEL}hPa", [None])[i]
    z = hourly.get(f"geopotential_height_{PARCEL_LEVEL}hPa", [None])[i]
    td = dewpoint(t, rh)
    if td is None or z is None:
        return None
    return z + LCL_K * max(0.0, t - td)


def moist_layer(prof):
    """Lowest moist layer as (base, top), interpolated off the model levels."""
    if len(prof) < 2:
        return None, None
    base = top = None
    z, hi = prof[0][0], prof[-1][0]
    while z <= hi:
        rh = interp(prof, z, 2)
        if rh is not None and rh >= RH_MOIST:
            if base is None:
                base = z
            top = z
        elif base is not None:
            break                        # first moist layer only
        z += GRID
    return base, top


def _normal_cdf(z):
    """Probability a standard normal is below z."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def verdict(summit, base, top, low_cover):
    """(label, in-cloud probability %, plain-English reason).

    Deliberately probabilistic. Broken cloud means the summit is in and out of
    it, and saying so is more useful than a confident icon that is wrong.

    Two independent things have to be true for a summit to be in cloud: there
    has to be cloud, and the summit has to be above its base. So:

        P(in cloud) = P(cloud present) x P(summit above the true base)

    The first is the modelled low cloud cover. The second is where the old
    version went wrong, by treating the modelled base as exact. It is not: it
    is known to about BASE_SIGMA, so the summit sitting a little below it is
    only weakly reassuring, and a summit far below it is genuinely safe. A
    normal CDF over the margin expresses exactly that, and it replaces a cliff
    that flipped a hill from 90% to 5% over a hundred metres.

    The practical effect is that the forecast stops claiming certainty it never
    had, in the direction it was always wrong: too much cloud, too often.
    """
    low_cover = low_cover or 0.0

    if base is None or low_cover < LOW_CLOUD_MIN:
        return "CLEAR", 5, f"little low cloud about ({low_cover:.0f}% cover)"

    # An inversion is a different question: the summit is above the cloud top
    # rather than below its base, and the useful answer is about standing on
    # top of it. Left as a separate branch on purpose.
    if top is not None and summit > top + CLEAR_MARGIN:
        return ("ABOVE CLOUD", 10,
                f"cloud {base:.0f}-{top:.0f}m, summit {summit - top:.0f}m clear above it")

    if top is not None and summit > top:
        return ("JUST ABOVE?", 45,
                f"cloud tops ~{top:.0f}m, summit only {summit - top:.0f}m above "
                f"- inside model error, could go either way")

    margin = summit - base                       # positive: summit above base
    p_above = _normal_cdf(margin / BASE_SIGMA)
    p = 100.0 * (low_cover / 100.0) * p_above
    p = max(2.0, min(97.0, p))                   # never absolute either way

    if p >= 60:
        label = "IN CLOUD"
    elif p >= 25:
        label = "ON THE EDGE"
    else:
        label = "CLEAR"

    top_s = f"{top:.0f}m" if top is not None else "well above"
    if margin >= 0:
        where = f"summit {margin:.0f}m above the base"
    else:
        where = f"summit {-margin:.0f}m below the base"
    return label, p, (f"cloud {base:.0f}m to {top_s}, {low_cover:.0f}% cover, "
                      f"{where}")


def inversion_score(summit, base, top, low_cover):
    """0-100. How good a cloud inversion this is to stand above.

    A proper inversion needs three things: the summit genuinely clear of the
    top, enough cover that it reads as a sea rather than scraps, and enough
    depth that it looks like a deck rather than a haze.
    """
    if top is None or base is None or summit <= top:
        return 0
    clearance = min(1.0, (summit - top) / 300.0)
    cover = min(1.0, (low_cover or 0) / 90.0)
    depth = min(1.0, (top - base) / 200.0)
    return round(100 * clearance * cover * depth)


def light_score(low_cover, mid_cover, high_cover, precip, above_cloud):
    """0-100. How good the sunrise or sunset light is likely to be.

    Needs mid or high cloud to catch colour - a clear sky gives a bland
    sunrise - but not so much that it blocks the light entirely. Rain kills it.

    The nuance that matters: low cloud is normally the enemy, but if you are
    standing ABOVE it, it stops being a blocker and becomes the subject. That
    is the shot photographers drive through the night for.
    """
    mid_high = max(mid_cover or 0, high_cover or 0)
    canvas = max(0.0, 100.0 - abs(mid_high - 50.0) * 2.0)   # peaks at 50% cover

    if above_cloud:
        blocker = 1.0
        canvas = min(100.0, canvas + (low_cover or 0) * 0.3)  # cloud sea below
    else:
        blocker = max(0.0, 1.0 - (low_cover or 0) / 100.0)

    wet = 0.15 if (precip or 0) > 0.2 else 1.0
    return round(canvas * blocker * wet)


def summit_conditions(hourly, i, hill, levels):
    """Everything we know about one summit at one hour."""
    prof = build_profile(hourly, i, levels)
    if not prof:
        return None

    summit = hill["height"]
    lcl = lcl_base(hourly, i)
    rh_base, rh_top = moist_layer(prof)
    low = hourly.get("cloud_cover_low", [None])[i]
    mid = hourly.get("cloud_cover_mid", [None])[i]
    high = hourly.get("cloud_cover_high", [None])[i]
    precip = hourly.get("precipitation", [None])[i]

    # Prefer the LCL for the base where it sits above a moist boundary layer -
    # a damp low-level airmass is normal and is not itself cloud.
    base = rh_base
    if rh_base is not None and lcl is not None and lcl > rh_base:
        base = lcl

    label, p_cloud, why = verdict(summit, base, rh_top, low)
    above = label == "ABOVE CLOUD"

    def r(v, n=0):
        return None if v is None else (round(v, n) if n else round(v))

    return {
        "t": hourly["time"][i],
        "verdict": label,
        "view_pct": round(100 - p_cloud),
        "why": why,
        "cloud_base": r(base),
        "cloud_top": r(rh_top),
        "lcl": r(lcl),
        "rh_base": r(rh_base),
        "temp": r(interp(prof, summit, 1), 1),
        "wind": r(interp(prof, summit, 3)),
        "wind_dir": r(interp(prof, summit, 4)),
        "gust": r(hourly.get("wind_gusts_10m", [None])[i]),
        "precip": r(precip, 1),
        "low": r(low), "mid": r(mid), "high": r(high),
        "freezing_level": r(hourly.get("freezing_level_height", [None])[i]),
        "inversion": inversion_score(summit, base, rh_top, low),
        "light": light_score(low, mid, high, precip, above),
        # Flagged where the two base estimates straddle the summit - that is
        # the only case where their disagreement changes the answer.
        "uncertain": bool(lcl is not None and rh_base is not None
                          and min(lcl, rh_base) < summit < max(lcl, rh_base)),
    }
