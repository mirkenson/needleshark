'use strict';
// Prototype-only interactions. No analytics, network requests or persisted input.
const menuButton = document.querySelector('.menu-toggle');
const mobileMenu = document.querySelector('#mobile-menu');
menuButton?.addEventListener('click', () => {
  const expanded = menuButton.getAttribute('aria-expanded') === 'true';
  menuButton.setAttribute('aria-expanded', String(!expanded));
  mobileMenu.hidden = expanded;
});
document.querySelectorAll('[data-gallery-src]').forEach((button, index, buttons) => {
  button.addEventListener('click', () => {
    const photo = document.querySelector('#gallery-image');
    photo.src = button.dataset.gallerySrc;
    photo.alt = button.dataset.galleryAlt;
    buttons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    document.querySelector('#photo-index').textContent = `${String(index + 1).padStart(2, '0')} / ${String(buttons.length).padStart(2, '0')}`;
    document.querySelector('#gallery-caption').textContent = button.dataset.galleryLabel;
  });
});

const sizeInputs = [...document.querySelectorAll('[name="product-size"]')];
function updateSize() {
  const selected = sizeInputs.find(input => input.checked)?.value;
  document.querySelectorAll('[data-select-size]').forEach(button => {
    const active = button.dataset.selectSize === selected;
    button.closest('tr').classList.toggle('is-selected', active);
    button.setAttribute('aria-pressed', String(active));
    button.innerHTML = active ? 'Выбрано <span aria-hidden="true">✓</span>' : 'Выбрать <span aria-hidden="true">↗</span>';
  });
  const note = document.querySelector('#selected-size-note');
  if (note) note.textContent = selected ? `Выбран размер ${selected} см. Он появится в вашей заявке.` : 'Выберите размер — он появится в вашей заявке.';
}
sizeInputs.forEach(input => input.addEventListener('change', updateSize));
document.querySelectorAll('[data-select-size]').forEach(button => button.addEventListener('click', () => {
  const input = sizeInputs.find(item => item.value === button.dataset.selectSize);
  if (input) input.checked = true;
  updateSize();
}));

let dialogOpener = null;
function openDialog(dialog, opener) {
  if (!dialog) return;
  dialogOpener = opener;
  dialog.showModal();
  document.body.classList.add('dialog-open');
}
document.querySelectorAll('dialog').forEach(dialog => {
  dialog.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => dialog.close()));
  dialog.addEventListener('close', () => {
    document.body.classList.remove('dialog-open');
    dialogOpener?.focus();
  });
});
const marketDialog = document.querySelector('#market-dialog');
document.querySelectorAll('[data-market]').forEach(button => button.addEventListener('click', () => {
  document.querySelector('#market-title').textContent = button.dataset.market;
  document.querySelector('#market-message').textContent = `Ссылка на товар в ${button.dataset.market} будет добавлена перед публикацией.`;
  openDialog(marketDialog, button);
}));

const requestDialog = document.querySelector('#request-dialog');
const requestForm = document.querySelector('#catalog-request');
const requestResult = document.querySelector('#request-result');
const contactError = document.querySelector('#contact-error');
document.querySelectorAll('[data-request]').forEach(button => button.addEventListener('click', () => {
  const selected = sizeInputs.find(input => input.checked)?.value;
  const product = document.body.dataset.productName;
  const context = product ? `${product} · ${selected ? `${selected} см` : 'размер пока не выбран'}` : 'Готовые изделия и пошив партии';
  document.querySelector('#request-context').textContent = context;
  requestForm.elements.intent.value = button.dataset.request;
  requestResult.hidden = true;
  openDialog(requestDialog, button);
}));
requestForm?.elements.contact.addEventListener('input', () => {
  requestForm.elements.contact.setCustomValidity('');
  requestForm.elements.contact.removeAttribute('aria-invalid');
  contactError.hidden = true;
});
requestForm?.addEventListener('input', () => { requestResult.hidden = true; });
requestForm?.addEventListener('submit', event => {
  event.preventDefault();
  const contact = requestForm.elements.contact;
  const value = contact.value.trim();
  const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  const validPhone = /^\+?[\d\s()\-]+$/.test(value) && value.replace(/\D/g, '').length >= 10 && value.replace(/\D/g, '').length <= 15;
  if (!validEmail && !validPhone) {
    contactError.textContent = 'Укажите email или телефон с кодом страны, например +7 999 123-45-67.';
    contactError.hidden = false;
    contact.setAttribute('aria-invalid', 'true');
    contact.setCustomValidity(contactError.textContent);
    contact.reportValidity();
    return;
  }
  if (!requestForm.reportValidity()) return;
  requestResult.textContent = 'Форма заполнена. Это прототип: заявка не отправлена и данные не сохранены. В готовой версии здесь появится подтверждение после получения заявки сервером.';
  requestResult.hidden = false;
});
mobileMenu?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
  mobileMenu.hidden = true;
  menuButton.setAttribute('aria-expanded', 'false');
}));
