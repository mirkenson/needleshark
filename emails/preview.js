'use strict';
const frame = document.getElementById('email-frame');
const stage = document.getElementById('stage');
const font = document.getElementById('font');
const caption = document.getElementById('review-caption');
let mobile = false;
let resizeObserver;
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
  await frame.contentDocument.fonts.ready;
  resizeObserver?.disconnect();
  resizeObserver = new ResizeObserver(fit);
  resizeObserver.observe(frame.contentDocument.body);
  update();
});
document.querySelectorAll('[data-size]').forEach(button => button.addEventListener('click', () => {
  mobile = button.dataset.size === 'mobile'; update();
}));
font.addEventListener('change', update);
window.addEventListener('resize', fit);
