# Handoff: Hill Weather redesign (hillweather.co.uk)

## Overview
A full redesign of the Hill Weather forecast site — cloud base & inversions for
all 282 Munros and 214 Wainwrights. Newspaper aesthetic: warm cream paper,
near-black ink, one serif (Newsreader), hairline rules, letter-spaced small
caps, single ochre accent. This package covers: the forecast page (ordinary day
and inversion morning), the expanded hill entry, the three-day comparison, the
phone layout, the "How to read this" explainer, the dark theme, two share
cards, and the animated inversion hero.

## About the design files
`design-reference/Hill Weather UI.dc.html` is a **design reference created in
HTML** — a canvas of artboards showing intended look and behaviour, not
production code to copy wholesale. The task is to **recreate these designs in
the site's real environment: hand-written static HTML, one stylesheet, a little
vanilla JavaScript. No framework, no build step.** Two pieces ARE
production-ready as written and can be lifted directly: the animated hero SVG
(`snippets/inversion-hero.svg.html`) and the glyph generator
(`snippets/hill-glyph.js`).

Open the design reference in a browser and pan/zoom. Artboards are labelled:

| Board | What it is |
|-------|------------|
| **2a** | Forecast page, ordinary day, desktop 1360 — **the primary spec** |
| **2b** | Forecast page, inversion morning (with animated hero) |
| **2c** | A hill expanded — guidebook entry (Ben Macdui) |
| **2d** | The three days together ("Tuesday is the day") |
| **2e** | Phone, 390 px |
| **2f** | How to read this |
| **3a** | Dark theme (desktop forecast) |
| **3b/3c** | Share cards, 1200×630 (inversion / ordinary) |
| **3d** | Share card, inversion, dark |
| **3e** | Phone, dark theme |
| 1a–1f | Earlier iteration — superseded by turn 2; ignore except for reference |

## Fidelity
**High-fidelity.** Colors, type sizes, spacing, rules and copy tone are final.
Recreate pixel-perfectly. All measurements below are CSS px at the artboard
widths (1360 desktop / 390 phone); use relative units where sensible.

## Hard constraints (from the product brief — do not violate)
- Static files only. No backend, no build step, no framework.
- Must work on one bar of signal: summary ~30 kB gzipped; hill detail fetched only on tap.
- Touch targets ≥ 44 px on phone.
- Only Google Fonts (Newsreader). No other external assets.
- Never imply more certainty than exists: the unverified-method notice and
  "a chance, not a promise" language must stay visible, never a footnote.

