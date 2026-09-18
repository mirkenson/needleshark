(() => {
  'use strict';
  const form = document.querySelector('#request-form');
  const emit = (element, item, state) => document.dispatchEvent(new CustomEvent('business-interaction', {detail: {element, item, state}}));
  const tablist = document.querySelector('.b2b-tabs');
  const tabs = [...tablist.querySelectorAll('a')];
  const panels = tabs.map(tab => document.querySelector(tab.getAttribute('href')));
  tablist.setAttribute('role', 'tablist');
  tabs.forEach((tab, index) => {
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-controls', panels[index].id);
    panels[index].setAttribute('role', 'tabpanel');
    panels[index].setAttribute('aria-labelledby', tab.id);
    panels[index].tabIndex = 0;
  });
  let selected = -1;
  function select(index, focus = false, track = false) {
    const changed = selected !== index;
    selected = index;
    tabs.forEach((tab, i) => {
      tab.setAttribute('aria-selected', String(i === index));
      tab.tabIndex = i === index ? 0 : -1;
      panels[i].hidden = i !== index;
    });
    if (focus) tabs[index].focus({preventScroll: true});
    if (track && changed) emit('business_material', panels[index].dataset.material, 'selected');
  }
  function fromHash() {
    const index = panels.findIndex(panel => '#' + panel.id === location.hash);
    if (index !== -1) select(index);
  }
  select(Math.max(0, panels.findIndex(panel => '#' + panel.id === location.hash)));
  window.addEventListener('hashchange', fromHash);
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', event => { event.preventDefault(); select(index, false, true); });
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (event.key === ' ') next = index;
      if (next !== undefined) { event.preventDefault(); select(next, true, true); }
    });
  });
  document.querySelectorAll('[data-business-intent]').forEach(link => link.addEventListener('click', () => {
    if (form.querySelector('[type=submit]').disabled) return;
    const choice = form.querySelector(`input[value="${link.dataset.businessIntent}"]`);
    choice.checked = true;
    if (!form.elements.question.value.trim()) {
      if (link.dataset.businessProduct) form.elements.question.value = `Интересует партия: ${link.dataset.businessProduct}. `;
      if (link.dataset.businessMaterial) form.elements.question.value = `Интересует материал: ${link.dataset.businessMaterial}. `;
    }
    form.dispatchEvent(new Event('input', {bubbles: true}));
  }));
  form.querySelectorAll('[name=business_intent]').forEach(input => input.addEventListener('change', () => emit('business_intent', input.value, 'selected')));
  document.querySelectorAll('[data-business-faq]').forEach(detail => detail.addEventListener('toggle', () => emit('business_faq', detail.dataset.businessFaq, detail.open ? 'open' : 'closed')));
})();
