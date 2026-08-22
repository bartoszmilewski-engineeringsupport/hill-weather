# Hill Weather

Cloud base and inversion forecasts for British hills — the one question no
mainstream weather app answers: **will I be in the cloud, above it, or clear?**

Free, non-commercial, no ads, no accounts. Covers all 282 Munros and 214
Wainwrights.

**Status: unvalidated.** The physics is defensible but has not yet been checked
against observations. See [Validation](#validation).

---

## Why it exists

Forecast models smooth terrain badly. A 2 km model shaves ~60 m off Ben Nevis;
a global 25 km model flattens the Highlands into a gentle bump. So when a
weather app shows "Ben Nevis, 8°C, light wind", it is describing a mountain
that does not exist.

This project takes the **pressure-level profile** — temperature, humidity, wind
and geopotential height at each level up through the atmosphere — and
interpolates it to the **true summit height**. From that, cloud base falls out,
and with it the three answers that matter:

- summit **in** cloud — save your petrol
- summit **above** cloud — an inversion, the best day of the year
- **clear**

Nothing else publishes which hills are likely to be poking above a cloud sea
tomorrow morning.

## How it works

```
Open-Meteo (UK Met Office 2 km, pressure levels)
        |
        +--> archive.py   raw responses, gzipped, kept forever  -> archive/
        |                 ~40 validation hills, all 75 variables
        |
        +--> build.py     all 496 hills, minimal variables
                 |
                 +--> physics.py   cloud base, inversion, light scores
                 +--> solar.py     sunrise/sunset, golden hour, sun azimuth
                 |
                 v
            web/data/<region>/summary.json   ranked list, ~30 kB gzipped
            web/data/<region>/hills/*.json   hourly detail, fetched on tap
```

Two independent cloud-base estimates, cross-checked:

| Method | Good for | Limitation |
|---|---|---|
| **LCL** — lift a glen-level parcel, `125 × (T − Td)` | Orographic hill fog, which is most of what Scotland produces | Says where cloud *would* form, not that it exists — so it is gated on actual low-cloud cover |
| **RH profile** — lowest level crossing a moist threshold | Layer cloud, and finding the cloud *top* (which is what reveals inversions) | Model levels are 215–466 m apart; Munro summits sit in the widest gap |

Output is deliberately **probabilistic**. Broken cloud means the summit is in
and out of it, and saying so is more useful than a confident icon that is wrong.

## Running it

Python 3.9+, standard library only. No dependencies, no install step.

```bash
python scripts/hills.py                  # check the hill lists load
python scripts/archive.py                # collect a validation snapshot
python scripts/build.py                  # live build, all 496 hills (~7 min)
python scripts/archive.py --status       # how much history exists
```

Serve locally:

```bash
python -m http.server 8000 --directory web
```

Rebuild from an archived day instead of fetching — this is the backtest path,
and the reason the archive stores raw responses rather than derived answers:

```bash
python scripts/build.py --file archive/lakes/2026-08-22T08Z.json.gz
```

## Deployment

Static site on the IONOS VPS, same pattern as the other sites there
(`nginx:alpine` in `/opt/<name>`, Nginx Proxy Manager terminating SSL).

```bash
cd /opt/hillweather/deploy && docker compose up -d
```

NPM proxy host: `hillweather.uk` → `http://<vps-ip>:5003`, Let's Encrypt on.

Cron, twice daily — Open-Meteo weights API calls by variable and location
count, so four builds a day would exceed the free tier:

```
15 5,16 * * *  /opt/hillweather/deploy/run-pipeline.sh >> /var/log/hillweather.log 2>&1
```

## Validation

The honest state of the project. The maths is sound; whether it matches
reality is untested.

The plan: score archived forecasts against the Nevis Range, Cairngorm and
Glencoe webcams, and against the Lake District Fell Top Assessor reports —
a professional human observation from Helvellyn most winter days, which is far
better ground truth than a webcam.

**Target: cloud base right to within ~200 m on most days.** If it is not, no
amount of app polish saves this.

The constants to tune live at the top of `scripts/physics.py`: `RH_MOIST`,
`LOW_CLOUD_MIN`, `CLEAR_MARGIN`.

## Rules this project holds to

1. **Never scrape MWIS.** Their forecast text is copyrighted and the hill
   community depends on the service. Link to them; do not compete.
2. **Phones never call the weather API.** One build fetches, everyone reads the
   same static files. That is what keeps this inside the free tier at any scale.
3. **Not a general outdoors app.** No routes, no gear lists, no step counting —
   that road ends with a worse OS Maps.
4. **Be honest about uncertainty.** "Could go either way" is a feature.

## Attribution

- Weather: [Open-Meteo](https://open-meteo.com), UK Met Office 2 km
  deterministic model. CC-BY 4.0.
- Hills: [Database of British and Irish Hills](https://www.hill-bagging.co.uk/dobih)
  v18.5. CC-BY 4.0.

Planning aid only — not a substitute for [MWIS](https://www.mwis.org.uk) or,
in winter, [SAIS](https://www.sais.gov.uk).
