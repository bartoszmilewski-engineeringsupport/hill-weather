/* Theme switch.
 *
 * Three states, not two: follow the machine, force light, force dark. Most
 * people never touch it and get whatever their phone is set to, which is the
 * point; the switch exists for the ones who want to override it.
 *
 * The initial read happens inline in <head> so the page never paints light
 * and then flips, which is worse than either theme.
 */
(function () {
  const KEY = 'hw.theme';
  const root = document.documentElement;

  function current() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }

  function systemIsDark() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  }

  function apply(mode) {
    if (mode === 'dark' || mode === 'light') root.setAttribute('data-theme', mode);
    else root.removeAttribute('data-theme');
    const dark = mode === 'dark' || (!mode && systemIsDark());
    const meta = document.querySelector('meta[name="theme-color"]:not([media])');
    if (meta) meta.content = dark ? '#16140F' : '#FBF7F0';
    const btn = document.getElementById('theme');
    if (btn) {
      btn.setAttribute('aria-pressed', String(dark));
      btn.title = mode
        ? `Theme: ${mode}. Tap to follow your device again.`
        : 'Theme: following your device. Tap to switch.';
    }
  }

  // Cycle light -> dark -> follow the device, so there is always a way back
  // to the default rather than being stuck on a manual choice.
  function next() {
    const mode = current();
    const now = mode === 'light' ? 'dark' : mode === 'dark' ? null : (systemIsDark() ? 'light' : 'dark');
    try {
      if (now) localStorage.setItem(KEY, now); else localStorage.removeItem(KEY);
    } catch (e) { /* private mode */ }
    apply(now);
  }

  document.addEventListener('DOMContentLoaded', () => {
    apply(current());
    const btn = document.getElementById('theme');
    if (btn) btn.addEventListener('click', next);
  });

  // Follow the device live, but only while the reader has not overridden it.
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)')
      .addEventListener('change', () => { if (!current()) apply(null); });
  }
})();
