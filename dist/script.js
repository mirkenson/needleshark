// Form submissions are persisted by the server before confirmation.
const form = document.querySelector('#request-form');
const status = document.querySelector('#form-status');
const submit = form.querySelector('[type=submit]');
let submissionId = null;
let sending = false;
form.addEventListener('input', () => { if (!sending) submissionId = null; });
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
  status.hidden = false;
  const file = form.elements.attachment.files[0];
  if (file && (file.size > 2 * 1024 * 1024 || !['image/jpeg', 'image/png', 'application/pdf'].includes(file.type))) {
    status.textContent = 'Прикрепите JPG, PNG или PDF размером до 2 МБ.';
    return;
  }
  submissionId ||= crypto.randomUUID();
  const payload = {id: submissionId, name: form.elements.name.value, contact: form.elements.contact.value, question: form.elements.question.value, website: form.elements.website?.value || ''};
  sending = true;
  const controls = [...form.querySelectorAll('input,textarea,button')];
  controls.forEach(control => { control.disabled = true; });
  status.textContent = 'Отправляем заявку…';
  try {
    if (file) payload.attachment = {name: file.name, type: file.type, data: await fileData(file)};
    const response = await fetch('/api/leads', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload), signal: AbortSignal.timeout(25000)});
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.ok) throw new Error(result.error || 'Не удалось отправить заявку. Попробуйте ещё раз или напишите на info@neesha.ru.');
    status.textContent = 'Заявка получена. Мы свяжемся с вами по указанному контакту.';
    form.reset();
    document.querySelector('#filename').textContent = '';
    submissionId = null;
  } catch (error) {
    status.textContent = error.name === 'TimeoutError' || error.name === 'TypeError'
      ? 'Не удалось получить подтверждение. Повторите отправку — повторная заявка не создастся.'
      : error.message;
  } finally {
    sending = false;
    controls.forEach(control => { control.disabled = false; });
  }
});
