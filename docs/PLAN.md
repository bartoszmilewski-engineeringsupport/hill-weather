# Hill Weather: plan

A cloud-base and inversion forecast for British hills. Answers the one question
no mainstream weather app answers: will I be in the cloud, above it, or clear?

**Audiences:** hillwalkers and landscape photographers. Same rare phenomenon
(inversions), different framing.

**Price:** free, no ads, no accounts. Static hosting keeps running costs near
zero, and free is what carries it through a tight community by word of mouth.

Last updated 2026-08-22 (end of day).

---

## Where things stand

| Phase | State |
|---|---|
| 0. Housekeeping | Done |
| 1. Data pipeline | Done |
| 2. Validation harness | **Collecting. This is the open question.** |
| 3. Web app | Designed and built |
| 4. Soft launch | Not started |
| 5. Alerts | Not started |
| 6. Android, then iOS | Not started |

Live at **hillweather.co.uk** on the IONOS VPS at `/opt/hillweather`, serving
282 Munros, 214 Wainwrights and the 50 Hewitts of Snowdonia, rebuilding twice
daily behind Cloudflare.

Four pages: the forecast, **The week ahead**, **How to read this** and
**Contact**, plus a 404.

---

## Phase 0: Housekeeping (done)

- [x] DoBIH licence confirmed: **CC-BY 4.0**, commercial and derivative use
      permitted with attribution. `hillcsv.zip` is committed so a fresh clone
      runs with no download step.
- [x] Repo created at `C:\dev\hill-weather`, **not** in Google Drive, which
      corrupts `.git`.
- [x] Name and domains: **hillweather.co.uk** canonical, hillweather.uk
      registered and redirected to it. Both bought through Cloudflare.
- [ ] Email Open-Meteo about the request pattern. Their terms already confirm a
      free ad-free app is non-commercial, so this is about sizing, not
      permission. Draft is written.

## Phase 1: Data pipeline (done)

- [x] All 546 hills from DoBIH, region-aware from the first commit. A region
      is a list column plus an optional `where` predicate, because Hewitts
      run the length of England and Wales and membership alone would have
      pulled in the Pennines with Snowdonia.
- [x] Batched requests, 25 locations each, with backoff on 429.
- [x] Ephemeris: sunrise, sunset, golden and blue hour, sun azimuth. Validated
      to within a minute against an independent source.
- [x] Inversion strength score: clearance above cloud top, weighted by cover
      and layer depth, not just presence.
- [x] Light quality score, sampled at sunrise and sunset specifically. Low
      cloud counts against it normally but *for* it when you are above the
      cloud, which is the shot photographers want.
- [x] Split output: small summary per region plus per-hill detail on tap. One
      5.5 MB file was unusable on one bar of signal.
- [x] Scheduler inside the compose stack rather than host cron, so the schedule
      travels with the app.

**Two builds a day, not four.** Open-Meteo weights API calls by variable and
location count, so 496 hills four times daily exceeds the free tier. Measured,
not assumed.

## Phase 2: Validation (running, and it has started answering)

Everything else is polish until this is answered.

### The harness

`scripts/validate.py` scores the forecast against real observations.

```bash
python scripts/validate.py --fetch      # collect, ~1 minute per station
python scripts/validate.py --score      # the report
python scripts/validate.py --tune       # search constants on training data only
python scripts/validate.py --score --rh 75 --lcl 140   # test a candidate
```

- [x] Archive raw API responses, never derived answers, so any future tuning
      can be re-scored against every day collected.
- [x] `build.py --file <archive>` rebuilds from any archived day.
- [x] **A validation set that did not need waiting for.** Open-Meteo's
      previous-runs endpoint returns 60 days of history *with pressure
      levels*, from the same model the site forecasts with, and Iowa State's
      ASOS archive returns historical METAR going back decades. So paired
      (profile, observed cloud base) records exist today rather than in March.
      It also costs none of the daily forecast budget: different endpoint.
- [x] Scoring: cloud base error by regime, calibration, verdict confusion,
      Brier score against climatology and persistence baselines, on a
      chronological held-out third that tuning never sees.
