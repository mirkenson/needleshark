'use strict';
// Catalogue UI and submissions to the existing durable lead endpoint.
const galleriesElement = document.querySelector('#product-galleries');
const galleries = JSON.parse(galleriesElement?.textContent || '{}');
let activeGallery = null;
function showGalleryPhoto(button) {
    const buttons = [...document.querySelectorAll('.gallery-thumbs [data-gallery-src]')];
    const index = buttons.indexOf(button);
    if (index < 0) return;
    const photo = document.querySelector('#gallery-image');
    if (button.dataset.galleryWidth) photo.width = Number(button.dataset.galleryWidth);
    if (button.dataset.galleryHeight) photo.height = Number(button.dataset.galleryHeight);
    photo.srcset = button.dataset.gallerySrcset || '';
    photo.src = button.dataset.gallerySrc;
    photo.alt = button.dataset.galleryAlt;
    buttons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    document.querySelector('#photo-index').textContent = `${String(index + 1).padStart(2, '0')} / ${String(buttons.length).padStart(2, '0')}`;
    document.querySelector('#gallery-caption').textContent = button.dataset.galleryLabel;
}
document.querySelector('.gallery-thumbs')?.addEventListener('click', event => {
  const button = event.target.closest('[data-gallery-src]');
  if (button) showGalleryPhoto(button);
});
function setPhoto(photo, image) {
  photo.width = image.photo.width;
  photo.height = image.photo.height;
  photo.srcset = image.photo.srcset || '';
  photo.src = image.photo.src;
  photo.alt = image.alt;
}
function setGalleryText(selector, text) {
  const node = document.querySelector(selector);
  if (node) node.textContent = text;
}
function activateGallery(key) {
  if (key === activeGallery || !galleries[key]) return;
  const gallery = galleries[key];
  activeGallery = key;
  document.querySelector('.gallery').dataset.galleryId = key;
  const buttons = gallery.images.map(image => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'gallery-thumb';
    Object.assign(button.dataset, {gallerySrc: image.photo.src, gallerySrcset: image.photo.srcset || '',
      galleryAlt: image.alt, galleryLabel: image.label, galleryWidth: image.photo.width, galleryHeight: image.photo.height});
    button.setAttribute('aria-label', image.label);
    const thumbnail = document.createElement('img');
    Object.entries(image.thumbnail).forEach(([name, value]) => thumbnail.setAttribute(name, value));
    thumbnail.alt = image.alt;
    thumbnail.decoding = 'async';
    button.append(thumbnail);
    return button;
  });
  document.querySelector('.gallery-thumbs').replaceChildren(...buttons);
  showGalleryPhoto(buttons[0]);
  setGalleryText('#gallery-model', gallery.label);
  document.querySelectorAll('[data-product-photo]').forEach(photo => setPhoto(photo, gallery.photos[photo.dataset.productPhoto]));
  setGalleryText('#material-description', gallery.materialText);
  setGalleryText('#material-caption', gallery.materialCaption);
  setGalleryText('#construction-label', gallery.label);
  const template = [...document.querySelectorAll('[data-gallery-features]')].find(item => item.dataset.galleryFeatures === key);
  if (template) document.querySelector('#construction-content').replaceChildren(template.content.cloneNode(true));
}
activateGallery(galleriesElement?.dataset.defaultGallery);

