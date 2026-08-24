#!/usr/bin/env python3
"""
Open-Meteo fetching, shared by the archiver and the builder.

One place that knows about the model, the variables and the batching, so the
archive and the live build can never drift apart.

Model: UK Met Office 2km deterministic. Chosen over the global models because
at 25km grid spacing the Highlands are a gentle bump - a model that cannot see
the mountain cannot forecast its summit.

Free tier is non-commercial and rate limited, which is why phones never call
this directly: one build fetches everything, everyone reads the static result.
"""

import json
import time
import urllib.error
import urllib.request

MODEL = "ukmo_uk_deterministic_2km"
LEVELS = [1000, 975, 950, 925, 900, 850, 800, 700]
CHUNK = 25              # hills per request, keeps the URL well inside limits

SURFACE_VARS = [
    "temperature_2m", "relative_humidity_2m", "dew_point_2m",
    "precipitation", "rain", "snowfall",
    "cloud_cover", "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high",
    "visibility", "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
    "freezing_level_height", "pressure_msl", "surface_pressure", "cape",
    "weather_code",
]
LEVEL_VARS = ["temperature", "relative_humidity", "cloud_cover",
              "wind_speed", "wind_direction", "geopotential_height",
              "vertical_velocity"]

# Open-Meteo weights a request by variables x locations x days (see call_weight
# below), so asking for all 75 variables across all 546 hills would cost about
# 4100 calls a run against an hourly allowance of 5000. The live build asks only
# for the 46 variables physics.py actually reads, which brings a run to ~2500.
# The archive keeps all 75, because it is only 60 hills and we cannot re-fetch
# the past if we later want a variable we did not save.
BUILD_SURFACE_VARS = [
    "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high",
    "precipitation", "freezing_level_height", "wind_gusts_10m",
]
BUILD_LEVEL_VARS = ["temperature", "relative_humidity",
                    "wind_speed", "wind_direction", "geopotential_height"]

# --------------------------------------------------------------- budget ---
# Open-Meteo counts fractional "calls", not requests. From their own worked
# example (45 variables, 3 days, 1 location = 4.5 calls):
#
#     calls = variables x forecast_days x locations / 30
#
# The free tier allows 600 calls a minute, 5000 an hour, 10000 a day. The
# per-minute one is what we kept tripping, and not because we ask for too
# much: one 25-hill chunk of the live build is 115 calls, so firing chunks
# three seconds apart is roughly 1400 calls a minute, over twice the limit.
# We were sprinting into a 429 in the first few seconds of every build and
# then backing off for twenty minutes.
#
# So pace by weight instead of by a flat sleep. A full run is about 2960
# calls, which is comfortable against the hourly 5000 as long as only one run
# happens per hour. Two builds in the same hour will not fit; that is why the
# scheduler runs twice a day and manual rebuilds should be occasional.
TARGET_PER_MIN = 450          # of 600; headroom, we are a guest on a free tier

_last_chunk_at = 0.0          # module-level so regions in one build queue up


def call_weight(locations, variables, forecast_days):
    """Open-Meteo's fractional call count for one request."""
    return locations * variables * forecast_days / 30.0


ATTRIBUTION = {
    "weather": "Open-Meteo, UK Met Office 2km model - https://open-meteo.com",
    "hills": ("DoBIH v18.5, CC-BY-4.0 - https://www.hill-bagging.co.uk/dobih"),
}


def all_variables(minimal=False):
    """Every variable, or just the ones the forecast maths reads."""
    surface = BUILD_SURFACE_VARS if minimal else SURFACE_VARS
    levels = BUILD_LEVEL_VARS if minimal else LEVEL_VARS
    v = list(surface)
    for lv in LEVELS:
        v += [f"{name}_{lv}hPa" for name in levels]
    return v


def _fetch_chunk(hills, variables, forecast_days, retries=6):
    lats = ",".join(str(h.lat) for h in hills)
    lons = ",".join(str(h.lon) for h in hills)
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={lats}&longitude={lons}"
           f"&hourly={','.join(variables)}"
           f"&models={MODEL}&wind_speed_unit=mph"
           f"&timezone=UTC&forecast_days={forecast_days}")
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                data = json.load(r)
            return data if isinstance(data, list) else [data]
        except urllib.error.HTTPError as e:
            last = e
            if e.code != 429 or attempt == retries - 1:
                raise RuntimeError(f"fetch failed: HTTP {e.code} {e.reason}")
            # Rate limited. With weight-based pacing this should now be rare,
            # so reaching here usually means something else ran recently and
            # ate the hourly allowance. That cannot be waited out in seconds,
            # hence the long backoff: nothing here is urgent, and a build that
            # takes twenty minutes beats one that fails and leaves the site
            # stale until the next slot.
            wait = min(600, 60 * (2 ** attempt))
            print(f"    rate limited, waiting {wait}s")
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"fetch failed after {retries} attempts: {last}")


def fetch_hills(hills, forecast_days=3, variables=None):
    """Fetch every hill, batched and paced to the free-tier call budget.

    Returns responses in the same order as `hills`.
    """
    global _last_chunk_at
    variables = variables or all_variables()
    per_chunk = call_weight(min(CHUNK, len(hills)), len(variables),
                            forecast_days)
    total = call_weight(len(hills), len(variables), forecast_days)
    # Seconds each chunk has to occupy for the minute average to stay legal.
    spacing = per_chunk / (TARGET_PER_MIN / 60.0)
    print(f"    {len(hills)} hills x {len(variables)} vars x {forecast_days}d"
          f" = ~{total:.0f} calls, one chunk every {spacing:.0f}s")

    out = []
    for i in range(0, len(hills), CHUNK):
        # Wait out whatever the previous chunk did not already use up. The
        # request's own latency counts, so a slow response costs no extra time.
        due = _last_chunk_at + spacing - time.monotonic()
        if due > 0:
            time.sleep(due)
        _last_chunk_at = time.monotonic()
        out.extend(_fetch_chunk(hills[i:i + CHUNK], variables, forecast_days))
    if len(out) != len(hills):
        raise RuntimeError(f"got {len(out)} responses for {len(hills)} hills")
    return out
