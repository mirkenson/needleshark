import test from 'node:test';
import assert from 'node:assert/strict';
import {LeadClient, leadFields, captureUtm} from './form-client.mjs';
const fields = leadFields({name: ' ТЕСТ ', email: ' qa@example.invalid ', phone: '+7 999 000-00-00', description: ' ТЕСТ релиза ', consent: true, direction: 'chehly', material: 'canvas', path: '/napravleniya/chehly/'});
const ack = (id, status = 202) => ({status, json: async () => ({ok: true, id})});
test('both contacts and description preserved without attachment', () => {
  assert.equal(fields.contact, fields.email);
  assert.equal(fields.phone, '+7 999 000-00-00');
  assert.equal(fields.question, 'ТЕСТ релиза');
  assert.equal(fields.business_direction, 'chehly');
  assert.equal(fields.business_material, 'canvas');
  assert.equal(fields.business_intent, 'materials');
  assert.equal(fields.name, 'ТЕСТ');
  assert.ok(!('attachment' in fields));
});
test('uncertain retry keeps UUID; repeat acknowledgment does not duplicate success', async () => {
  const ids = []; let calls = 0;
  const client = new LeadClient({protect: async () => ({}), uuid: () => 'test-id', send: async (_url, options) => {
    const {id} = JSON.parse(options.body); ids.push(id);
    if (++calls === 1) throw new TypeError('Network failed');
    return ack(id, 200);
  }});
  await assert.rejects(client.submit(fields), /подтверждение/);
  assert.equal((await client.submit(fields)).firstConfirmation, true);
  assert.equal((await client.submit(fields)).firstConfirmation, false);
  assert.deepEqual(ids, ['test-id', 'test-id', 'test-id']);
});
test('double click sends one request', async () => {
  let finish; let calls = 0;
  const client = new LeadClient({protect: async () => ({}), uuid: () => 'test-id', send: () => {calls++; return new Promise(resolve => {finish = resolve;});}});
  const pending = client.submit(fields);
  assert.deepEqual(await client.submit(fields), {busy: true});
  finish(ack('test-id')); await pending;
  assert.equal(calls, 1); assert.equal(client.busy, false);
});
test('errors and missing/mismatched acknowledgments never confirm success', async () => {
  for (const response of [ack('wrong'), ack('test-id', 503), ack('test-id', 429),
    {status: 202, json: async () => ({ok: false, id: 'test-id'})},
    {status: 200, json: async () => {throw new SyntaxError();}}]) {
    const client = new LeadClient({protect: async () => ({}), uuid: () => 'test-id', send: async () => response});
    await assert.rejects(client.submit(fields));
    assert.equal(client.saved.size, 0); assert.equal(client.busy, false);
  }
});
test('changed payload, new inquiry and conflict receive a fresh UUID', async () => {
  let next = 0; const ids = []; let conflict = true;
  const client = new LeadClient({protect: async () => ({}), uuid: () => String(++next), send: async (_url, options) => {
    const {id} = JSON.parse(options.body); ids.push(id);
    if (conflict) {conflict = false; return ack(id, 409);}
    return ack(id);
  }});
  await assert.rejects(client.submit(fields));
  await client.submit(fields);
  await client.submit({...fields, question: 'Changed'});
  client.newInquiry(); await client.submit({...fields, question: 'Changed'});
  assert.deepEqual(ids, ['1', '2', '3', '4']);
});
test('default browser fetch is called without the client as its receiver', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async function (_url, options) {
      assert.ok(this === undefined || this === globalThis, 'Native browser fetch rejects an arbitrary receiver');
      return ack(JSON.parse(options.body).id);
    };
    const client = new LeadClient({protect: async () => ({}), uuid: () => 'test-id'});
    assert.equal((await client.submit(fields)).firstConfirmation, true);
  } finally { globalThis.fetch = original; }
});

test('campaign survives internal navigation and is replaced as a whole', () => {
  const data = new Map();
  const storage = {getItem: key => data.get(key), setItem: (key, value) => data.set(key, value)};
  const first = captureUtm('?utm_source=vk&utm_medium=cpc&utm_campaign=test&utm_content=one&utm_term=чехлы&email=private', storage);
  assert.deepEqual(first, {utm_source: 'vk', utm_medium: 'cpc', utm_campaign: 'test', utm_content: 'one', utm_term: 'чехлы'});
  assert.deepEqual(captureUtm('', storage), first);
  assert.deepEqual(captureUtm('?utm_source=other', storage), {utm_source: 'other'});
  assert.deepEqual(captureUtm('', storage), {utm_source: 'other'});
  assert.deepEqual(captureUtm('?utm_source=', storage), {});
  assert.deepEqual(captureUtm('', storage), {});
  assert.deepEqual(captureUtm('', {getItem: () => null}), {});
});
test('bad campaign values/storage do not prevent submission; no arbitrary URL data', () => {
  const storage = {getItem() {throw new Error();}, setItem() {throw new Error();}};
  assert.deepEqual(captureUtm('?utm_source=vk&contact=private', storage), {utm_source: 'vk'});
  assert.deepEqual(captureUtm('', storage), {});
  assert.deepEqual(captureUtm('?utm_source=%00bad&utm_campaign=' + 'x'.repeat(501)), {});
  assert.deepEqual(captureUtm('?utm_source=first&utm_source=second'), {utm_source: 'first'});
  assert.deepEqual(captureUtm('', {getItem: () => '{broken'}), {});
  assert.deepEqual(captureUtm('', {getItem: () => '{"utm_source":42,"email":"private"}'}), {});
  const payload = leadFields({name: 'TEST', email: 'qa@example.invalid', phone: '', description: 'TEST', consent: true, path: '/', utm: {utm_source: 'vk', email: 'private'}});
  assert.equal(payload.utm_source, 'vk');
  assert.equal(payload.email, 'qa@example.invalid');
});
