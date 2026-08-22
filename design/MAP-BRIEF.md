# Brief: an interactive relief map for Hill Weather

Paste this into Claude Design. It is written to stand alone.

---

## The product

**hillweather.co.uk** is a free forecast for British hills that answers one
question no mainstream weather app answers: **will the summit be in cloud,
above it, or clear?**

Cloud has a bottom. On a typical day it might sit at 700 metres: below that
line you can see for miles, above it you are inside a grey nothing. That line
is the *cloud base*, and which side of it a summit falls on decides whether the
day was worth the drive. The site computes it for all 282 Munros and all 214
Wainwrights, twice a day.

Two audiences, chasing the same rare thing:

- **Hillwalkers** (Munro and Wainwright baggers) deciding where to go this
  weekend.
- **Landscape photographers** chasing **cloud inversions**: cold air trapped in
  the valleys, cloud filling the glens, the tops standing clear above a sea of
  white. Rare, maybe twenty mornings a year, and they will drive through the
  night for one.

## What to design

An **interactive relief map** as a second view alongside the existing ranked
list. Pan and zoom, from the whole of Britain down to a single hill.

### The job it does, precisely

This map is **not** for checking a hill you have already chosen; the list does
that better and always will. It exists for one moment: *"I was going to the
Lakes, but the map shows the Cairngorms are clear and the Lakes are not, so I
am changing my plan."*

That means the map must make the **pattern** legible, not the individual
readings. Design consequences:

- **Do not plot 496 markers.** A field of pins is a list with extra steps, and
  at national zoom it is unreadable.
- **Draw the cloud itself.** The cloud base is a smooth, continuous field.
  Render it as a layer over the terrain so you can see at a glance where the
  deck is low and where it lifts.
- **Let hills emerge with zoom.** Nothing at national scale; major summits at
  regional scale; every hill with its numbers when you are close.
- The single most valuable thing the map can show is an **inversion**: terrain
  poking through a cloud layer. That is the shot photographers want and the day
  walkers remember. It should be unmistakable and, ideally, beautiful.

### Aesthetic direction (settled, do not restart it)

The site is designed as a **newspaper**: warm cream paper (#FBF7F0), near-black
ink (#2A2521), Newsreader serif throughout, hairline rules, section heads in
letter-spaced small caps, an ochre accent (#A8763F). Restrained, printed,
quiet. It should feel like it was made by someone who actually walks these
hills, not by a weather company.

Accents in use: clear #3F6B4A, borderline #8A6A2E, in cloud #9C4B36.

The map must belong to that world. **Do not** make it look like a
general-purpose web map. The strongest idea available: render the relief in the
language of **antique engraved cartography** — hachures, contour lines,
stipple, cross-hatching — so it reads as an old map with today's weather laid
over it. That is a look nothing else on the web has, and the terrain data to
build it honestly is freely available.

Avoid: satellite imagery, glossy gradients, neon heatmaps, drop shadows,
generic map-pin iconography, dark mode.

### Technical constraints that shape the design

- **No external map tiles.** Everything is self-hosted static files: no
  Mapbox, no Google, no OpenStreetMap tiles. The relief is pre-rendered at
  build time and shipped as static assets, so it works with one bar of signal
  in a car park.
- **The terrain data is confirmed available.** OS Terrain 50 is free for
  everyone, 50 m post spacing, and ships **10 m interval contours as vectors**
  (Shapefile, GeoPackage, GML) alongside the elevation grid. The contour lines
  do not have to be computed: they are supplied. That makes engraved
  cartography a matter of styling existing linework rather than deriving it,
  and 50 m spacing is far finer than a national view needs, so it downsamples
  freely. Attribution to Ordnance Survey is required; confirm the exact wording
  against the OS OpenData licence before publishing.
- **The cloud field needs its own data.** The 496 hill points are unevenly
  distributed and leave large gaps, so a smooth field cannot honestly be
  interpolated from them alone. A coarse regular grid (roughly 25 km spacing
  over the Highlands, 10 km over the Lakes, around 150 to 200 points) gives a
  proper field and is cheap: far fewer variables per point than the hill
  forecast needs.
- **Rendering is open.** SVG, canvas, WebGL, pre-rendered raster, or any
  combination. Going elaborate is welcome if it earns its place.
- **Phones matter**, but design desktop first. One-handed use, and the result
  must be screenshot-shareable into a WhatsApp walking group.
- **Must degrade honestly.** The forecast is unvalidated against real
  observations so far, and the site says so plainly rather than hiding it.
  Nothing in the map should imply more certainty than exists.

### Data available per hill

Name, height in metres, prominence, geographic area, latitude and longitude,
chance of a view as a percentage, cloud base and cloud top in metres, a verdict
(CLEAR / ON THE EDGE / IN CLOUD / ABOVE CLOUD), an inversion score 0-100, a
sunrise light score, summit temperature and wind speed and direction, freezing
level, sunrise and sunset times with sun azimuth. Three days ahead, hourly.

Regions: Scottish Highlands (282 Munros, 915 to 1345 m) and the Lake District
(214 Wainwrights, 290 to 978 m).

## What to produce

Artboards for:

1. **National view.** The whole of Britain, or one region. The cloud field
   readable at a glance, no individual hills. The answer to "where is it clear
   today?"
2. **Regional view.** Mid zoom. Major summits named, conditions visible,
   still showing the pattern.
3. **Close view.** A single hill with its full readings, and how that relates
   back to the list view.
4. **An inversion day.** The same map when the interesting thing is happening:
   summits standing above a cloud sea. This is the emotional peak of the whole
   product and deserves its own artboard.
5. **The transition.** How zoom moves between these states, and how the map and
   the list relate to each other.

## Open questions worth designing an opinion about

- Is the cloud drawn from above (plan view, as cloud cover) or is the
  relationship between summit and cloud base shown some other way? Plan view is
  conventional; the interesting information is vertical.
- Time: three days of hourly data exists. A scrubber, an animation, or nothing?
- Should the map ever be the landing page, or always a second view?