## Design tokens
See `tokens.css` — complete light + dark palettes as CSS custom properties,
with usage comments. Dark is a warm inversion of the same design (near-black
brown paper #16140F, warm off-white ink #EFE8DB, ochre #CC9A5B), not a
different personality. Theme switch = `data-theme="dark"` on `<html>`.

**Typography — Newsreader everywhere.** Load with
`family=Newsreader:ital,opsz,wght@0,6..72,400..700;1,6..72,400..700`.
Scale (desktop): masthead 58/600; page headline 42–46/500, line-height 1.18;
lede paragraph 17.5/400 muted, lh 1.65; band header 17 letter-spacing .22em
caps; hill name 19.5/400; hill meta 13.5 italic faint; hill % 26/400 in verdict
colour; small caps labels 12–13.5 with .13–.32em tracking; italic ochre band
notes 14.5. Phone: headline 24, names 16.5, % 21. Never below 12 px.

## Screens

### 2a — Forecast page, ordinary day (desktop)
Layout, top to bottom (all inside 56 px side padding):
1. **Top bar**: date left, "FREE · NO ACCOUNTS · NO ADVERTISING" right —
   12.5 px caps, .2em, muted. Below: 2 px ink rule.
2. **Masthead**: centered "Hill Weather" 58/600, then tagline
   "CLOUD BASE & INVERSIONS FOR BRITISH HILLS" 13.5 px, .32em, ochre.
   1 px ink rule below.
3. **Nav row**: regions left (SCOTTISH HIGHLANDS / LAKE DISTRICT), dated day
   tabs right (SUN 23 AUG / MON 24 AUG / TUE 25 AUG) — 13.5 px caps .16em.
   Active item: ink, weight 600, 2 px ochre underline. Inactive: muted, hover
   ink+underline. Second row: NEAREST TO ME · HOW TO READ THIS · ☀ THEME ·
   SHARE. 1 px ink rule below.
4. **Search band** (full width, prominent): 1 px muted border box on raised
   paper, 13 px padding, magnifier icon (stroked circle+line, 19 px), italic
   19 px muted placeholder "Find a hill by name…", right-aligned hint
   "ALL 496 HILLS · PRESS /" with a bordered `/` keycap. `/` focuses the
   input. 1 px ink rule below.
5. **Lede + at-a-glance**: grid `1fr 340px`, gap 64. Left: headline (the
   generated sentence, e.g. "The tops are in cloud. Everything below about
   890 m is clear."), supporting paragraph, then the unverified notice in
   14 px italic faint. Right: "AT A GLANCE" 13 px .22em, then label/value rows
   (16 px label muted-ink / 20 px value right) separated by --rule hairlines:
   Cloud base, Freezing level, Sunrise, Tops clear (value in --clear green).
6. **Legend**: dot + "CLEAR — 70% AND UP / ON THE EDGE — 40–69% / IN CLOUD —
   UNDER 40%" 12 px caps .13em, plus right-aligned italic hint "tap any hill
   for routes, sun times and the hour-by-hour".
7. **Height bands** (OVER 900M, 800 TO 900M, 700 TO 800M, UNDER 700M…):
   header = band label left + italic ochre note right ("None clear · best
   chance 33% on Nethermost Pike"), 2 px ink rule under. Hills in a
   **3-column grid** (column gap 56), each cell:
   `grid: 64px glyph | name+meta | %`, 13 px vertical padding, --hair
   hairline below, hover --row-hover + cursor pointer (whole row expands the
   hill). After the 9 shown rows: the **dense tier** — a centered run
   "Grasmoor 78% · Stybarrow Dodd 80% · … *and 13 more, 85–91%*" 13.5 px,
   percentages in verdict colours (this replaces the old "36 more in this
   band" flat line).
8. **Footer**: 2 px ink rule; 4 columns (GET IN TOUCH / BEFORE YOU GO /
   HOW IT IS MADE / SOURCES), 13 px caps headers, 15 px muted text, ochre
   underlined links. Copy is in the design reference — keep it verbatim
   (MWIS/SAIS warning, Open-Meteo/DoBIH/Wikipedia/Walkhighlands credits).

### 2b — Inversion morning
Same shell. Differences: Highlands active; ochre kicker "CLOUD INVERSION
LIKELY" above the headline; at-a-glance leads with **Inversion score 84 of
100** (ochre, 600); then the **hero panel** framed by 3 px ochre rules top and
bottom containing the animated SVG (see `snippets/inversion-hero.svg.html`)
and a 4-cell stat row (TOPS ABOVE CLOUD 241 of 282 · CLOUD TOP ~750 m ·
SUNRISE LIGHT 9 of 10 · WINDOW until ~09:00, values 28 px). Hill percentages
and phrases use --above ochre ("595 m above the deck"). Footer line: "EVEN
TODAY — A CHANCE, NOT A PROMISE".

### 2c — Hill expanded (guidebook entry)
Opens in place under the tapped row. Grid `380px 1fr`, gap 72.
Left: hill name 36, Gaelic name 17 italic muted; definition rows (Lists,
Height (+drop), Area, County, Grid ref, OS Landranger, Summit) label/value
with --hair rules; links row (Map · Routes on Walkhighlands · Hill-bagging)
ochre underlined; sun rows (Sunrise+bearing, Sunset+bearing, Golden hour,
Daylight). Right, in order: **verdict sentence** ("9% — in cloud all day."
in verdict colour + italic elaboration), **annotated section drawing**
(700×170: ridge, cloud rect, dashed base line, labelled summit dot, headroom
annotation), description prose 17/1.65 with "From Wikipedia, CC BY-SA 4.0"
credit, then the hourly table: HOUR / VIEW / CLOUD / TEMP / WIND, 12.5 px
caps headers, 16 px rows, VIEW % in verdict colour. Detail data is fetched
on tap (per constraint).

### 2d — Three days together
Compact masthead (36 px, tagline "THE WEEK AHEAD"). Headline names the answer
("Tuesday is the day."). Three equal columns separated by --rule hairlines;
winner column gets a 3 px ochre top rule + "THE DAY" tag (others 3 px ink).
Per column: dated label, giant % of Highland tops clear (62 px, verdict
colour), stacked distribution bar (clear/edge/cloud widths, 9 px, hairline
border), italic bar note, mini framed scene (220×84, same glyph language,
cloud band at that day's base), italic lede, then Highlands / Lake District /
Cloud base rows. Closing italic caveat: "Monday could go either way…".

### 2e — Phone (390)
Order: tiny top bar → centered masthead 27 px + tagline 8.5 px → region
selector + dated day tabs in ONE row → boxed search → headline 24 px →
one-line unverified notice → two at-a-glance rows → bands as single-column
rows (56 px glyph, min-height 44 px) → dense tier → "show all 34 in this
band ↓" ochre expander → footer line. First hill lands ~½ screen down.

### 2f — How to read this
Headline "Cloud has a bottom." + two intro paragraphs (max 74ch). Three-case
diagram: three framed scenes (below / inside / above the cloud) with coloured
caption labels and 15.5 px explanations. Then two columns: "A CHANCE, NOT A
PROMISE" (with the bordered unverified notice box) and "WHY OTHER FORECASTS
GET SUMMITS WRONG". Then GLOSSARY: 2-column list, term in 12.5 px caps 600 +
muted definition, --hair rules.

### 3a/3e — Dark theme
Same layouts, tokens from `[data-theme="dark"]`. Theme toggle label becomes
"☾ THEME". Persist choice in localStorage.

### 3b/3c/3d — Share cards (1200×630)
Generated OG images (screenshot or SVG-render at build time). Structure:
HILL WEATHER + region/date bar, double rule, (inversion: ochre kicker),
headline italic 58–66, key stats, the section drawing (STATIC — no
animation in share cards), rule, "HILLWEATHER.CO.UK" in ochre + "free · no
accounts · a chance, not a promise".

## The elevation glyph (production code included)
`snippets/hill-glyph.js` — generates each hill's unique framed 64×48 glyph:
deterministic ridge silhouette seeded from the hill's name, apex at true
relative height (LD scale 1200 m, Highlands 1600 m), cloud rect drawn over
the ridge at 0.7 opacity, dashed cloud-base line. Generate at build time and
inline; do not ship a per-hill runtime cost.

## The inversion hero animation (production code included)
`snippets/inversion-hero.svg.html` — complete, lift-ready. Pure SVG SMIL,
zero JavaScript, ~2 kB: sun rises out of the deck along a curved arc (16 s
loop, spline-eased, opacity fade at both ends, pulsing radial-gradient glow),
two cloud layers drift opposite directions (18 s / 26 s, paths oversized 80 px
per side so no edge shows). **Reduced motion**: include the CSS in the snippet
header; `data-anim` elements hide, `data-static` fallbacks (static deck +
fixed sun) show. Desktop only is fine; it's decorative — keep it out of the
share-card renders.

## Interactions & behaviour
- **Hill row** → tap/click expands the guidebook entry in place (fetch detail
  JSON on demand); whole row is the target; hover --row-hover, cursor pointer.
- **Day tabs / region tabs** → re-render from the prebuilt JSON; active =
  ochre underline. Keep the current day/region in the URL hash.
- **Search** → filters all 496 hills across both regions, matching English
  and Gaelic names; `/` focuses it.
- **Dense tier names** → tapping a name in the run expands that hill too.
- **Theme** → toggles `data-theme`, persisted.
- **"Show all N in this band ↓"** (phone) → reveals the remaining rows.
- No other animation anywhere — the hero is the single animated moment.

## State
Tiny: { region, dayIndex, expandedHillId, theme, searchQuery }. All render
from the prebuilt summary JSON; hill detail cached after first fetch.

## Assets
- Newsreader (Google Fonts) — the only external asset permitted.
- No images. All drawings are inline SVG generated from forecast data.

## Files in this package
- `README.md` — this document
- `tokens.css` — light + dark palettes, type scale notes
- `snippets/inversion-hero.svg.html` — production-ready animated hero
- `snippets/hill-glyph.js` — production-ready glyph generator
- `design-reference/Hill Weather UI.dc.html` — the full artboard canvas
  (open in a browser; reference only)
