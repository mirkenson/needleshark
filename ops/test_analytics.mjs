import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';

const source = readFileSync(new URL('../dist/analytics.js', import.meta.url), 'utf8');

function setup({product = 'chehol-dlya-kolyaski', catalog = true, business = false} = {}) {
  const goals = [], listeners = new Map(), formListeners = new Map(), nodes = new Map();
  const listen = map => (name, callback, options) => map.set(name, {callback, options});
  const emit = (map, name, event = {}) => {
    const handler = map.get(name);
    if (!handler) return;
    if (handler.options?.once) map.delete(name);
    handler.callback(event);
  };
  const form = {
    dataset: business ? {context: 'business'} : {},
    elements: {business_intent: {value: 'custom'}, contact: {value: 'PRIVATE_CONTACT'}},
    checkValidity: () => true, addEventListener: listen(formListeners)
  };
  const document = {
    body: {dataset: {productSlug: product}, classList: {contains: value => catalog && value === 'assortment'}},
    addEventListener: listen(listeners),
    querySelectorAll: selector => selector === 'form' ? [form] : nodes.get(selector) || []
  };
  vm.runInNewContext(source, {
    document, location: {hostname: 'needle-shark.ru', pathname: '/catalog/example/'},
    window: {ym: (counter, method, name, params) => goals.push(JSON.parse(JSON.stringify({counter, method, name, params})))},
    localStorage: {getItem: () => '1'}, URL, setTimeout, clearTimeout
  });
  const element = (matches = [], attrs = {}) => {
    const node = {
      tagName: 'BUTTON', dataset: {}, disabled: false,
      matches: selector => matches.includes(selector),
      closest: selector => selector === '[data-article]' ? null : node,
      getAttribute: () => '', hasAttribute: () => false, ...attrs
    };
    return node;
  };
  return {goals, nodes, element, form,
    emit: (name, event) => emit(listeners, name, event),
    formEmit: name => emit(formListeners, name),
    click: target => emit(listeners, 'click', {target, type: 'click', button: 0})};
}

test('loading analytics sends no artificial interaction or success goals', () => {
  assert.deepEqual(setup().goals, []);
});

test('radio choice is counted once and free-form search text is excluded', () => {
  const s = setup();
  const radio = s.element(['.size-picker input[type=radio]'], {dataset: {option: 'color'}, value: 'PRIVATE_VALUE'});
  radio.closest = () => ({querySelectorAll: () => [{}, radio]});
  s.emit('change', {target: radio});
  s.emit('change', {target: s.element([], {value: 'PRIVATE_SEARCH'})});
  assert.equal(s.goals.length, 1);
  assert.deepEqual(s.goals[0], {counter: 112428810, method: 'reachGoal', name: 'ui_click', params: {
    page: '/catalog/example/', context: 'catalog', product: 'chehol-dlya-kolyaski', element: 'catalog_variant', group: 'color', item: 2
  }});
  assert.ok(!JSON.stringify(s.goals).includes('PRIVATE'));
});

test('gallery and variant table use one existing ui_click goal each', () => {
  const s = setup();
  for (const [selector, element] of [['.gallery-thumb', 'catalog_gallery'], ['[data-select-variant],[data-select-size]', 'catalog_variant_table']]) {
    const node = s.element([selector]); s.nodes.set(selector, [node]); s.click(node);
    assert.equal(s.goals.at(-1).params.element, element);
    assert.equal(s.goals.at(-1).params.item, 1);
  }
  assert.equal(s.goals.length, 2);
});

test('FAQ click records resulting open and closed states without answer text', () => {
  const s = setup(); const details = {open: false};
  const node = s.element(['.faq-list summary'], {tagName: 'SUMMARY', textContent: 'PRIVATE_TEXT'});
  node.closest = selector => selector === 'details' ? details : selector === '[data-article]' ? null : node;
  s.nodes.set('.faq-list summary', [node]);
  s.click(node); details.open = true; s.click(node);
  assert.deepEqual(s.goals.map(g => g.params.state), ['open', 'closed']);
  assert.ok(!JSON.stringify(s.goals).includes('PRIVATE'));
});

test('form attempts never create success; saved event carries only page/product context', () => {
  const s = setup(); s.formEmit('focusin'); s.formEmit('focusin'); s.formEmit('submit');
  assert.deepEqual(s.goals.map(g => g.name), ['form_start', 'form_submit_attempt']);
  s.emit('lead-saved', {detail: {contact: 'PRIVATE_CONTACT', question: 'PRIVATE_QUESTION'}});
  assert.deepEqual(s.goals.map(g => g.name), ['form_start', 'form_submit_attempt', 'lead_submitted']);
  assert.equal(s.goals[2].params.product, 'chehol-dlya-kolyaski');
  assert.ok(!JSON.stringify(s.goals).includes('PRIVATE'));
});

test('business goals retain their existing context and intent', () => {
  const s = setup({product: '', catalog: false, business: true});
  s.formEmit('focusin'); s.formEmit('submit');
  s.emit('lead-saved', {detail: {context: 'business', intent: 'custom'}});
  for (const goal of s.goals) assert.deepEqual(goal.params, {page: '/catalog/example/', context: 'business', intent: 'custom'});
});

test('invalid contact or missing required fields do not count as a valid submit attempt', () => {
  const s = setup(); s.form.checkValidity = () => false;
  s.formEmit('submit');
  assert.deepEqual(s.goals, []);
});

test('home form keeps existing payload and ignores catalog radio handler', () => {
  const s = setup({product: '', catalog: false});
  s.emit('change', {target: s.element(['.size-picker input[type=radio]'])});
  s.formEmit('focusin'); s.emit('lead-saved', {});
  assert.deepEqual(s.goals.map(g => g.name), ['form_start', 'lead_submitted']);
  assert.deepEqual(s.goals.map(g => g.params), [{}, {}]);
});
