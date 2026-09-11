(() => {
  const counter = 112428810;
  const goal = (name, params = {}) => {
    if (typeof window.ym === 'function') window.ym(counter, 'reachGoal', name, params);
  };
  const localHosts = new Set(['needleshark.ru', 'www.needleshark.ru', location.hostname]);
  function trackClick(event) {
    if (event.type === 'auxclick' && event.button !== 1) return;
    const el = event.target.closest('a,button,input[type=checkbox],input[type=file]');
    if (!el || el.disabled) return;
    const params = {page: location.pathname};
    if (el.dataset.blogCta) {
      goal('blog_cta_click', {...params, article: el.dataset.article, cta: el.dataset.blogCta});
      return;
    }
    const href = el.getAttribute('href') || '';
    if (/^(mailto:|tel:)/i.test(href)) {
      goal('contact_click', {...params, method: href.startsWith('mailto:') ? 'email' : 'phone'});
      return;
    }
    if (el.tagName === 'A' && href) {
      const url = new URL(href, location.href);
      if (['http:', 'https:'].includes(url.protocol) && !localHosts.has(url.hostname)) {
        goal('outbound_click', {...params, host: url.hostname, element: el.dataset.track || 'external_link'});
        return;
      }
    }
    if (el.hasAttribute('data-request')) {
      goal('request_open', {...params, product: document.body.dataset.productSlug || 'catalog'});
      return;
    }
    if (el.dataset.track || el.tagName === 'A') goal('ui_click', {...params, element: el.dataset.track || 'internal_link'});
  }
  document.addEventListener('click', trackClick);
  document.addEventListener('auxclick', trackClick);
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('focusin', () => goal('form_start'), {once: true});
    form.addEventListener('submit', () => goal('form_submit_attempt'));
  });
  document.addEventListener('lead-saved', () => goal('lead_submitted'));
  let dismissed = false;
  try { dismissed = localStorage.getItem('needle_cookie_notice') === '1'; } catch (_) {}
  if (dismissed) return;
  const notice = document.createElement('aside');
  notice.className = 'cookie-notice';
  notice.setAttribute('aria-label', 'Использование cookie');
  notice.innerHTML = '<p>Мы используем cookie и Яндекс Метрику для анализа посещений и улучшения сайта. <a href="/privacy-policy" data-track="cookie_policy">Подробнее в политике</a>.</p><button type="button" data-track="cookie_close">Понятно</button>';
  document.body.append(notice);
  notice.querySelector('button').addEventListener('click', () => {
    try { localStorage.setItem('needle_cookie_notice', '1'); } catch (_) {}
    notice.remove();
  });
})();
