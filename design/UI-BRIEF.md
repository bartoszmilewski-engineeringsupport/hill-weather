# Brief: redesign the Hill Weather website

Paste this into Claude Design. It is written to stand alone.

---

## The product

**hillweather.co.uk** is a free, non-commercial forecast for British hills. It
answers one question no mainstream weather app answers: **will the summit be in
cloud, above it, or clear?**

Cloud has a bottom. On a typical day it might sit at 700 metres: below that line
you can see for miles, above it you are inside a grey nothing with fifteen
metres of visibility. That line is the *cloud base*, and which side of it a
summit falls on decides whether the day was worth the drive. The site computes
it for all 282 Munros and all 214 Wainwrights, twice a day.

It is live, built and run by one person, with no company behind it, no ads, no
accounts and nothing for sale.

### Who uses it

- **Hillwalkers** deciding where to go this weekend. Munro and Wainwright
  baggers, obsessive about lists, used to reading maps.
- **Landscape photographers** chasing **cloud inversions**: cold air trapped in
  the valleys, cloud filling the glens, the tops standing clear above a white
  sea. Maybe twenty mornings a year, and they will drive through the night for
  one.

Both are checking on a phone, often outdoors, often on one bar of signal, often
before dawn.

---

## What is settled, and should not be reopened

**The aesthetic is a newspaper.** Warm cream paper, near-black ink, one serif
throughout, hairline rules, section heads in letter-spaced small caps, a single
ochre accent. Restrained, printed, quiet. It should feel like it was made by
someone who actually walks these hills, not by a weather company.

This was chosen from three candidates and the others were rejected for reasons
worth keeping: a dark, data-dense "instrument" direction was rejected as
generic, and a cartographic direction as too busy. **Do not propose a dark-first
or dashboard-style redesign.** A dark *theme* exists and should stay, but it is
a warm inversion of the same design (near-black brown, warm off-white), not a
different personality.

Current tokens:

```
paper   #FBF7F0     ink      #2A2521     muted   #6B6156
faint   #8C8175     rule     #DCD2C0     hair    #EDE5D7
ochre   #A8763F     clear    #3F6B4A     edge    #8A6A2E     in cloud #9C4B36
Type: Newsreader (Google Fonts), everything. Hierarchy from size and weight.

Dark: paper #16140F, ink #EFE8DB, ochre #CC9A5B, clear #86C495,
      edge #DBB165, in cloud #DE8F79
```

**Honest uncertainty is a feature, not a wrinkle to smooth out.** The forecast
gives a *chance* of a view rather than a verdict, and says "could go either way"
where it genuinely is. It also carries a prominent notice that the method has
not yet been checked against real observations. Any design must keep that
visible rather than tidying it into a footnote.

---

## What exists now

### Page 1: the forecast

- Masthead, then navigation: region (Scottish Highlands / Lake District), day
  (three days), theme switch, links to the other pages.
- A full-width **search band**: all 496 hills, both regions, Gaelic names too.
- A **lede**: an opening paragraph generated from the numbers, not a table.
  Real examples from the live site:
  - *"The tops are in cloud. Everything below about 948 m is clear."* with
    *"Cloud base runs from 715 m to 1,243 m across the Lake District. 166 of 214
    tops should stay out of it, the highest of them Blencathra at 868 m. Go low
    today and you will still get your view."*
  - *"A cloud inversion is possible, with tops standing clear above the deck."*
  - *"In cloud everywhere. A day for the valleys."*
- An **at a glance** panel: cloud base range, freezing level, sunrise, tops clear.
- Hills grouped into **height bands**, each with a header saying how many are
  clear. Nine hills shown per band, the rest summarised as a count.
- Each hill row: a small **elevation glyph** (the hill in section with the cloud
  layer drawn across it), name, height, a phrase like "210 m below cloud" or
  "well inside", and a large percentage.
- Tapping a hill expands: bagging lists, prominence, county, grid reference, OS
  Landranger sheet, what marks the summit, a Wikipedia description, links to a
  map, Walkhighlands routes and Hill-bagging, sun times with compass bearings,
  and an hourly table.

### Page 2: How to read this

An explainer for a first-time visitor. Why cloud base matters, why other
forecasts get summits wrong, why the number is a chance not a promise, a
three-case diagram (below the cloud, inside it, above it), and a glossary.

### Page 3: Contact

