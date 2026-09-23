/* Progressive catalogue filtering. Free-form searches never enter URLs or analytics. */
(() => {
  'use strict';
  const normalize = value => String(value).normalize('NFKC').toLocaleLowerCase('ru-RU')
    .replaceAll('ё', 'е').replace(/[\u2010-\u2015\u2212]/g, '-');
  const matches = (text, query) => normalize(query).trim().split(/\s+/).filter(Boolean)
    .every(term => normalize(text).includes(term));
  if (typeof module !== 'undefined') module.exports = {normalize, matches};
  if (typeof document === 'undefined') return;
  const tools = document.querySelector('#catalog-tools');
  if (!tools) return;
  const search = document.querySelector('#catalog-search');
  const cards = [...document.querySelectorAll('.catalog-card')];
  const buttons = [...document.querySelectorAll('[data-category-filter]')];
  const reset = document.querySelector('#catalog-reset');
  const disclosure = document.querySelector('#category-picker');
  const allowed = new Set(buttons.map(button => button.dataset.categoryFilter));
  const fromURL = new URL(location.href).searchParams.get('category') || '';
  const saved = history.state?.needleCatalog;
  let category = allowed.has(fromURL) ? fromURL : '';
  // Session-history state restores Back navigation; no persistent local/session storage.
  if (saved && saved.category === category && typeof saved.query === 'string') search.value = saved.query.slice(0, 150);
  const remember = () => {
    try {
      const url = new URL(location.href);
      if (category) url.searchParams.set('category', category);
      else url.searchParams.delete('category');
      history.replaceState({...history.state, needleCatalog: {category, query: search.value, scrollY}}, '', url);
    } catch (_) { /* Filtering remains usable when history access is unavailable. */ }
  };
  const filter = () => {
    const matching = cards.map(card => matches(card.dataset.search || '', search.value));
    let count = 0;
    cards.forEach((card, i) => {
      const show = matching[i] && (!category || card.dataset.category === category);
      card.hidden = !show;
      if (show) count++;
    });
    buttons.forEach(button => {
      const value = button.dataset.categoryFilter;
      button.setAttribute('aria-pressed', String(value === category));
      button.querySelector('span').textContent = cards.filter((card, i) => matching[i] && (!value || card.dataset.category === value)).length;
    });
    document.querySelector('#catalog-results').textContent = `${count} из ${cards.length} изделий`;
    document.querySelector('#catalog-empty').hidden = count !== 0;
    reset.hidden = !category && !search.value;
    document.querySelector('#category-label').textContent = buttons.find(button => button.dataset.categoryFilter === category).dataset.categoryLabel;
  };
  buttons.forEach(button => button.addEventListener('click', () => {
    category = button.dataset.categoryFilter;
    filter(); remember();
    if (matchMedia('(max-width: 700px)').matches) disclosure.open = false;
  }));
  search.addEventListener('input', () => { filter(); remember(); });
  reset.addEventListener('click', () => {
    category = ''; search.value = ''; filter(); remember(); search.focus();
  });
  const compactCategories = matchMedia('(max-width: 700px)');
  disclosure.open = !compactCategories.matches;
  compactCategories.addEventListener('change', event => { disclosure.open = !event.matches; });
  tools.hidden = false;
  filter();
  const restoreScroll = () => {
    if (saved && Number.isFinite(saved.scrollY)) requestAnimationFrame(() => requestAnimationFrame(() => window.scrollTo(0, saved.scrollY)));
  };
  if (document.readyState === 'complete') restoreScroll();
  else window.addEventListener('load', restoreScroll, {once: true});
  window.addEventListener('pagehide', remember);
})();
