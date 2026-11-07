(() => {
  const allowedPaths = new Set([
    '/',
    '/contacts.html',
    '/features.html',
    '/privacy.html',
    '/project-catalog.html',
    '/terms.html',
  ]);
  const path = window.location.pathname;
  if (!allowedPaths.has(path)) return;

  const params = new URLSearchParams(window.location.search);
  const value = (key) => {
    const raw = (params.get(key) || '').trim().toLowerCase();
    return /^[a-z0-9._-]{1,120}$/.test(raw) ? raw : '';
  };

  fetch('/site/analytics/pageview', {
    method: 'POST',
    mode: 'same-origin',
    credentials: 'omit',
    keepalive: true,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      path,
      utmSource: value('utm_source'),
      utmMedium: value('utm_medium'),
      utmCampaign: value('utm_campaign'),
    }),
  }).catch(() => {});
})();
