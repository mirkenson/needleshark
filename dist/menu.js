(() => {
  'use strict';
  const button = document.querySelector('.menu-toggle');
  const menu = document.querySelector('#mobile-menu');
  if (!button || !menu) return;
  const close = () => { button.setAttribute('aria-expanded', 'false'); menu.hidden = true; };
  button.addEventListener('click', () => {
    const open = button.getAttribute('aria-expanded') === 'true';
    button.setAttribute('aria-expanded', String(!open));
    menu.hidden = open;
  });
  menu.addEventListener('click', event => { if (event.target.closest('a')) close(); });
  document.addEventListener('keydown', event => {
    // Let an open modal handle Escape first; its opener must stay visible for focus return.
    if (event.key === 'Escape' && !menu.hidden && !document.querySelector('dialog[open]')) {
      close(); button.focus();
    }
  });
})();
