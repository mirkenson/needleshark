(() => {
  'use strict';
  const article = document.querySelector('.blog-article[data-article]');
  const track = (event, element, group, index, state) => {
    if (!event.isTrusted || !article) return;
    document.dispatchEvent(new CustomEvent('blog-interaction', {detail: {
      article: article.dataset.article, element, block: group.dataset.blogBlock,
      item: index + 1, state
    }}));
  };
  document.querySelectorAll('[data-article-tabs]').forEach(group => {
    const list = group.querySelector('.article-tab-list');
    const tabs = [...list.querySelectorAll('[data-tab-target]')];
    const panels = tabs.map(tab => document.getElementById(tab.dataset.tabTarget));
    if (panels.some(panel => !panel)) return;
    const select = (index, event) => {
      const changed = tabs[index].getAttribute('aria-selected') !== 'true';
      tabs.forEach((tab, i) => {
        tab.setAttribute('aria-selected', String(i === index));
        tab.tabIndex = i === index ? 0 : -1;
        panels[i].hidden = i !== index;
      });
      if (event && changed) track(event, 'blog_tab', group, index, 'selected');
    };
    list.setAttribute('role', 'tablist');
    tabs.forEach((tab, index) => {
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-controls', panels[index].id);
      panels[index].setAttribute('role', 'tabpanel');
      panels[index].setAttribute('aria-labelledby', tab.id);
      panels[index].tabIndex = 0;
      tab.addEventListener('click', event => select(index, event));
      tab.addEventListener('keydown', event => {
        const next = {ArrowRight: (index + 1) % tabs.length, ArrowLeft: (index - 1 + tabs.length) % tabs.length, Home: 0, End: tabs.length - 1}[event.key];
        if (next === undefined) return;
        event.preventDefault();
        select(next, event);
        tabs[next].focus();
      });
    });
    group.classList.add('is-enhanced');
    select(0);
    list.hidden = false;
  });

  document.querySelectorAll('[data-article-checklist]').forEach(group => {
    const inputs = [...group.querySelectorAll('input[type="checkbox"]')];
    const status = group.querySelector('.checklist-status');
    const update = () => {
      const count = inputs.filter(input => input.checked).length;
      status.textContent = count === inputs.length ? `Все ${count} пунктов отмечены. Памятка готова.` : `Отмечено ${count} из ${inputs.length}`;
    };
    group.addEventListener('change', event => {
      update();
      const index = inputs.indexOf(event.target);
      if (index >= 0) track(event, 'blog_checklist', group, index, event.target.checked ? 'checked' : 'unchecked');
    });
    update();
    status.hidden = false;
  });

  document.querySelectorAll('.article-accordion').forEach(group => {
    group.querySelectorAll('details').forEach((detail, index) => {
      detail.querySelector('summary').addEventListener('click', event => {
        requestAnimationFrame(() => {
          if (!event.defaultPrevented) track(event, 'blog_accordion', group, index, detail.open ? 'open' : 'closed');
        });
      });
    });
  });

  // Notes can point back into a collapsed disclosure or an inactive tab.
  const revealTarget = () => {
    let target;
    try { target = document.getElementById(decodeURIComponent(location.hash.slice(1))); } catch (_) { return; }
    if (!target || !target.closest('.blog-article')) return;
    const disclosure = target.closest('details');
    if (disclosure) disclosure.open = true;
    const panel = target.closest('.article-tab-panel');
    if (panel?.hidden) {
      panel.closest('[data-article-tabs]').querySelector(`[aria-controls="${panel.id}"]`)?.click();
    }
    if (disclosure || panel) target.scrollIntoView({block: 'start'});
    target.focus({preventScroll: true});
  };
  window.addEventListener('hashchange', revealTarget);
  revealTarget();
})();
