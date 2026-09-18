// Form submissions are persisted by the server before confirmation.
const form = document.querySelector('#request-form');
const status = document.querySelector('#form-status');
const submit = form.querySelector('[type=submit]');
const isBusiness = form.dataset.context === 'business';
let submissionId = null;
let sending = false;
form.addEventListener('input', () => {
  if (!sending) submissionId = null;
  if (isBusiness) {
    form.elements.contact.setCustomValidity('');
    form.elements.contact.removeAttribute('aria-invalid');
    document.querySelector('#contact-error').hidden = true;
  }
});
document.querySelectorAll('[data-product]').forEach(button => button.addEventListener('click', () => {
  if (sending) return;
  form.elements.question.value = 'Интересует: ' + button.dataset.product + '. ';
  submissionId = null;
  document.querySelector('#contact').scrollIntoView({behavior: 'smooth'});
}));
document.querySelector('#attachment').addEventListener('change', event => {
  document.querySelector('#filename').textContent = event.target.files[0]?.name || '';
});
function fileData(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = () => reject(new Error('Не удалось прочитать файл.'));
    reader.readAsDataURL(file);
  });
}
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (sending || !form.reportValidity()) return;
  if (isBusiness) {
    const value = form.elements.contact.value.trim();
    const email = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    const digits = value.replace(/\D/g, '').length;
    const phone = /^\+?[\d\s()\-]+$/.test(value) && digits >= 10 && digits <= 15;
    if (!email && !phone) {
      const error = document.querySelector('#contact-error');
      error.textContent = 'Укажите email или телефон с кодом страны, например +7 999 123-45-67.';
      error.hidden = false;
      form.elements.contact.setAttribute('aria-invalid', 'true');
      form.elements.contact.setCustomValidity(error.textContent);
      form.elements.contact.reportValidity();
      return;
    }
  }
  status.hidden = false;
  const file = form.elements.attachment.files[0];
  if (file && (file.size > 2 * 1024 * 1024 || !['image/jpeg', 'image/png', 'application/pdf'].includes(file.type))) {
    if (isBusiness) status.dataset.state = 'error';
    status.textContent = 'Прикрепите JPG, PNG или PDF размером до 2 МБ.';
    return;
  }
  submissionId ||= crypto.randomUUID();
  const payload = {id: submissionId, name: form.elements.name.value, contact: form.elements.contact.value, question: form.elements.question.value, consent: form.elements.consent.checked, website: form.elements.website?.value || ''};
  const intent = isBusiness ? (form.elements.business_intent.value || 'unspecified') : '';
  if (isBusiness) {
    const company = form.elements.business_company.value.trim();
    if (intent !== 'unspecified') payload.business_intent = intent;
    if (company) payload.business_company = company;
    payload.source_path = form.dataset.sourcePath;
    payload.inquiry_type = intent === 'materials' ? 'direct' : 'wholesale';
  }
  sending = true;
  const controls = [...form.querySelectorAll('input,textarea,button')];
  controls.forEach(control => { control.disabled = true; });
  status.textContent = 'Отправляем заявку…';
  if (isBusiness) status.dataset.state = 'pending';
  try {
    if (file) payload.attachment = {name: file.name, type: file.type, data: await fileData(file)};
    const response = await fetch('/api/leads', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload), signal: AbortSignal.timeout(25000)});
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.ok || (isBusiness && (result.ok !== true || result.id !== payload.id))) throw new Error(result.error || 'Не удалось отправить заявку. Попробуйте ещё раз или напишите на info@neesha.ru.');
    if (isBusiness) status.dataset.state = 'success';
    status.textContent = 'Заявка получена. Мы свяжемся с вами по указанному контакту.';
    document.dispatchEvent(isBusiness ? new CustomEvent('lead-saved', {detail: {context: 'business', intent}}) : new Event('lead-saved'));
    form.reset();
    document.querySelector('#filename').textContent = '';
    submissionId = null;
  } catch (error) {
    if (isBusiness) status.dataset.state = 'error';
    status.textContent = error.name === 'TimeoutError' || error.name === 'TypeError'
      ? 'Не удалось получить подтверждение. Повторите отправку — повторная заявка не создастся.'
      : error.message;
  } finally {
    sending = false;
    controls.forEach(control => { control.disabled = false; });
  }
});
