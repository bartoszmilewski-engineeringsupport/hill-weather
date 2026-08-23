/* Share card.
 *
 * The growth model is somebody pasting a picture into a walking group on a
 * Friday night, so the card is the marketing. It is drawn rather than
 * screenshotted so it always carries the date, the region and where it came
 * from, and it is laid out as a front page: the headline does the work, the
 * numbers back it up.
 */
(function () {
  const W = 1080, H = 1350;
  const C = {
    paper: '#FBF7F0', ink: '#2A2521', muted: '#6B6156', faint: '#8C8175',
    rule: '#DCD2C0', hair: '#EDE5D7', ochre: '#A8763F',
    clear: '#3F6B4A', edge: '#8A6A2E', cloud: '#9C4B36',
    font: "'Newsreader', Georgia, serif",
  };
  const colour = v => v >= 70 ? C.clear : v >= 35 ? C.edge : C.cloud;
  const PAD = 76;

  function wrap(x, text, maxWidth) {
    const words = text.split(' ');
    const lines = [];
    let line = '';
    for (const w of words) {
      const next = line ? line + ' ' + w : w;
      if (x.measureText(next).width > maxWidth && line) {
        lines.push(line);
        line = w;
      } else {
        line = next;
      }
    }
    if (line) lines.push(line);
    return lines;
  }

  function draw() {
    const d = state.data[state.region];
    const day = state.day;
    const c = document.createElement('canvas');
    c.width = W; c.height = H;
    const x = c.getContext('2d');

    x.fillStyle = C.paper;
    x.fillRect(0, 0, W, H);
    x.textBaseline = 'alphabetic';

    let y = 84;

    // Dateline
    x.fillStyle = C.muted;
    x.font = `400 22px ${C.font}`;
    const dateline = new Date(day + 'T12:00').toLocaleDateString('en-GB',
      { weekday: 'long', day: 'numeric', month: 'long' }).toUpperCase();
    x.fillText(dateline, PAD, y);
    x.textAlign = 'right';
    x.fillText(d.meta.label.toUpperCase(), W - PAD, y);
    x.textAlign = 'left';

    // Masthead
    y += 22;
    x.fillStyle = C.ink;
    x.fillRect(PAD, y, W - PAD * 2, 4);
    y += 84;
    x.font = `500 78px ${C.font}`;
    x.textAlign = 'center';
    x.fillText('Hill Weather', W / 2, y);
    y += 34;
    x.fillStyle = C.ochre;
    x.font = `400 20px ${C.font}`;
    x.fillText('CLOUD BASE & INVERSIONS FOR BRITISH HILLS', W / 2, y);
    x.textAlign = 'left';
    y += 24;
    x.fillStyle = C.ink;
    x.fillRect(PAD, y, W - PAD * 2, 1.5);

    // Headline, straight off the page so the card and the site never disagree.
    y += 70;
    const headline = document.getElementById('headline').textContent;
    x.font = `400 46px ${C.font}`;
    for (const line of wrap(x, headline, W - PAD * 2)) {
      x.fillText(line, PAD, y);
      y += 56;
    }

    // Bands
    y += 18;
    const rows = d.hills.map(h => ({ h, s: h.daily[day] })).filter(r => r.s)
      .sort((a, b) => b.s.view_pct - a.s.view_pct || b.h.height - a.h.height);
    const bands = (d.meta.bands && d.meta.bands.length) ? d.meta.bands : [[0, 'All hills']];
    const populated = bands.filter(([f]) => rows.some(r =>
      r.h.height >= f && !bands.some(([g]) => g > f && r.h.height >= g)));

    // Budget the rows before drawing so every populated band always appears.
    // Dropping one would be the worst failure here: on a poor day the low band
    // is the only one with anything clear in it, which is the whole message.
    const FOOT = H - 190, CHROME = 84, ROW = 52;
    const per = (FOOT - y) / Math.max(1, populated.length);
    const perBand = Math.max(1, Math.min(3, Math.floor((per - CHROME) / ROW)));

    for (const [floor, label] of bands) {
      const inBand = rows.filter(r => r.h.height >= floor &&
        !bands.some(([f]) => f > floor && r.h.height >= f));
      if (!inBand.length) continue;

      const clear = inBand.filter(r => r.s.view_pct >= 70).length;
      x.fillStyle = C.ink;
      x.font = `400 24px ${C.font}`;
      x.fillText(label.toUpperCase(), PAD, y);
      x.textAlign = 'right';
      x.fillStyle = clear ? C.clear : C.cloud;
      x.font = `400 22px ${C.font}`;
      x.fillText(clear ? `${clear} of ${inBand.length} clear` : 'none clear', W - PAD, y);
      x.textAlign = 'left';

      y += 14;
      x.fillStyle = C.ink;
      x.fillRect(PAD, y, W - PAD * 2, 2);
      y += 48;

      for (const { h, s } of inBand.slice(0, perBand)) {
        const pct = `${s.view_pct}%`;
        x.font = `400 36px ${C.font}`;
        const pctW = x.measureText(pct).width;
        x.fillStyle = colour(s.view_pct);
        x.textAlign = 'right';
        x.fillText(pct, W - PAD, y);
        x.textAlign = 'left';

        const ht = `${h.height} m`;
        x.font = `400 24px ${C.font}`;
        const htW = x.measureText(ht).width;

        // Truncate to the room actually left, not a guessed character count:
        // "Beinn a' Ghlo - Braigh Coire Chruinn-bhalgain" is a real hill.
        const room = W - PAD * 2 - pctW - htW - 64;
        x.font = `400 34px ${C.font}`;
        let name = h.name;
        while (x.measureText(name).width > room && name.length > 4) name = name.slice(0, -2);
        if (name !== h.name) name = name.trimEnd() + '…';
        x.fillStyle = C.ink;
        x.fillText(name, PAD, y);
        const nameW = x.measureText(name).width;

        x.fillStyle = C.faint;
        x.font = `400 24px ${C.font}`;
        x.fillText(ht, PAD + nameW + 18, y);

        y += ROW - 14;
        x.fillStyle = C.hair;
        x.fillRect(PAD, y, W - PAD * 2, 1);
        y += 14;
      }
      y += 26;
    }

    // Footer
    x.fillStyle = C.ink;
    x.fillRect(PAD, H - 150, W - PAD * 2, 3);
    x.font = `500 34px ${C.font}`;
    x.fillText('hillweather.co.uk', PAD, H - 96);
    x.fillStyle = C.muted;
    x.font = `400 22px ${C.font}`;
    x.fillText('A planning aid, not a forecast service. Always read MWIS.', PAD, H - 58);

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
