# Hill Weather: plan

A cloud-base and inversion forecast for British hills. Answers the one question
no mainstream weather app answers: will I be in the cloud, above it, or clear?

**Audiences:** hillwalkers and landscape photographers. Same rare phenomenon
(inversions), different framing.

**Price:** free, no ads, no accounts. Static hosting keeps running costs near
zero, and free is what carries it through a tight community by word of mouth.

Last updated 2026-08-22.

---

## Where things stand

| Phase | State |
|---|---|
| 0. Housekeeping | Done |
| 1. Data pipeline | Done |
| 2. Validation harness | **Collecting. This is the open question.** |
| 3. Web app | Working, unpolished |
| 4. Soft launch | Not started |
| 5. Alerts | Not started |
| 6. Android, then iOS | Not started |

Live on the IONOS VPS at `/opt/hillweather`, serving 282 Munros and 214
Wainwrights, rebuilding twice daily.

---

## Phase 0: Housekeeping (done)

- [x] DoBIH licence confirmed: **CC-BY 4.0**, commercial and derivative use
      permitted with attribution. `hillcsv.zip` is committed so a fresh clone
      runs with no download step.
- [x] Repo created at `C:\dev\hill-weather`, **not** in Google Drive, which
      corrupts `.git`.
- [x] Name and domains: **hillweather.uk** canonical, hillweather.co.uk
      registered and redirected.
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

## Phase 3: Web app (working, needs work before launch)

- [x] Ranked list, region and day tabs, sortable by view, inversion or light.
- [x] Per-hill hourly detail fetched on tap and cached.
- [x] Disclaimer and attribution in the footer.
- [x] Deployed behind Nginx Proxy Manager with Let's Encrypt.
- [ ] **Ranking needs rethinking.** With all 496 hills in, the top of the list
      is small fells that are simply below cloud base. Correct, but nobody
      drives to the Lakes for Bleaberry Fell. Weight by height or prominence so
      it answers "which decent hill is clear".
- [ ] Share card image. This is the marketing and matters more than it looks.
- [ ] Offline caching, so it works in a car park with no signal.

No map in v1. The ranked list is the product.

## Phase 4: Soft launch

- [ ] One-tap "what was it actually like up there?" report. This is the
      observation network and it feeds Phase 2.
- [ ] Post to Walkhighlands and two or three hillwalking Facebook groups. Ask
      for feedback, not installs.
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

1. **Never scrape MWIS.** Their forecast text is copyrighted and the community
   depends on the service. Link to them; do not compete.
2. **Do not become a general outdoors app.** The moment it grows routes, gear
   lists and step counts, it is competing with OS Maps and Komoot and the
   reason anyone chose it disappears.
3. **Phones never call the weather API.** One build fetches, everyone reads the
   same static files.
4. **Be honest about uncertainty.** "Could go either way" is a feature. It is
   the thing every other weather app refuses to say.

---

## Open questions

- Open-Meteo request sizing at this volume, and whether self-hosting their API
  server on the DL360 is worth doing.
- Whether SAIS will provide a feed.
- **Does the forecast actually match reality?** Unanswered until Phase 2
  produces data. Everything else is secondary to this.
