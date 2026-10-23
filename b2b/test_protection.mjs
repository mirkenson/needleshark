import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash, webcrypto} from 'node:crypto';
import {solveProof, browserProof} from './form-protection.mjs';
import {LeadClient, leadFields} from './form-client.mjs';

test('real browser algorithm solves server SHA-256 work with bounded time', async () => {
  const proof = await solveProof('test-challenge', 14, {cryptoApi: webcrypto});
  const digest = createHash('sha256').update(`${proof.challenge}:${proof.nonce}`).digest();
  assert.equal(digest[0], 0); assert.ok(digest[1] < 4);
  await assert.rejects(solveProof('test', 30, {cryptoApi: webcrypto}));
  await assert.rejects(solveProof('test', 14, {cryptoApi: null}));
  let time = 0;
  await assert.rejects(solveProof('test', 14, {cryptoApi: webcrypto, now: () => time += 20000}));
});

test('invalid challenge or server refusal never advances to submission', async () => {
  for (const response of [{status: 429, json: async () => ({})}, {status: 200, json: async () => ({ok: true})},
    {status: 200, json: async () => {throw new Error();}}]) {
    let calls = 0;
    const client = new LeadClient({uuid: () => 'qa-id', send: async () => {calls++; return response;}});
    await assert.rejects(client.submit({name: 'TEST'}));
    assert.equal(calls, 1); assert.equal(client.saved.size, 0); assert.equal(client.busy, false);
  }
});

test('proof completes before intake; retry refreshes proof but retains UUID and payload', async () => {
  const calls = []; let proofCount = 0; let fail = true;
  const client = new LeadClient({uuid: () => 'qa-id', protect: async (send, id) => {
    assert.equal(id, 'qa-id'); calls.push('proof'); return {challenge: 'token-' + ++proofCount, nonce: 42};
  }, send: async (url, options) => {
    const payload = JSON.parse(options.body); calls.push(payload);
    if (fail) {fail = false; throw new TypeError('Network failed');}
    return {status: 200, json: async () => ({ok: true, id: payload.id})};
  }});
  await assert.rejects(client.submit({question: 'TEST'}));
  assert.equal((await client.submit({question: 'TEST'})).firstConfirmation, true);
  assert.equal(calls[1].id, calls[3].id);
  assert.notEqual(calls[1].protection.challenge, calls[3].protection.challenge);
  assert.equal(calls[1].question, calls[3].question);
});

test('filled trap reaches server validation without being discarded', () => {
  const fields = leadFields({name: 'TEST', email: 'qa@example.invalid', phone: '', description: 'TEST', consent: true, path: '/', website: 'bot-filled'});
  assert.equal(fields.website, 'bot-filled');
});
