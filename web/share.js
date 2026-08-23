/* Share card. Boards 3b, 3c and 3d of the design handoff.
 *
 * The growth model is somebody pasting a picture into a walking group on a
 * Friday night, so the card is the marketing. It is drawn rather than
 * screenshotted so it always carries the date, the region and where it came
 * from, and it is laid out as a front page: the headline does the work, the
 * numbers back it up.
 *
 * 1200 x 630 is the aspect every platform expects, and it is the same card the
 * link preview uses, so a pasted link and a pasted picture agree.
 *
 * The headline is READ FROM THE PAGE rather than recomputed here. There are
 * four ways the front page can describe a day and they have already been argued
 * over once; deriving them a second time in a different file is how a card ends
 * up claiming something the page it came from does not.
 */
(function () {
  const W = 1200, H = 630;
  const PAD_X = 56, PAD_TOP = 40, PAD_BOT = 34;

  const LIGHT = {
    paper: '#FBF7F0', ink: '#2A2521', muted: '#6B6156', faint: '#8C8175',
    rule: '#DCD2C0', ochre: '#A8763F', ridge: '#F3ECDF', deck: '#E7DDC8',
  };
  // Board 3d. Not a different design, the same one inverted.
  const DARK = {
    paper: '#16140F', ink: '#EFE8DB', muted: '#A89A88', faint: '#8C8175',
    rule: '#3A332A', ochre: '#CC9A5B', ridge: '#262019', deck: '#3A322A',
  };
  const FONT = "'Newsreader', Georgia, serif";

  function palette() {
    const set = document.documentElement.getAttribute('data-theme');
    if (set === 'dark') return DARK;
    if (set === 'light') return LIGHT;
    return matchMedia('(prefers-color-scheme: dark)').matches ? DARK : LIGHT;
  }

  /* Canvas has letterSpacing only in recent browsers, and the tracked small
     caps are half the look, so they are drawn a character at a time. */
  function tracked(x, text, px, y, spacing, right) {
    const widths = [...text].map(c => x.measureText(c).width);
    const total = widths.reduce((a, b) => a + b, 0) + spacing * (text.length - 1);
    let cx = right ? px - total : px;
    [...text].forEach((c, i) => { x.fillText(c, cx, y); cx += widths[i] + spacing; });
    return total;
  }

  function wrap(x, text, maxWidth) {
    const lines = [];
    let line = '';
    for (const w of text.split(' ')) {
      const next = line ? line + ' ' + w : w;
      if (x.measureText(next).width > maxWidth && line) { lines.push(line); line = w; }
      else line = next;
    }
    if (line) lines.push(line);
    return lines;
  }

  // The ridge from the handoff hero, in its own 1112 x 216 space.
  const RIDGE = [[0,206],[55,192],[130,120],[195,152],[258,86],[320,142],[400,58],
                 [468,132],[540,96],[610,150],[676,66],[748,138],[820,104],[888,158],
                 [958,88],[1030,148],[1112,196],[1112,208],[0,208]];
  const PEAKS = [[400,58],[676,66],[958,88]];
  const SUMMITS = [58, 66, 86, 88, 96, 104, 120];

  /* Where to draw the deck so the picture tells the truth.

     The ridge is a fixed engraving with its own distribution of heights, so
     putting the deck at the day's cloud base in metres draws whatever that
     distribution happens to give, which on a Lakeland day meant four of seven
     peaks standing proud under a headline saying the tops were in cloud. The
     deck is placed by proportion instead: if a seventh of the hills are out of
     the cloud, a seventh of the drawn peaks stand above the line. Same rule as
     scripts/og_image.py, so the card and the link preview agree. */
  function deckLine(fraction) {
    const n = Math.round(SUMMITS.length * Math.max(0, Math.min(1, fraction)));
    if (n <= 0) return SUMMITS[0] - 14;
    if (n >= SUMMITS.length) return SUMMITS[SUMMITS.length - 1] + 24;
    return (SUMMITS[n - 1] + SUMMITS[n]) / 2;
  }

  function scene(x, C, x0, y0, width, fraction, labels, sun) {
    const k = width / 1112;
    const px = p => [x0 + p[0] * k, y0 + p[1] * k];

    x.fillStyle = C.ridge;
    x.strokeStyle = C.ink;
    x.lineWidth = 1.2;
    x.beginPath();
    RIDGE.forEach((p, i) => { const [a, b] = px(p); i ? x.lineTo(a, b) : x.moveTo(a, b); });
    x.closePath();
    x.fill();
    x.stroke();

    // The deck goes OVER the ridge, so summits above it stay visible and
    // summits below it are swallowed: the whole idea of the site in one shape.
    const dy = y0 + deckLine(fraction) * k;
    const ground = y0 + 206 * k;
    x.globalAlpha = 0.94;
    x.fillStyle = C.deck;
    x.fillRect(x0, dy, width, Math.max(0, ground - dy));
    x.globalAlpha = 1;

    x.strokeStyle = C.faint;
    x.lineWidth = 0.9;
    x.setLineDash([4, 4]);
    x.beginPath(); x.moveTo(x0, dy); x.lineTo(x0 + width, dy); x.stroke();
    x.setLineDash([]);

    if (sun) {
      x.strokeStyle = C.ochre;
      x.lineWidth = 1.4;
      x.beginPath();
      x.arc(x0 + 72 * k, y0 + 34 * k, 13 * k, 0, Math.PI * 2);
      x.stroke();
    }

    x.fillStyle = C.ink;
    x.font = `400 ${Math.round(12.5)}px ${FONT}`;
    labels.slice(0, PEAKS.length).forEach((name, i) => {
      const [lx, ly] = px(PEAKS[i]);
      tracked(x, name.toUpperCase(), lx - 12, ly - 11, 1.5, false);
    });
  }

  /* Everything the card says, taken from the same state the page rendered. */
  function facts() {
    const d = state.data[state.region];
    const day = state.day;
    const rows = d.hills.map(h => ({ h, s: h.daily[day] })).filter(r => r.s);
    const above = rows.filter(r => aboveDeck(r.h, r.s));
    const strong = above.filter(r => r.s.verdict === 'ABOVE CLOUD');
    const clear = rows.filter(r => r.s.view_pct >= 70);
    const mid = a => a.length ? a.slice().sort((p, q) => p - q)[Math.floor(a.length / 2)] : null;
    const bases = rows.map(r => r.s.cloud_base).filter(v => v != null).sort((a, b) => a - b);

    return {
      label: d.meta.label, day, total: rows.length,
      inversion: strong.length > 0,
      above: above.length, clear: clear.length,
      score: Math.max(...rows.map(r => r.s.inversion || 0)),
      deck: mid((above.length ? above : rows).map(r => r.s.cloud_top).filter(v => v != null)),
      bases,
      sunrise: rows[0].h.sunrise ? rows[0].h.sunrise[day] : null,
      named: (above.length ? above : clear.length ? clear : rows)
        .slice().sort((a, b) => b.h.height - a.h.height).slice(0, 3).map(r => r.h.name),
    };
  }

  const metres = v => v == null ? null : v.toLocaleString('en-GB') + ' m';

  function standfirst(f) {
    if (f.inversion)
      return `${f.above} of ${f.total} tops stand clear above a white sea` +
        (f.deck != null ? `, cloud top about ${metres(f.deck)}` : '') +
        (f.sunrise ? `, sunrise ${f.sunrise.slice(11, 16)}.` : '.');
    if (!f.bases.length)
      return `Little low cloud anywhere. ${f.clear} of ${f.total} tops should be clear.`;
    return `${f.clear} of ${f.total} tops should stay out of the cloud. ` +
      `Base runs ${metres(f.bases[0])} to ${metres(f.bases[f.bases.length - 1])}.`;
  }

  function draw() {
    const C = palette();
    const f = facts();
    const c = document.createElement('canvas');
    c.width = W; c.height = H;
    const x = c.getContext('2d');

    x.fillStyle = C.paper;
    x.fillRect(0, 0, W, H);
    x.textBaseline = 'alphabetic';
    const right = W - PAD_X;

    // Masthead bar, then the double rule.
    let y = PAD_TOP + 16;
    x.fillStyle = C.ink;
    x.font = `600 19px ${FONT}`;
    tracked(x, 'HILL WEATHER', PAD_X, y, 4, false);
    x.fillStyle = C.muted;
    x.font = `400 18px ${FONT}`;
    const when = new Date(f.day + 'T12:00')
      .toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
    tracked(x, `${f.label.toUpperCase()}  ${when.toUpperCase()}`, right, y, 3.6, true);

    y += 18;
    x.fillStyle = C.ink;
    x.fillRect(PAD_X, y, right - PAD_X, 2);
    x.fillRect(PAD_X, y + 5, right - PAD_X, 1);
    y += 34;

    if (f.inversion) {
      x.fillStyle = C.ochre;
      x.font = `600 18px ${FONT}`;
      tracked(x, `CLOUD INVERSION  SCORE ${f.score} OF 100`, PAD_X, y + 14, 4.2, false);
      y += 36;
    }

    // The drawing is anchored to the footer, so the copy above it has a fixed
    // budget. The headline is set as large as fits inside that budget rather
    // than at one size that happens to work for the shortest of the five
    // things the page can say: two lines of headline over two of standfirst
    // would otherwise run straight through the ridge.
    const footRule = H - PAD_BOT - 44;
    const sceneW = right - PAD_X;
    const sceneH = sceneW * 216 / 1112;
    const sceneTop = footRule - 14 - sceneH;

    const headline = (document.getElementById('headline') || {}).textContent
      || 'Will the summit be in cloud, above it, or clear?';
    const sub = standfirst(f);

    let size = 62, lines, subLines;
    for (;;) {
      x.font = `500 italic ${size}px ${FONT}`;
      lines = wrap(x, headline, right - PAD_X);
      x.font = `400 21px ${FONT}`;
      subLines = wrap(x, sub, 900);
      const needed = lines.length * size + 34 + subLines.length * 30;
      if (y + needed <= sceneTop - 10 || size <= 38) break;
      size -= 4;
    }

    x.fillStyle = C.ink;
    x.font = `500 italic ${size}px ${FONT}`;
    for (const line of lines) {
      y += size;
      x.fillText(line, PAD_X, y);
    }

    y += 34;
    x.fillStyle = C.muted;
    x.font = `400 21px ${FONT}`;
    for (const line of subLines) {
      x.fillText(line, PAD_X, y);
      y += 30;
    }

    scene(x, C, PAD_X, sceneTop, sceneW,
          (f.inversion ? f.above : f.clear) / f.total, f.named, f.inversion);

    x.fillStyle = C.rule;
    x.fillRect(PAD_X, footRule, right - PAD_X, 1);
    x.fillStyle = C.ochre;
    x.font = `600 21px ${FONT}`;
    tracked(x, 'HILLWEATHER.CO.UK', PAD_X, footRule + 32, 3.4, false);
    x.fillStyle = C.faint;
    x.font = `400 italic 18px ${FONT}`;
    tracked(x, 'free · no accounts · a chance, not a promise',
            right, footRule + 32, 0, true);

    return c;
  }

  async function share(ev) {
    const btn = (ev && ev.currentTarget) || document.getElementById('share');
    const label = btn.textContent;
    btn.disabled = true;
    btn.textContent = '…';
    try {
      // Without this the card can render in a fallback face on first use.
      if (document.fonts && document.fonts.ready) await document.fonts.ready;
      const canvas = draw();
      const blob = await new Promise(r => canvas.toBlob(r, 'image/png'));
      const name = `hillweather-${state.region}-${state.day}.png`;
      const file = new File([blob], name, { type: 'image/png' });

      // Phones get the real share sheet, which is where this actually gets
      // used. Everything else falls back to a download.
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file] });
      } else {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = name;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 5000);
      }
    } catch (e) {
      if (e.name !== 'AbortError') console.error('share failed', e);
    } finally {
      btn.disabled = false;
      btn.textContent = label;
    }
  }

  document.querySelectorAll('.share-btn').forEach(b => b.addEventListener('click', share));
  window.drawShareCard = draw;
})();
