import {validateContacts} from './form-validation.mjs';
import {LeadClient, leadFields} from './form-client.mjs';

// Navigation stays usable with native details when JavaScript is unavailable.
const toggle = document.querySelector('.ns-menu-toggle');
const menu = document.querySelector('#ns-mobile-menu');
const dropdown = document.querySelector('.ns-directions-menu');
if (toggle && menu) {
  toggle.hidden = false;
  const closeMenu = () => { menu.hidden = true; toggle.setAttribute('aria-expanded', 'false'); };
  toggle.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') !== 'true';
    menu.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
  });
  menu.addEventListener('click', event => { if (event.target.closest('a')) closeMenu(); });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    if (!menu.hidden) { closeMenu(); toggle.focus(); }
    if (dropdown?.open) { dropdown.open = false; dropdown.querySelector('summary').focus(); }
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.ns-header')) { closeMenu(); if (dropdown) dropdown.open = false; }
  });
  matchMedia('(min-width:1001px)').addEventListener('change', event => { if (event.matches) closeMenu(); });
}

const tabs = [...document.querySelectorAll('[data-material]')];
const panels = [...document.querySelectorAll('[data-panel]')];
if (tabs.length) {
  document.querySelector('.ns-material-tabs').setAttribute('role', 'tablist');
  const select = (index, focus = false, track = false) => {
    tabs.forEach((tab, i) => {
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-selected', String(i === index));
      tab.setAttribute('aria-controls', `panel-${tab.dataset.material}`);
      tab.tabIndex = i === index ? 0 : -1;
      panels[i].hidden = i !== index;
      panels[i].setAttribute('role', 'tabpanel');
      panels[i].setAttribute('aria-labelledby', tab.id);
    });
    if (focus) tabs[index].focus();
    if (track) document.dispatchEvent(new CustomEvent('business-interaction', {detail: {element: 'business_material', item: tabs[index].dataset.material, state: 'selected'}}));
  };
  tabs.forEach((tab, i) => {
    tab.addEventListener('click', () => select(i, false, true));
    tab.addEventListener('keydown', event => {
      const next = {'ArrowRight': (i + 1) % tabs.length, 'ArrowLeft': (i + tabs.length - 1) % tabs.length, 'Home': 0, 'End': tabs.length - 1}[event.key];
      if (next === undefined) return;
      event.preventDefault(); select(next, true, true);
    });
  });
  select(0);
}

const form = document.querySelector('.ns-form');
if (form) {
  const client = new LeadClient();
  const error = document.querySelector('#contact-error');
  const status = form.querySelector('.ns-form-status');
  form.addEventListener('input', () => {
    for (const name of ['name', 'email', 'phone', 'description']) {
      form.elements[name].setCustomValidity('');
      form.elements[name].removeAttribute('aria-invalid');
    }
    error.hidden = true;
    status.hidden = true;
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (client.busy) return;
    for (const name of ['name', 'description']) {
      if (!form.elements[name].value.trim()) form.elements[name].setCustomValidity(name === 'name' ? 'Укажите имя.' : 'Опишите вашу задачу.');
    }
    const invalid = validateContacts(form.elements.email.value, form.elements.phone.value);
    if (invalid) {
      const control = form.elements[invalid.field];
      control.setCustomValidity(invalid.message);
      control.setAttribute('aria-invalid', 'true');
      error.textContent = invalid.message;
      error.hidden = false;
    }
    if (!form.reportValidity()) return;
    if (document.body.dataset.preview === 'true') {
      status.textContent = 'Это предпросмотр: заявка не отправлена. Сейчас можно написать на info@neesha.ru.';
      status.hidden = false;
      return;
    }
    const fields = leadFields({
      name: form.elements.name.value, email: form.elements.email.value,
      phone: form.elements.phone.value, description: form.elements.description.value,
      consent: form.elements.consent.checked, direction: document.body.dataset.direction,
      material: form.dataset.material || '', path: location.pathname
    });
    const controls = [...form.querySelectorAll('input,textarea,button')];
    controls.forEach(control => { control.disabled = true; });
    form.setAttribute('aria-busy', 'true');
    status.textContent = 'Сохраняем заявку…';
    status.hidden = false;
    document.dispatchEvent(new CustomEvent('b2b-form-attempt'));
    try {
      const result = await client.submit(fields);
      if (result.busy) return;
      status.textContent = 'Заявка сохранена. Свяжемся с вами по указанному контакту, чтобы уточнить задачу и подготовить расчёт.';
      if (result.firstConfirmation) document.dispatchEvent(new CustomEvent('lead-saved', {detail: {
        context: 'b2b', intent: fields.business_intent, direction: fields.business_direction,
        material: fields.business_material
      }}));
      form.reset();
      delete form.dataset.material;
      client.newInquiry();
    } catch (error) {
      status.textContent = error.message || 'Не удалось получить подтверждение. Повторите отправку или напишите на info@neesha.ru.';
    } finally {
      controls.forEach(control => { control.disabled = false; });
      form.removeAttribute('aria-busy');
      status.hidden = false;
    }
  });
  document.querySelectorAll('[data-topic]').forEach(link => {
    if (link === form) return;
    link.addEventListener('click', () => { if (!client.busy) form.dataset.topic = link.dataset.topic; });
  });
  document.querySelectorAll('[data-material-inquiry]').forEach(link => link.addEventListener('click', () => {
    if (!client.busy) form.dataset.material = link.dataset.materialInquiry;
  }));
}