- [ ] Summit observations: Cairngorm summit AWS, Fell Top Assessor, webcams.
- [ ] Fix the calibration, which is the real problem.

### Why airports

Almost nobody measures cloud base over a summit. Airports measure it every half
hour, for free, and report the two numbers the LCL formula takes as input,
temperature and dewpoint, alongside the base it is trying to predict.

This does **not** answer whether the method transfers to mountains: orographic
lift raises cloud base over a summit and the model's terrain is smoothed. But
if the physics is wrong over an airfield it cannot be right on Ben Nevis, so
it is the first question and the only one answerable now.

### What the measurement found, and what it fixed

**The single bug behind almost all of it.** `verdict()` treated the modelled
cloud base as exact. A hill 51 m below it got a 90% chance of a view; one 49 m
below got 5%. A hundred-metre cliff, on an input whose mean absolute error is
about 300 m. The forecast was far more confident than its own data justified,
and because the cliff always fell the pessimistic way, it cried wolf.

It is now probabilistic in the base as well as the cover:

    P(in cloud) = P(cloud present) x P(summit above the true base)

the second being a normal CDF over the margin, with `BASE_SIGMA` standing for
how well the base is actually known. A summit exactly at the modelled base now
reads 50%, which is the honest answer, instead of 5%.

**Held out, and never used for tuning:**

| | before | after |
|---|---|---|
| Brier score | 0.2019 | **0.1164** |
| skill vs climatology | **-29%** | **+20.6%** |
| accuracy | 75.6% | **83.4%** |
| beaten by answering "clear" always? | yes, 83.0% | **no** |
| when it says IN CLOUD, right | 39.6% | **50.8%** |
| worst calibration gap | +47 pts | **+23 pts** |
| cloud base mean abs error | 329 m | **290 m** |
| cloud base within 200 m | 37.3% | **43.8%** |

Every measure moved the same way, on data never used to choose anything.

**Cloud base by regime, held out:**

| observed ceiling | bias | mean abs error | within 200 m |
|---|---|---|---|
| 0 to 800 m, in among the hills | +117 m | **215 m** | **63.4%** |
| 800 to 1400 m, around the summits | -316 m | 366 m | 28.6% |
| above 1400 m, over everything | -1744 m | 1763 m | 6.8% |

### Two methodological traps, both nearly fallen into

**Brier will walk a forecast into the majority class.** Sweeping `LCL_K`, the
Brier score kept improving all the way to 200, but the cloud base error
bottomed at 140 to 150 and then climbed to 300 m. Past the optimum a larger
value simply makes every forecast more optimistic, which pays on a problem
where 83% of summit-hours are clear without being any more accurate. `LCL_K` is
therefore chosen on base error, the physical measure, not on Brier.

**A holdout stops being a holdout the moment you choose with it.** Sweeping
`BASE_SIGMA`, training preferred 500 and the held-out third kept improving past
650. 500 was taken. The held-out number is only worth having because nothing
was selected on it.

### Still wrong

- **Calibration is halved, not fixed.** The middle bands still run about 22
  points underconfident: when the site says 50%, the summit is clear about 74%
  of the time. Still too pessimistic, just far less so.
- **The 800 to 1400 m band**, where the Munros are, remains the weakest, at
  -316 m bias and 28.6% within 200 m.
- **Summer only.** Every hour of this is June to August. Winter is a different
  problem, with more low stratus and the inversions the site is built around.
  The model side of the data is a rolling 60-day window, so a re-fetch in late
  winter is needed to say anything about the season that matters most.
- **Airfields, not mountains.** Orographic lift raises cloud base over a summit
  and the model's terrain is smoothed. None of this proves the transfer.

### Success criteria

- Cloud base within 200 m on most days: **63.4% in the low regime, 43.8%
  overall. Not met, but close in the regime that matters.**
- Calibration within about 10 points: **worst gap +23. Not met.**
- Positive skill against climatology: **+20.6%. Met.**

The site is worth using for the first time. It is still not validated on
mountains, and every page still says so.

## Phase 3: Web app (designed and built)

