// Existing Needle Shark VK Ads / Top Mail.Ru counter; page views only.
(() => {
  if (location.protocol !== 'https:' || location.hostname !== 'needle-shark.ru' || window.__needleVkPixelStarted || document.body?.dataset.preview === 'true') return;
  window.__needleVkPixelStarted = true;
  const cleanUrl = value => {
    try { const url = new URL(value); return url.origin + url.pathname; }
    catch (_) { return ''; }
  };
  const queue = window._tmr || (window._tmr = []);
  queue.push({id: '3766157', type: 'pageView', start: Date.now(),
    url: cleanUrl(location.href), referrer: cleanUrl(document.referrer)});
  if (document.getElementById('tmr-code')) return;
  const script = document.createElement('script');
  script.id = 'tmr-code';
  script.async = true;
  script.src = 'https://top-fwz1.mail.ru/js/code.js';
  document.head.appendChild(script);
})();