const tools = document.querySelector('.ns-catalog-tools');
if (tools) {
  tools.hidden = false;
  const search = tools.querySelector('input');
  const cards = [...document.querySelectorAll('.ns-product')];
  const filters = [...tools.querySelectorAll('[data-filter]')];
  const count = document.querySelector('#product-count');
  const empty = document.querySelector('.ns-empty');
  let category = new URL(location.href).searchParams.get('category') || '';
  if (!filters.some(button => button.dataset.filter === category)) category = '';
  const normalize = text => text.toLocaleLowerCase('ru').replaceAll('ё', 'е');
  const update = () => {
    const terms = normalize(search.value.trim()).split(/\s+/).filter(Boolean);
    let visible = 0;
    cards.forEach(card => {
      card.hidden = Boolean(category && card.dataset.category !== category) || terms.some(term => !normalize(card.dataset.search).includes(term));
      if (!card.hidden) visible++;
    });
    filters.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === category)));
    count.textContent = `Найдено изделий: ${visible}`;
    empty.hidden = visible !== 0;
  };
  const reset = () => { category = ''; search.value = ''; update(); };
  filters.forEach(button => button.addEventListener('click', () => { category = button.dataset.filter; update(); }));
  search.addEventListener('input', update);
  document.querySelector('#reset-search').addEventListener('click', () => { reset(); search.focus(); });
  const revealTarget = () => {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch (_) { return; }
    const target = cards.find(card => card.id === id);
    if (!target) return;
    if (target.hidden) reset();
    target.scrollIntoView({block: 'start'});
  };
  update(); revealTarget();
  window.addEventListener('hashchange', revealTarget);
}

// Animate once on entry; primary content and interactive controls stay available.
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
if ('IntersectionObserver' in window && !reduced.matches) {
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) { entry.target.classList.add('ns-visible'); observer.unobserve(entry.target); }
  }), {threshold: 0.08});
  const elements = [...document.querySelectorAll('.ns-section-head,.ns-direction-card,.ns-production-grid,.ns-custom-cta,.ns-process>li,.ns-brief')];
  elements.forEach(element => {
    if (element.getBoundingClientRect().top < window.innerHeight) return;
    element.classList.add('ns-reveal');
    observer.observe(element);
  });
  reduced.addEventListener('change', event => {
    if (event.matches) { elements.forEach(element => element.classList.add('ns-visible')); observer.disconnect(); }
  });
}
