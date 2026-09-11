(() => {
  const counter = 112428810;
  const goal = (name, params = {}) => {
    if (typeof window.ym === 'function') window.ym(counter, 'reachGoal', name, params);
  };
  document.addEventListener('click', event => {
    const el = event.target.closest('a,button,input[type=checkbox],input[type=file]');
    if (el?.dataset.blogCta) goal('blog_cta_click', {article: el.dataset.article, cta: el.dataset.blogCta, page: location.pathname});
    if (!el || !el.dataset.track) return;
    goal('ui_click', {element: el.dataset.track, page: location.pathname});
  });
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
