(() => {
  const counter = 112428810;
  const goal = (name, params = {}, callback) => {
    if (typeof window.ym === 'function') window.ym(counter, 'reachGoal', name, params, callback);
    else callback?.();
  };
  const navigationGoal = (event, el, name, params) => {
    const sameTab = el.tagName === 'A' && (!el.target || el.target === '_self') && !el.hasAttribute('download');
    if (!sameTab || event.type !== 'click' || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.defaultPrevented) {
      goal(name, params);
      return;
    }
    event.preventDefault();
    let followed = false;
    const follow = () => { if (!followed) { followed = true; clearTimeout(timer); location.assign(el.href); } };
    const timer = setTimeout(follow, 800);
    goal(name, params, follow);
  };
  const localHosts = new Set(['needleshark.ru', 'www.needleshark.ru', location.hostname]);
  const catalogParams = () => document.body.classList.contains('assortment') ? {
    page: location.pathname, context: 'catalog', product: document.body.dataset.productSlug || 'catalog'
  } : {};
  function trackClick(event) {
    if (event.type === 'auxclick' && event.button !== 1) return;
    const el = event.target.closest('a,button,summary,input[type=checkbox],input[type=file]');
    if (!el || el.disabled) return;
    const article = el.closest('[data-article]')?.dataset.article;
    const params = {page: location.pathname, ...(article ? {article} : {})};
    if (document.body.dataset.productSlug) {
      let element, item, state;
      if (el.matches('[data-select-variant],[data-select-size]')) {
        element = 'catalog_variant_table';
        item = [...document.querySelectorAll('[data-select-variant],[data-select-size]')].indexOf(el) + 1;
      } else if (el.matches('.gallery-thumb')) {
        element = 'catalog_gallery';
        item = [...document.querySelectorAll('.gallery-thumb')].indexOf(el) + 1;
      } else if (el.matches('.faq-list summary')) {
        element = 'catalog_faq';
        item = [...document.querySelectorAll('.faq-list summary')].indexOf(el) + 1;
        state = el.closest('details').open ? 'closed' : 'open';
      }
      if (element) {
        goal('ui_click', {...catalogParams(), element, item, ...(state ? {state} : {})});
        return;
      }
    }
    if (el.dataset.blogCta) {
      navigationGoal(event, el, 'blog_cta_click', {...params, article: el.dataset.article, cta: el.dataset.blogCta});
      return;
    }
    const href = el.getAttribute('href') || '';
    if (el.dataset.businessCta) {
      goal('request_open', {...params, context: 'business', element: el.dataset.businessCta, intent: el.dataset.businessIntent || 'unspecified'});
      return;
    }
    if (el.getAttribute('role') === 'tab' && el.closest('.b2b-tabs')) return;
    if (/^(mailto:|tel:)/i.test(href)) {
      goal('contact_click', {...params, method: href.startsWith('mailto:') ? 'email' : 'phone'});
      return;
    }
    if (el.tagName === 'A' && href) {
      const url = new URL(href, location.href);
      if (['http:', 'https:'].includes(url.protocol) && !localHosts.has(url.hostname)) {
        navigationGoal(event, el, 'outbound_click', {...params, host: url.hostname, element: el.dataset.track || 'external_link'});
        return;
      }
    }
    if (el.hasAttribute('data-request')) {
      goal('request_open', {...params, product: document.body.dataset.productSlug || 'catalog'});
      return;
    }
    if (el.dataset.track || el.tagName === 'A') navigationGoal(event, el, 'ui_click', {...params, element: el.dataset.track || 'internal_link'});
  }
  document.addEventListener('click', trackClick);
  document.addEventListener('auxclick', trackClick);
  document.addEventListener('change', event => {
    const input = event.target;
    if (!document.body.dataset.productSlug || !input.matches('.size-picker input[type=radio]')) return;
    const group = input.closest('fieldset');
    goal('ui_click', {...catalogParams(), element: 'catalog_variant',
      group: input.dataset.option || 'size', item: [...group.querySelectorAll('input[type=radio]')].indexOf(input) + 1});
  });
  document.addEventListener('blog-interaction', event => {
    const {article, element, block, item, state} = event.detail || {};
    if (!['blog_tab', 'blog_accordion', 'blog_checklist'].includes(element)) return;
    goal('ui_click', {page: location.pathname, article, element, block, item, state});
  });
  document.querySelectorAll('form').forEach(form => {
    const params = () => form.dataset.context === 'business' ? {page: location.pathname, context: 'business', intent: form.elements.business_intent.value || 'unspecified'} : catalogParams();
    form.addEventListener('focusin', () => goal('form_start', params()), {once: true});
    form.addEventListener('submit', () => {
      if (form.checkValidity()) goal('form_submit_attempt', params());
    });
  });
  document.addEventListener('lead-saved', event => goal('lead_submitted', event.detail?.context === 'business' ? {page: location.pathname, context: 'business', intent: event.detail.intent} : catalogParams()));
  document.addEventListener('business-interaction', event => {
    const {element, item, state} = event.detail || {};
    if (!['business_material', 'business_intent', 'business_faq'].includes(element)) return;
    goal('ui_click', {page: location.pathname, context: 'business', element, item, state});
  });
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
