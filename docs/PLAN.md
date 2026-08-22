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
282 Munros and 214 Wainwrights, rebuilding twice daily behind Cloudflare.

Three pages: the forecast, **How to read this**, and **Contact**.

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

- [x] All 496 hills from DoBIH, region-aware from the first commit.
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

## Phase 2: Validation (the long pole, running now)

Everything else is polish until this is answered.

- [x] Archive raw API responses, never derived answers, so any future tuning
      can be re-scored against every day collected.
- [x] `build.py --file <archive>` rebuilds from any archived day. The backtest
      harness and the production pipeline are the same code.
- [ ] Webcam list: Nevis Range, Cairngorm, Glencoe.
- [ ] Ingest Lake District Fell Top Assessor reports. A professional human
      observation from Helvellyn most winter days, far better ground truth
      than a webcam.
- [ ] Daily capture of stills alongside the matching forecast.
- [ ] Score sheet: predicted cloud base against observed, per hill per day.
- [ ] Tune `RH_MOIST`, `LOW_CLOUD_MIN`, `CLEAR_MARGIN` in `scripts/physics.py`.

**Success criterion: cloud base right to within ~200 m on most days.** If it is
not, no amount of app polish saves this. Better to know in week four than in
month six.

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

Scotland (Munros) and the Lake District (Wainwrights) are both built and
served. The Lakes were expected to be a later expansion but cost almost nothing
to add, and three things make them more than extra coverage:

- **Better resolved.** Lakeland tops sit where model pressure levels are about
  215 m apart, not the 466 m gap between 900 and 850 hPa where Munro summits
  sit. The method should be more accurate there.
- **Better validation.** The Fell Top Assessors publish observed conditions from
  Helvellyn most winter days.
- **Bigger audience.** 214 Wainwrights within reach of Manchester, Leeds,
  Newcastle and Glasgow.

**Still launch one region at a time.** "UK hills" reads generic; one region done
properly reads local. Scotland first, Lakes as the second announcement, even
though both are already built.

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

When something looks wrong in the browser, check what is actually being served
before trusting local rendering. One curl settles it.

## Open questions

- Open-Meteo request sizing at this volume, and whether self-hosting their API
  server on the DL360 is worth doing.
- Whether SAIS will provide a feed.
- **Does the forecast actually match reality?** Unanswered until Phase 2
  produces data. Everything else is secondary to this.
