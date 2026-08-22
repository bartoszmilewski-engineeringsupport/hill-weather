#!/usr/bin/env python3
"""
Solar position and event times - NOAA algorithm, standard library only.

Kept dependency-free on purpose so the pipeline runs anywhere (GitHub Actions,
a Pi, a laptop) with no install step.

What the app needs from this:
  - sunrise / sunset                     (walkers: how much daylight have I got)
  - golden and blue hour                 (photographers: when is the light)
  - sun AZIMUTH at sunrise and sunset    (photographers: where will it come from)

Accurate to well under a minute for our latitudes, which is far better than the
weather forecast it sits next to.
"""

import math
from datetime import datetime, timedelta, timezone

# Zenith angles defining each event. 90.833 includes atmospheric refraction and
# the solar disc radius - the standard sunrise/sunset definition.
ZENITH = {
    "sunrise": 90.833,
    "golden": 84.0,      # sun 6 deg up: end of the warm light
    "civil": 96.0,       # sun 6 deg down: blue hour outer edge
    "blue": 94.0,        # sun 4 deg down
}


def _julian_day(dt):
    """Julian day from a UTC datetime."""
    y, m = dt.year, dt.month
    d = (dt.day + dt.hour / 24 + dt.minute / 1440 + dt.second / 86400)
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return (math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1))
            + d + b - 1524.5)


def _sun_params(jd):
    """Return (declination deg, equation of time minutes) for a Julian day."""
    t = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    mr = math.radians(m)
    c = (math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(2 * mr) * (0.019993 - 0.000101 * t)
         + math.sin(3 * mr) * 0.000289)
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    lam = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))

    decl = math.degrees(math.asin(math.sin(math.radians(eps))
                                  * math.sin(math.radians(lam))))

    y = math.tan(math.radians(eps / 2)) ** 2
    l0r = math.radians(l0)
    eot = 4 * math.degrees(
        y * math.sin(2 * l0r)
        - 2 * e * math.sin(mr)
        + 4 * e * y * math.sin(mr) * math.cos(2 * l0r)
        - 0.5 * y * y * math.sin(4 * l0r)
        - 1.25 * e * e * math.sin(2 * mr))
    return decl, eot


def event_time(date, lat, lon, event="sunrise", morning=True):
    """UTC datetime of a solar event, or None if it does not occur that day.

    None is a real answer this far north - in June the sun never gets 6 degrees
    below the horizon in Scotland, so there is no true blue hour at all.
    """
    noon_utc = datetime(date.year, date.month, date.day, 12,
                        tzinfo=timezone.utc)
    decl, eot = _sun_params(_julian_day(noon_utc))
    zen = math.radians(ZENITH[event])
    latr, declr = math.radians(lat), math.radians(decl)

    cos_ha = ((math.cos(zen) - math.sin(latr) * math.sin(declr))
              / (math.cos(latr) * math.cos(declr)))
    if not -1 <= cos_ha <= 1:
        return None                      # sun never reaches that altitude today

    ha = math.degrees(math.acos(cos_ha))
    solar_noon_min = 720 - 4 * lon - eot
    minutes = solar_noon_min + (-4 * ha if morning else 4 * ha)
    return (datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
            + timedelta(minutes=minutes))


def position(dt_utc, lat, lon):
    """Return (elevation deg, azimuth deg from north) at a UTC datetime."""
    decl, eot = _sun_params(_julian_day(dt_utc))
    latr, declr = math.radians(lat), math.radians(decl)

    minutes = dt_utc.hour * 60 + dt_utc.minute + dt_utc.second / 60
    true_solar = (minutes + eot + 4 * lon) % 1440
    ha = true_solar / 4 - 180                       # degrees, 0 at solar noon
    har = math.radians(ha)

    zen = math.acos(math.sin(latr) * math.sin(declr)
                    + math.cos(latr) * math.cos(declr) * math.cos(har))
    elev = 90 - math.degrees(zen)

    if abs(math.sin(zen)) < 1e-9:
        return elev, 0.0
    cos_az = ((math.sin(declr) - math.sin(latr) * math.cos(zen))
              / (math.cos(latr) * math.sin(zen)))
    az = math.degrees(math.acos(max(-1.0, min(1.0, cos_az))))
    if ha > 0:
        az = 360 - az
    return elev, az


def compass(deg):
    if deg is None:
        return ""
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[int((deg % 360) / 22.5 + 0.5) % 16]


def day_summary(date, lat, lon):
    """Everything the app shows for one hill on one day."""
    def iso(dt):
        return dt.replace(microsecond=0).isoformat() if dt else None

    sunrise = event_time(date, lat, lon, "sunrise", morning=True)
    sunset = event_time(date, lat, lon, "sunrise", morning=False)
    out = {
        "sunrise": iso(sunrise),
        "sunset": iso(sunset),
        "golden_morning_end": iso(event_time(date, lat, lon, "golden", True)),
        "golden_evening_start": iso(event_time(date, lat, lon, "golden", False)),
        "blue_morning_start": iso(event_time(date, lat, lon, "blue", True)),
        "blue_evening_end": iso(event_time(date, lat, lon, "blue", False)),
        "sunrise_azimuth": None,
        "sunset_azimuth": None,
        "daylight_hours": None,
    }
    if sunrise and sunset:
        out["sunrise_azimuth"] = round(position(sunrise, lat, lon)[1], 1)
        out["sunset_azimuth"] = round(position(sunset, lat, lon)[1], 1)
        out["daylight_hours"] = round((sunset - sunrise).total_seconds() / 3600, 2)
    return out


if __name__ == "__main__":
    from datetime import date as _date
    for name, lat, lon in [("Ben Nevis", 56.7969, -5.0036),
                           ("Helvellyn", 54.5270, -3.0166)]:
        s = day_summary(_date.today(), lat, lon)
        print(f"{name}:")
        print(f"   sunrise {s['sunrise']}  az {s['sunrise_azimuth']}"
              f" ({compass(s['sunrise_azimuth'])})")
        print(f"   sunset  {s['sunset']}  az {s['sunset_azimuth']}"
              f" ({compass(s['sunset_azimuth'])})")
        print(f"   daylight {s['daylight_hours']} h")
