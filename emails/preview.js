'use strict';
const frame = document.getElementById('email-frame');
const stage = document.getElementById('stage');
const font = document.getElementById('font');
const caption = document.getElementById('review-caption');
const templates = {
  received: {name: 'Получили обращение', subject: 'Получили ваше обращение — Needle Shark', status: 'Сохранено в Unisender · 16 октября', note: 'Первое письмо уже сохранено как шаблон в Unisender. Автоматическая отправка пока не включена.'},
  details: {name: 'Уточнение данных', subject: 'Уточним детали вашего запроса — Needle Shark', status: 'Сохранено в Unisender · 19 октября', note: 'Вместо текста в квадратных скобках впишите необходимые данные и вопросы. Их состав вы определяете сами.'},
  quote: {name: 'Коммерческое предложение', subject: 'Коммерческое предложение: [Название партии] — Needle Shark', status: 'Сохранено в Unisender · 19 октября', note: 'Впишите название партии, изделие, количество и рассчитанную сумму. Название партии также замените в теме. Комментарий к расчёту можно заполнить или удалить целиком.'},
  'follow-up': {name: 'Напоминание', subject: 'Актуален ли ваш запрос? — Needle Shark', status: 'Сохранено в Unisender · 19 октября', note: 'Короткое напоминание после письма без ответа. Подходит и после запроса данных, и после коммерческого предложения.'}
};
let mobile = false;
let resizeObserver;
function selectTemplate() {
  const hash = location.hash.slice(1);
  const key = Object.hasOwn(templates, hash) ? hash : 'details';
  const template = templates[key];
  document.querySelectorAll('[data-template]').forEach(link => {
    if (link.dataset.template === key) link.setAttribute('aria-current', 'true');
    else link.removeAttribute('aria-current');
  });
  document.getElementById('subject').textContent = template.subject;
  document.getElementById('review-status').textContent = template.status;
  document.getElementById('template-note').textContent = template.note;
  frame.title = `Письмо: ${template.name}`;
  if (frame.getAttribute('src') !== `${key}.html`) frame.src = `${key}.html`;
}
function fit() {
  if (!frame.contentDocument?.body) return;
  frame.style.height = `${Math.ceil(frame.contentDocument.body.getBoundingClientRect().height)}px`;
}
function update() {
  stage.classList.toggle('mobile', mobile);
  document.querySelectorAll('[data-size]').forEach(button => {
    button.setAttribute('aria-pressed', String((button.dataset.size === 'mobile') === mobile));
  });
  const doc = frame.contentDocument;
  if (doc?.body) {
    let override = doc.getElementById('preview-font-override');
    if (!override) { override = doc.createElement('style'); override.id = 'preview-font-override'; doc.head.append(override); }
    override.textContent = font.value === 'Arial' ? 'body,td,div,p,h1,a,span,strong{font-family:Arial,sans-serif!important}' : '';
  }
  caption.textContent = `${font.value} · макет для ${mobile ? 'телефона' : 'компьютера'}`;
  requestAnimationFrame(fit);
}
frame.addEventListener('load', async () => {
  resizeObserver?.disconnect();
  resizeObserver = new ResizeObserver(fit);
  resizeObserver.observe(frame.contentDocument.body);
  update();
  await frame.contentDocument.fonts.ready;
  fit();
});
document.querySelectorAll('[data-size]').forEach(button => button.addEventListener('click', () => {
  mobile = button.dataset.size === 'mobile'; update();
}));
font.addEventListener('change', update);
window.addEventListener('resize', fit);
window.addEventListener('hashchange', selectTemplate);
selectTemplate();
