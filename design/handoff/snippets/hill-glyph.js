// Hill Weather — per-hill elevation glyph (framed, 64x48)
// Each hill gets a UNIQUE ridge silhouette, deterministically seeded from its
// name, with the apex at the hill's true height relative to the region scale.
// The cloud rectangle is drawn OVER the ridge at ~0.7 opacity so an in-cloud
// summit shows faintly through the grey — the whole idea of the site in 64px.
//
// Region scales used in the design: Lake District 1200 m, Highlands 1600 m.
// Ground line y = 44, frame 64x48.

/** Deterministic ridge polygon points for one hill.
 *  name: hill name (the seed)  ay: apex y  g: ground y  x0..x1: horizontal span */
function ridge(name, ay, g, x0, x1) {
  let s = 7;
  for (const c of name) s = (s * 31 + c.charCodeAt(0)) & 0x7fffffff;
  const rnd = () => ((s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
  const w = x1 - x0, ax = x0 + w * (0.36 + rnd() * 0.28), d = g - ay;
  const p = [[x0, g],
    [x0 + w * (0.11 + rnd() * 0.09), g - d * (0.16 + rnd() * 0.16)],
    [x0 + w * (0.24 + rnd() * 0.1),  g - d * (0.4  + rnd() * 0.24)],
    [ax, ay],
    [ax + (x1 - ax) * (0.28 + rnd() * 0.18), g - d * (0.48 + rnd() * 0.26)],
    [x1 - w * (0.13 + rnd() * 0.09), g - d * (0.14 + rnd() * 0.16)],
    [x1, g]];
  return p.map(q => q[0].toFixed(1) + ',' + q[1].toFixed(1)).join(' ');
}

/** Full glyph SVG for one hill.
 *  h: height m   cloudBase: m   scale: region max m   inversion: cloud fills the valley instead */
function hillGlyph(name, h, cloudBase, scale, inversion = false) {
  const k = 38 / scale;
  const ay = +(44 - h * k).toFixed(1);          // apex y
  const by = +(44 - cloudBase * k).toFixed(1);  // cloud base y
  const cy = inversion ? by : 2;                 // cloud rect y
  const ch = inversion ? +(43 - by).toFixed(1) : +(by - 2).toFixed(1);
  return `<svg viewBox="0 0 64 48" width="64" height="48" role="img" aria-label="${name}, ${h} m">
  <rect x="0.5" y="0.5" width="63" height="47" fill="var(--glyph-bg)" stroke="var(--glyph-frame)"/>
  <polygon points="${ridge(name, ay, 44, 5, 59)}" fill="var(--glyph-hill)" stroke="var(--glyph-hill-line)" stroke-width="1"/>
  <rect x="1" y="${cy}" width="62" height="${ch}" fill="var(--glyph-cloud)" opacity="0.7"/>
  <line x1="2" y1="${by}" x2="62" y2="${by}" stroke="#8C8175" stroke-width="0.9" stroke-dasharray="3 3"/>
</svg>`;
}
// Glyphs can be generated once at build time (they only change when the cloud
// base changes, i.e. twice a day) and inlined into the prebuilt page/JSON.
