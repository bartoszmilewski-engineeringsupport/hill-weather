/* Per-hill elevation glyph, framed 64x48.
 *
 * From the design handoff (design/handoff/snippets/hill-glyph.js), unchanged
 * in geometry. Each hill gets a UNIQUE ridge silhouette, deterministically
 * seeded from its name, with the apex at its true height relative to the
 * region scale. The cloud rectangle is drawn OVER the ridge at 0.7 so an
 * in-cloud summit shows faintly through the grey: the whole idea of the site
 * in 64 pixels.
 *
 * The handoff suggests generating these at build time. They are generated in
 * the page instead, because only about thirty are on screen at once while a
 * region holds up to 282 hills across three days: baking them in would inflate
 * the summary JSON many times over to save a fraction of a millisecond. The
 * shapes are memoised per hill so scrolling and re-rendering cost nothing.
 */
(function () {
  const GROUND = 44;
  const cache = new Map();

  /* Deterministic ridge polygon for one hill. The name is the seed, so a hill
     keeps the same silhouette from one visit to the next. */
  function ridge(name, ay, g, x0, x1) {
    let s = 7;
    for (const c of name) s = (s * 31 + c.charCodeAt(0)) & 0x7fffffff;
    const rnd = () => ((s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
    const w = x1 - x0, ax = x0 + w * (0.36 + rnd() * 0.28), d = g - ay;
    const p = [[x0, g],
      [x0 + w * (0.11 + rnd() * 0.09), g - d * (0.16 + rnd() * 0.16)],
      [x0 + w * (0.24 + rnd() * 0.10), g - d * (0.40 + rnd() * 0.24)],
      [ax, ay],
      [ax + (x1 - ax) * (0.28 + rnd() * 0.18), g - d * (0.48 + rnd() * 0.26)],
      [x1 - w * (0.13 + rnd() * 0.09), g - d * (0.14 + rnd() * 0.16)],
      [x1, g]];
    return p.map(q => q[0].toFixed(1) + "," + q[1].toFixed(1)).join(" ");
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, c =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  /* Exposed so the expanded entry can draw the same hill large, with the same
     silhouette. A hill that looked one way in the list must not look like a
     different mountain when opened. */
  window.hillRidge = ridge;

  /* h: height m. cloudBase / cloudTop: m or null. scale: region max m.
     inversion: the cloud fills the valley below the summit instead. */
  window.hillGlyph = function (name, h, cloudBase, scale, inversion) {
    const k = 38 / scale;
    const ay = +(GROUND - h * k).toFixed(1);
    const shape = cache.get(name) ||
      cache.set(name, ridge(name, ay, GROUND, 5, 59)).get(name);

    let cloud = "";
    if (cloudBase != null) {
      const by = +(GROUND - cloudBase * k).toFixed(1);
      const cy = inversion ? by : 2;
      const ch = inversion ? +(43 - by).toFixed(1) : +(by - 2).toFixed(1);
      if (ch > 0) {
        cloud =
          `<rect x="1" y="${cy}" width="62" height="${ch}" fill="var(--glyph-cloud)"` +
          ` opacity="var(--glyph-cloud-op)"></rect>` +
          `<line x1="2" y1="${by}" x2="62" y2="${by}" stroke="#8C8175"` +
          ` stroke-width="0.9" stroke-dasharray="3 3"></line>`;
      }
    }

    return `<svg viewBox="0 0 64 48" width="64" height="48" role="img" ` +
      `aria-label="${esc(name)}, ${h} m">` +
      `<rect x="0.5" y="0.5" width="63" height="47" fill="var(--glyph-bg)" ` +
      `stroke="var(--glyph-frame)"></rect>` +
      `<polygon points="${shape}" fill="var(--glyph-hill)" ` +
      `stroke="var(--glyph-hill-line)" stroke-width="1"></polygon>` +
      cloud + `</svg>`;
  };
})();
