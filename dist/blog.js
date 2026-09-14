(() => {
  'use strict';
  document.querySelectorAll('[data-article-tabs]').forEach(group => {
    const list = group.querySelector('.article-tab-list');
    const tabs = [...list.querySelectorAll('[data-tab-target]')];
    const panels = tabs.map(tab => document.getElementById(tab.dataset.tabTarget));
    if (panels.some(panel => !panel)) return;
    const select = index => {
      tabs.forEach((tab, i) => {
        tab.setAttribute('aria-selected', String(i === index));
        tab.tabIndex = i === index ? 0 : -1;
        panels[i].hidden = i !== index;
      });
    };
    list.setAttribute('role', 'tablist');
    tabs.forEach((tab, index) => {
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-controls', panels[index].id);
      panels[index].setAttribute('role', 'tabpanel');
      panels[index].setAttribute('aria-labelledby', tab.id);
      panels[index].tabIndex = 0;
      tab.addEventListener('click', () => select(index));
      tab.addEventListener('keydown', event => {
        const next = {ArrowRight: (index + 1) % tabs.length, ArrowLeft: (index - 1 + tabs.length) % tabs.length, Home: 0, End: tabs.length - 1}[event.key];
        if (next === undefined) return;
        event.preventDefault();
        select(next);
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
    group.addEventListener('change', update);
    update();
    status.hidden = false;
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
