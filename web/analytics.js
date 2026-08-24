/* Google Analytics, behind consent.
 *
 * GA4 sets cookies and sends visitor data to a third party. Under UK PECR that
 * is not something a site may do until the visitor has agreed, and analytics
 * are explicitly not "strictly necessary": the site works identically without
 * them. So nothing here loads until somebody says yes, and saying no is a
 * single click that is remembered.
 *
 * That is also why the choice is stored in localStorage rather than a cookie.
 * Recording "this person declined" in a cookie would mean setting a cookie in
 * order to honour a refusal, which is the kind of thing this site should not do.
 *
 * The banner is deliberately plain and appears once. If you find yourself
 * wanting to make it harder to decline than to accept, that is the moment to
 * drop analytics instead.
 */
(function () {
  var ID = 'G-8J78948PTM';          // Measurement ID, from the GA data stream
  var KEY = 'hw.analytics';

  function stored() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function remember(v) {
    try { localStorage.setItem(KEY, v); } catch (e) {}
  }

  var configured = ID && ID.indexOf('X') === -1;

  function load() {
    if (!configured) return;
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + ID;
    document.head.appendChild(s);

    window.dataLayer = window.dataLayer || [];
    function gtag() { window.dataLayer.push(arguments); }
    window.gtag = gtag;
    gtag('js', new Date());
    /* Consent Mode. Analytics storage is the only thing ever granted: no ad
       storage, no personalisation, no user data sharing for advertising. This
       site does not advertise and is not going to. */
    gtag('consent', 'default', {
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied',
      analytics_storage: 'granted',
    });
    gtag('config', ID, { anonymize_ip: true });
  }

  function dismiss(banner, answer) {
    remember(answer);
    if (banner) banner.remove();
    if (answer === 'yes') load();
  }

  function ask() {
    var b = document.createElement('div');
    b.className = 'consent';
    b.setAttribute('role', 'dialog');
    b.setAttribute('aria-label', 'Analytics');
    b.innerHTML =
      '<p>Hill Weather would like to count visits with Google Analytics, to know ' +
      'whether any of this is useful to anyone. It sets cookies and sends data to ' +
      'Google. The forecast works exactly the same either way, and no is a ' +
      'perfectly good answer.</p>' +
      '<div class="consent-buttons">' +
      '<button type="button" data-answer="no">No thanks</button>' +
      '<button type="button" data-answer="yes" class="consent-yes">Allow</button>' +
      '</div>';
    document.body.appendChild(b);
    b.addEventListener('click', function (e) {
      var btn = e.target.closest('button[data-answer]');
      if (btn) dismiss(b, btn.getAttribute('data-answer'));
    });
  }

  // No measurement ID means no analytics, so there is nothing to ask about.
  // Without this the banner would appear on a site that tracks nobody, which
  // is worse than useless: it teaches people to click through consent.
  if (!configured) return;

  var choice = stored();
  if (choice === 'yes') load();
  else if (choice !== 'no') {
    if (document.readyState === 'loading')
      document.addEventListener('DOMContentLoaded', ask);
    else ask();
  }

  /* Let anyone change their mind later, from the footer. */
  window.hillAnalyticsReset = function () {
    try { localStorage.removeItem(KEY); } catch (e) {}
    location.reload();
  };
})();