A form, plus a note on what the project is and what is worth writing about.

---

## What is open, and where the design is weakest

This is the useful part. Everything below is a real problem with the current
design.

**1. Too much furniture before the content.** On desktop the first hill sits
around 290 px down; on a phone the masthead and navigation take a third of the
screen before anything useful. The masthead is handsome and possibly too
generous.

**2. Only nine hills per band are shown**, and the remainder is a flat line of
text: *"36 more in this band, all in cloud"*. That is honest but weak. What
should the other 487 hills look like? Progressive disclosure, a denser
secondary tier, something else?

**3. Time matters more than the design admits.** Measured across all 496 hills:
the median area swung **72 percentage points across three days**, and the whole
western Highlands went from 0% of tops clear on Saturday to 100% on Monday.
Weather sweeps the whole country, so on most days the honest question is *which
day* rather than *which hill*. Right now the three days are three small tabs.
They may deserve to be the primary axis: a comparison, a small-multiple, a
scrubber.

**4. Hill detail is a two-column data dump.** Everything is present and nothing
is composed. A hill has a description, a photograph's worth of character, a
grid reference, an hourly profile and a route link. It should read like an
entry in a good guidebook.

**5. The elevation glyph is small and does very little.** It is the single
clearest expression of the whole idea and it is 56 px wide in a corner of each
row. It could carry far more, at any size.

**6. There is no sense of place.** No geography anywhere, so 496 hills are a
list with no spatial meaning. A relief map is briefed separately
(`MAP-BRIEF.md`) and is deliberately not being built yet, but the list itself
could still convey where things are.

**7. The at-a-glance panel is underused.** Four numbers in a sidebar. On an
inversion morning it should probably be shouting.

**8. Nothing celebrates the good day.** An inversion is the best morning of the
year and the page treats it as one more headline variant. It could be the moment
the design earns its keep.

---

## Constraints

- **Static files only.** No backend for the forecast, no build step, no
  framework. Everything is hand-written HTML, one stylesheet, a little vanilla
  JavaScript. Fancy layout is fine; a React app is not.
- **Must work on one bar of signal.** The whole forecast is pre-built JSON, the
  summary is about 30 kB gzipped, and hill detail is fetched only on tap.
- **Phone matters as much as desktop.** Touch targets are 44 px. Design desktop
  first, but a layout that collapses badly is not acceptable.
- **Screenshot-shareable.** The growth model is somebody pasting a picture into
  a walking group on a Friday night. There is a generated share card; the page
  itself should also survive being screenshotted.
- **Only Google Fonts are available** for typefaces. No other external assets at
  all.
- **Never imply more certainty than exists.**

---

## Data available per hill

Name and Gaelic name, height, prominence, geographic area, county, grid
reference, OS Landranger sheet, what marks the summit (trig point, cairn,
shelter), which bagging lists it belongs to, latitude and longitude.

Per day: chance of a view as a percentage, the range across the day, cloud base
and cloud top in metres, a verdict (CLEAR / ON THE EDGE / IN CLOUD / ABOVE
CLOUD), an inversion score 0-100, a sunrise light score, freezing level.

Per hour: view chance, cloud base and top, summit temperature, wind speed and
direction.

Per day and hill: sunrise and sunset with compass bearings, golden and blue
hour, daylight hours.

Plus a Wikipedia description for 465 of 496, and a Walkhighlands route link for
432 of 496.

Regions: Scottish Highlands (282 Munros, 915 to 1345 m) and the Lake District
(214 Wainwrights, 290 to 978 m).

---

## What to produce

Artboards at desktop width, with a phone version of at least the forecast page.

1. **The forecast page, ordinary day.** The common case: tops in cloud, low
   fells clear. This is what the site looks like most of the time and it is the
   one that has to work.
2. **The forecast page, inversion morning.** The rare good day. Should feel
   different from the ordinary one without becoming a different site.
3. **A hill, expanded.** Composed like a guidebook entry rather than a data
   dump.
4. **The three days together.** An answer to weakness 3: how does the design
   let someone see that Monday is the day?
5. **Phone.** The forecast page at 390 px, one-handed, with less furniture
   before the content.
6. **How to read this.** The explainer, since a first-time visitor understanding
   the idea is the difference between the site working and not.

Keep the newspaper direction. Push on composition, hierarchy, density and the
moments the current design underplays.