const sizeInputs = [...document.querySelectorAll('[name="product-size"]')];
function updateSize() {
  const selectedInput = sizeInputs.find(input => input.checked);
  const selected = selectedInput?.value;
  document.querySelectorAll('[data-size-market="Ozon"]').forEach(link => {
    if (selectedInput?.dataset.ozonUrl) {
      link.href = selectedInput.dataset.ozonUrl;
      link.setAttribute('aria-label', `Перейти на Ozon: ${selected} см`);
    }
  });
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
if (sizeInputs.some(input => input.checked)) updateSize();

// Only combinations listed in product data can be selected. Additional groups
// (for example colour) use the same controls without inventing combinations.
const variants = JSON.parse(document.querySelector('#product-variants')?.textContent || '[]').map(variant => ({
  ...variant, label: variant.label || [variant.summary, variant.sizeLabel].filter(Boolean).join(' · ')
}));
const optionInputs = [...document.querySelectorAll('[data-option]')];
const optionGroups = [...new Set(optionInputs.map(input => input.dataset.option))];
const packProduct = variants.some(variant => variant.unitsPerPack > 1);
let selectedVariant = variants[0] || null;
function updateVariant(variant) {
  selectedVariant = variant;
  optionInputs.forEach(input => {
    const group = input.dataset.option;
    input.checked = variant.options[group] === input.value;
    const preceding = optionGroups.slice(0, optionGroups.indexOf(group));
    input.disabled = !variants.some(candidate => candidate.options[group] === input.value &&
      preceding.every(key => candidate.options[key] === variant.options[key]));
  });
  document.querySelector('#variant-selection').textContent = `Выбрано: ${variant.label}`;
  document.querySelectorAll('[data-variant-market="Ozon"]').forEach(link => {
    if (variant.ozonUrl) link.href = variant.ozonUrl;
    else link.removeAttribute('href');
    link.setAttribute('aria-disabled', String(!variant.ozonUrl));
    link.setAttribute('aria-label', `Перейти на Ozon: ${variant.label}`);
  });
  activateGallery(variant.galleryId);
  setGalleryText('#kit-configuration', variant.label);
  const kit = document.querySelector('#variant-kit');
  if (kit) kit.replaceChildren(...variant.kit.map((text, index) => {
    const item = document.createElement('li');
    const number = document.createElement('span');
    number.textContent = String(index + 1).padStart(2, '0');
    item.append(number, document.createTextNode(text));
    return item;
  }));
  document.querySelectorAll('[data-select-variant]').forEach(button => {
    const active = button.dataset.selectVariant === variant.id;
    button.closest('tr').classList.toggle('is-selected', active);
    button.setAttribute('aria-pressed', String(active));
    button.innerHTML = active ? 'Выбрано <span aria-hidden="true">✓</span>' : 'Выбрать <span aria-hidden="true">↗</span>';
  });
  const note = document.querySelector('#selected-size-note');
  if (note) note.textContent = `Выбрано: ${variant.label}. Этот вариант появится в заявке.`;
  const quantity = document.querySelector('[name="quantity"]');
  if (quantity && packProduct) quantity.max = String(Math.floor(1000000 / variant.unitsPerPack));
}
optionInputs.forEach(input => input.addEventListener('change', () => {
  const group = input.dataset.option;
  const candidates = variants.filter(variant => variant.options[group] === input.value);
  const score = variant => optionGroups.filter(key => key !== group && variant.options[key] === selectedVariant.options[key]).length;
  candidates.sort((a, b) => score(b) - score(a));
  if (candidates[0]) updateVariant(candidates[0]);
}));
document.querySelectorAll('[data-select-variant]').forEach(button => button.addEventListener('click', () => {
  const variant = variants.find(item => item.id === button.dataset.selectVariant);
  if (variant) updateVariant(variant);
}));
if (selectedVariant) updateVariant(selectedVariant);

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
if (packProduct) {
  const label = requestForm.elements.quantity.closest('label');
  label.firstChild.textContent = 'Количество комплектов';
}
const quantityLabel = requestForm?.elements.quantity.closest('label');
if (quantityLabel && document.body.dataset.productSlug === 'stropa-remennaya') quantityLabel.firstChild.textContent = 'Количество отрезов по 10 м';
if (quantityLabel && document.body.dataset.productSlug === 'bahily-mnogorazovye') quantityLabel.firstChild.textContent = 'Количество пар';
let customLength = false;
let sending = false;
let submissionId = null;
let submissionContent = null;
document.querySelectorAll('[data-request]').forEach(button => button.addEventListener('click', () => {
  if (sending) return;
  customLength = button.dataset.request === 'Свой метраж';
  const selected = sizeInputs.find(input => input.checked)?.value;
  const product = document.body.dataset.productName;
  const choice = customLength ? `${selectedVariant.label.replace(' × 10 м', '')} · длина по заявке` : selectedVariant ? selectedVariant.label : (selected ? `${selected} см` : 'размер пока не выбран');
  const context = product ? `${product} · ${choice}` : 'Готовые изделия и пошив партии';
  document.querySelector('#request-context').textContent = context;
  requestForm.elements.intent.value = intentValues[button.dataset.request] || 'direct';
  quantityLabel.hidden = customLength;
  document.querySelector('#request-title').textContent = customLength ? 'Стропа нужной длины' : (requestForm.elements.intent.value === 'wholesale' ? 'Получить расчёт партии' : 'Уточнить цену и заказ');
  document.querySelector('.request-description').textContent = customLength ? 'Укажите ширину и нужную длину в комментарии. Условия отреза и стоимость согласуем с вами.' : 'Оставьте контакт и количество. Менеджер уточнит детали, стоимость и доставку.';
  requestForm.elements.question.placeholder = customLength ? 'Нужная длина в метрах и количество отрезов' : 'Варианты, количество, город и ваши вопросы';
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
  const quantity = customLength || requestForm.elements.quantity.value === '' ? null : Number(requestForm.elements.quantity.value);
  const question = requestForm.elements.question.value.trim() || 'Обращение по каталогу.';
  const variantContext = customLength ? `Ременная стропа. Ширина: ${selectedVariant.label.replace(' × 10 м', '')}. Длина по заявке.\n` : selectedVariant ? `${selectedVariant.context}\n${selectedVariant.sizeLabel ? `Габариты / типоразмер: ${selectedVariant.sizeLabel}\n` : ''}Артикул варианта: ${selectedVariant.id}\n${packProduct ? `${document.body.dataset.unitLabel || 'Чехлов'} в комплекте: ${selectedVariant.unitsPerPack}\nКоличество комплектов: ${quantity ?? 'не указано'}\n` : ''}\nКомментарий: ` : '';
  const payload = {
    name: requestForm.elements.name.value.trim(),
    contact: value,
    question: variantContext + (customLength ? 'Запрос своего метража. ' : '') + question,
    consent: requestForm.elements.consent.checked,
    website: requestForm.elements.website.value,
    product_slug: document.body.dataset.productSlug || '',
    product_name: document.body.dataset.productName || '',
    product_size: customLength ? '' : selectedVariant ? selectedVariant.legacySize : sizeInputs.find(input => input.checked)?.value || '',
    inquiry_type: requestForm.elements.intent.value,
    quantity: quantity === null ? null : quantity * (selectedVariant?.unitsPerPack || 1),
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