Designed as a **newspaper**: cream paper (#FBF7F0), near-black ink (#2A2521),
Newsreader serif throughout, hairline rules, ochre accent (#A8763F). Desktop
first, collapsing to two columns then one. The direction was chosen from three
candidates; the other two are in `design/`.

- [x] Ranked list, grouped by **height band**. A single ranking put the
      smallest fells on top because they sit below the cloud: correct, and
      useless. Band headers say how many are clear, which turns the list into
      the answer people want.
- [x] **A lede written from the numbers.** Without it the page is 214
      percentages and the reader has to work out what kind of day it is
      themselves. Cases for an inversion, a clear day, a hopeless day and the
      usual in-between.
- [x] An elevation glyph per hill: the cloud layer as a band, the summit in
      section. The idea of the site in one drawing.
- [x] Per-hill detail: bagging lists, prominence, county, grid reference, OS
      Landranger sheet, what marks the summit, sun times with azimuth, hourly
      table.
- [x] **Descriptions from Wikipedia** (465 of 496, CC BY-SA 4.0, attributed)
      and **route links to Walkhighlands** (432 of 496, verified, never
      copied).
- [x] Share card as a front page, drawn on a canvas so it carries the date and
      the source wherever it is pasted.
- [x] Scotland leads; the region is then a remembered preference rather than a
      geolocation guess. Opt-in "nearest to me" for those who want it.
- [x] **How to read this**, the explainer for a first-time visitor.
- [x] **Contact form**, the one running service in the project.
- [x] **Search across both regions**, including Gaelic names, given as its own
      band. Nine hills show per band, so search is the only route to the other
      487 and nothing on the page had said so.
- [x] **Dark theme** as a warm inversion rather than a switch to slate. Three
      states: follow the device, force light, force dark.
- [x] **Link previews**, favicon and touch icon. Pasting the site into a
      walking group is the growth model, and it showed a bare URL.
- [x] **Usable on a phone.** 44px targets keyed on pointer rather than width,
      since a tablet is as much a finger as a phone is.
- [ ] Offline caching, so it works in a car park with no signal.
- [ ] A one-tap "what was it like up there?" report, which feeds Phase 2.

No map in v1. The ranked list is the product. See `design/MAP-BRIEF.md` for
where a map might go, and why it waits for validation.

## Phase 4: Soft launch

- [ ] One-tap "what was it actually like up there?" report. This is the
      observation network and it feeds Phase 2.
- [ ] Post to Walkhighlands and two or three hillwalking Facebook groups. Ask
      for feedback, not installs.
- [ ] **Approach Walkhighlands about a volunteer collaboration.** Worth going
      in able to say the site already links to ~87% of their hill pages, sends
      them traffic, has never copied a word, and credits them in every footer.
- [ ] Approach SAIS about an avalanche feed once there is something to show.

## Phase 5: Alerts

- [ ] Inversion alert by email or Telegram first, so the idea can be tested
      without an app.
- [ ] Fires roughly 15 to 20 mornings a year. Rare enough never to be spam.
- [ ] Then push, which is the real reason to go native.

## Phase 6: Android, then iOS

- [ ] Android: thin shell around the same static JSON, plus push.
- [ ] iOS: separate project, from 2026-09-03 when macOS access returns. Never
      mixed with the Android project.

---

## Regions

Scotland (Munros), the Lake District (Wainwrights) and Snowdonia (Hewitts of
DoBIH region 30B) are built and served: 546 hills. The Lakes were expected to
be a later expansion but cost almost nothing to add, and three things make
them more than extra coverage:

- **Better resolved.** Lakeland tops sit where model pressure levels are about
  215 m apart, not the 466 m gap between 900 and 850 hPa where Munro summits
  sit. The method should be more accurate there.
- **Better validation.** The Fell Top Assessors publish observed conditions from
  Helvellyn most winter days.
- **Bigger audience.** 214 Wainwrights within reach of Manchester, Leeds,
  Newcastle and Glasgow.

**Snowdonia**, added 2026-08-23, is the strongest case of the three for what
this site does. The 2 km grid smooths **155 m** off Cadair Idris against about
60 m off Ben Nevis, because Welsh peaks are sharper and more isolated, so
reading the profile at true summit height matters more there rather than less.
Coverage came out at 96% Wikipedia and 96% route links, better than either
existing region: Walkhighlands files the 2000 ft hills of England and Wales
under `/hewitts/`, and the slug guesser already tried both halves of a
compound name, so `Snowdon - Yr Wyddfa` resolves without special-casing.

**Still launch one region at a time.** "UK hills" reads generic; one region done
properly reads local. Scotland first, Lakes as the second announcement, even
though all three are already built.

### What fits next

API cost scales with hills, so the question for any new region is budget.
Scottish **Corbetts** (222, 762 to 914 m) would take the site to 768 hills and
fit; **Grahams** on top (231 more) would not leave enough margin. All Welsh
Hewitts is 136, and English Hewitts outside the Lakes is 65, which together
with the existing lists would make a national service of about 697.

SAIS avalanche data is Scotland only and does not extend.

---

## Rules to hold

1. **Never scrape MWIS or Walkhighlands.** Their words are their own editorial
   work and both are communities this project depends on. Link to them; never
   copy them. Wikipedia is the licensed source for prose, with attribution.
2. **Do not become a general outdoors app.** The moment it grows routes, gear
   lists and step counts, it is competing with OS Maps and Komoot and the
   reason anyone chose it disappears.
3. **Phones never call the weather API.** One build fetches, everyone reads the
   same static files.
4. **Be honest about uncertainty.** "Could go either way" is a feature. It is
   the thing every other weather app refuses to say.

---

## Traps worth remembering

Each of these cost real time and each looks like something it is not.

1. **`nginx.conf` needs the container recreated.** Editing it does nothing, and
   `docker compose up -d` will not do it either: compose sees an unchanged
   service definition and leaves the container running.
2. **Stale assets look exactly like code bugs.** A four-hour CDN cache on the
   stylesheet, served against new markup, produced giant icons and a collapsed
   layout while the origin was entirely correct. Fixed for good with
   content-hashed URLs (`scripts/version_assets.py`).
3. **Purge Cloudflare after a manual rebuild**, or the old forecast serves for
   half an hour and looks like a failed build.
4. **Do not stack manual builds.** Three inside twenty minutes exhausted the
   hourly API budget and everything failed for an hour after.
5. **A silent build is usually a backoff, not a hang.** Check with
   `docker compose exec scheduler ps` before assuming the worst.
6. **The API limit that bites is per minute, not per hour.** A build two hours
   after the previous one still hit a 429 on its first request, because the
   archive stage finishes and the build stage starts seven seconds later,
   firing 25-hill chunks a second apart behind the heaviest requests the site
   makes. The fix is pacing, not fewer hills, which is why adding regions is
   cheaper than it looks.
7. **An SPA fallback in nginx is a soft 404.** `try_files ... /index.html`
   returned the whole site with HTTP 200 for every address that does not
   exist, which search engines read as unlimited duplicate pages. The site
   routes on the URL hash and never on the path, so it bought nothing.
8. **`server_name _` is not a catch-all.** It is a name matching no real host.
   A block gets unmatched traffic only because it is the FIRST block on that
   port. Adding a server block above it steals the default and, in this case,
   took the site down: the apex matched nothing, fell through to a www
   redirect and bounced to itself. Fixed with an explicit `default_server`.
9. **Cloudflare caches redirects for hours.** A `return 301` never reaches the
   `location` blocks that set short cache headers, so it ships bare and
   Cloudflare applies a multi-hour default. That outlived the fix. Purge after
   any redirect mistake, not just after a rebuild.
10. **Test the hostname you did not touch.** Adding the www redirect, www was
   verified and passed while the apex was broken.

When something looks wrong in the browser, check what is actually being served
before trusting local rendering. One curl settles it.

## Open questions

- Open-Meteo request sizing at this volume, and whether self-hosting their API
  server on the DL360 is worth doing.
- Whether SAIS will provide a feed.
- **Does the forecast actually match reality?** Unanswered until Phase 2
  produces data. Everything else is secondary to this.
