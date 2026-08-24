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

### First findings, ~7,000 paired hours, 5 stations, 60 days

**Regime matters more than anything.** A first run showed skill of minus 110%
against climatology, which was a flaw in the scoring rather than the forecast.
The LCL predicts the base of cloud lifted from the surface, which is what hill
fog and low stratus are, and says nothing useful about a deck at 3000 m. Those
hours, where no British summit is anywhere near the cloud, were dominating a
single average. Split by how low the cloud actually was:

| observed ceiling | bias | mean abs error | within 200 m |
|---|---|---|---|
| 0 to 800 m, in among the hills | **+51 m** | **191 m** | **67.5%** |
| 800 to 1400 m, around the summits | -399 m | 418 m | 19.6% |
| above 1400 m, over everything | -1697 m | 1706 m | 3.7% |

So the method is respectable exactly where it is asked the real question, and
poor in the band where Munro summits actually sit. That band is the work.

**The forecast is far too pessimistic.** This is the headline failure and it is
calibration, not cloud base. When the site says a 0 to 20% chance of a view,
the summit was actually clear **54%** of the time. Every band is
underconfident, by 47 points at the low end. The verdict errors are lopsided in
the same direction: 3,590 "said in cloud, was clear" against 490 the other way.

**The plain accuracy number is worse than saying nothing.** 75.6% of summit
hours are judged correctly, but 83.0% of them were clear, so a model that
answered "clear" every single time and knew nothing at all would score higher.
When the site says IN CLOUD it is right 39.6% of the time; when it says CLEAR
it is right 95.5%. It catches 82.7% of genuinely clouded summits. That is a
very sensitive, very imprecise detector: it almost never promises a view that
is not there, and it talks people out of days they should have gone on.
It cries wolf.

**Negative skill so far.** Brier 0.202 against climatology's 0.157, so -29%:
worse than always predicting the base rate. It does beat persistence (0.253). A forecast that cannot beat climatology has no value yet, and saying
so plainly is the point of measuring.

**Tuning helps a little and generalises.** A search on the training half picked
`RH_MOIST=75, LCL_K=140` over the current `85, 125`, and it held up on the
held-out third it had never seen: mean absolute error 330 to 306 m, median 284
to 250, within-200 m 37.6% to 42.0%, Brier 0.2163 to 0.2099. Real, but small
relative to the calibration problem, and **not yet applied to production.**

### What the numbers say to do next

1. **Fix calibration before anything else.** `verdict()` turns "the modelled
   base is below the summit" into a near-certainty of cloud, when broken cover
   at summit level means in and out. The probability should reflect cover
   fraction and the margin between base and summit, not saturate.
2. **Then the 800 to 1400 m band**, which is where the Munros are.
3. **Then summit observations**, to find out how much of this transfers off
   the airfield.

### Success criteria

- Cloud base within 200 m on most days, in the low regime. Currently 67.5%
  there, but only 37% across the hill-relevant range: **partly met**.
- Calibration within about 10 points across the range. Currently out by up to
  46: **not met**.
- Positive skill against climatology. Currently -29%: **not met**.

Honest position: the method is not yet good enough to be trusted, the site says
so on every page, and now there is a measurement instead of an opinion.

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
