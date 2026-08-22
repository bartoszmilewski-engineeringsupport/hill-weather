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

# Open-Meteo weights a request by variables x locations x days, so the full set
# above times 496 hills trips the free-tier rate limit. The live build asks only
# for what physics.py actually reads; the archive keeps everything, because it
# is only ~40 hills and we cannot re-fetch the past if we later want a variable
# we did not save.
BUILD_SURFACE_VARS = [
    "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high",
    "precipitation", "freezing_level_height", "wind_gusts_10m",
]
BUILD_LEVEL_VARS = ["temperature", "relative_humidity",
                    "wind_speed", "wind_direction", "geopotential_height"]

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


def _fetch_chunk(hills, variables, forecast_days, retries=4):
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
            # Rate limited. Back off hard rather than hammering a free service.
            wait = 30 * (attempt + 1)
            print(f"    rate limited, waiting {wait}s")
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"fetch failed after {retries} attempts: {last}")


def fetch_hills(hills, forecast_days=3, variables=None, pause=1.0):
    """Fetch every hill, batched. Returns responses in the same order."""
    variables = variables or all_variables()
    out = []
    for i in range(0, len(hills), CHUNK):
        out.extend(_fetch_chunk(hills[i:i + CHUNK], variables, forecast_days))
        if i + CHUNK < len(hills):
            time.sleep(pause)          # be a good citizen on a free API
    if len(out) != len(hills):
        raise RuntimeError(f"got {len(out)} responses for {len(hills)} hills")
    return out
