'use strict';
// Catalogue UI and submissions to the existing durable lead endpoint.
document.querySelectorAll('[data-gallery-src]').forEach((button, index, buttons) => {
  button.addEventListener('click', () => {
    const photo = document.querySelector('#gallery-image');
    photo.srcset = button.dataset.gallerySrcset || '';
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
const requestDialog = document.querySelector('#request-dialog');
const requestForm = document.querySelector('#catalog-request');
const requestResult = document.querySelector('#request-result');
const contactError = document.querySelector('#contact-error');
const intentValues = {'Заказ напрямую': 'direct', 'Подбор размера': 'sizing', 'Партия для бизнеса': 'wholesale'};
let sending = false;
let submissionId = null;
let submissionContent = null;
document.querySelectorAll('[data-request]').forEach(button => button.addEventListener('click', () => {
  if (sending) return;
  const selected = sizeInputs.find(input => input.checked)?.value;
  const product = document.body.dataset.productName;
  const context = product ? `${product} · ${selected ? `${selected} см` : 'размер пока не выбран'}` : 'Готовые изделия и пошив партии';
  document.querySelector('#request-context').textContent = context;
  requestForm.elements.intent.value = intentValues[button.dataset.request] || 'direct';
  requestResult.hidden = true;
  openDialog(requestDialog, button);
}));
requestForm?.elements.contact.addEventListener('input', () => {
  requestForm.elements.contact.setCustomValidity('');
  requestForm.elements.contact.removeAttribute('aria-invalid');
  contactError.hidden = true;
});
requestForm?.addEventListener('input', () => { requestResult.hidden = true; });
requestForm?.addEventListener('submit', async event => {
  event.preventDefault();
  if (sending) return;
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
  const payload = {
    name: requestForm.elements.name.value.trim(),
    contact: value,
    question: requestForm.elements.question.value.trim() || 'Обращение по каталогу.',
    consent: requestForm.elements.consent.checked,
    website: requestForm.elements.website.value,
    product_slug: document.body.dataset.productSlug || '',
    product_name: document.body.dataset.productName || '',
    product_size: sizeInputs.find(input => input.checked)?.value || '',
    inquiry_type: requestForm.elements.intent.value,
    quantity: requestForm.elements.quantity.value === '' ? null : Number(requestForm.elements.quantity.value),
    source_path: location.pathname
  };
  // Reuse the ID after a lost response; a changed request gets its own ID.
  const content = JSON.stringify(payload);
  if (!submissionId || content !== submissionContent) {
    submissionId = crypto.randomUUID();
    submissionContent = content;
  }
  payload.id = submissionId;
  sending = true;
  const controls = [...requestForm.querySelectorAll('input,textarea,select,button')];
  controls.forEach(control => { control.disabled = true; });
  requestResult.hidden = false;
  requestResult.dataset.state = 'pending';
  requestResult.textContent = 'Отправляем заявку…';
  try {
    const response = await fetch('/api/leads', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
      signal: AbortSignal.timeout(25000)
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || result.ok !== true || result.id !== payload.id) {
      if (response.status === 409) submissionId = null;
      throw new Error(result.error || 'Не удалось получить подтверждение. Повторите отправку или напишите на info@neesha.ru.');
    }
    requestResult.dataset.state = 'success';
    requestResult.textContent = 'Заявка получена. Свяжемся с вами по указанному контакту, чтобы обсудить заказ.';
    document.dispatchEvent(new Event('lead-saved'));
    requestForm.reset();
    submissionId = null;
    submissionContent = null;
  } catch (error) {
    requestResult.dataset.state = 'error';
    requestResult.textContent = error.name === 'TimeoutError' || error.name === 'TypeError'
      ? 'Не удалось получить подтверждение. Повторите отправку — повторная заявка не создастся.'
      : error.message;
  } finally {
    sending = false;
    controls.forEach(control => { control.disabled = false; });
  }
});
