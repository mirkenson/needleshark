import test from 'node:test';
import assert from 'node:assert/strict';
import {validateContacts} from './form-validation.mjs';

test('accepts either contact and retains the option to provide both', () => {
  assert.equal(validateContacts('test@example.com',''),null);
  assert.equal(validateContacts('','+7 (911) 128-51-32'),null);
  assert.equal(validateContacts(' test@example.com ',' 8 911 128 51 32 '),null);
});
test('requires a contact and validates each supplied field independently', () => {
  assert.equal(validateContacts(' ',' ').field,'email');
  assert.equal(validateContacts('not-email','+79111285132').field,'email');
  assert.equal(validateContacts('test@example.com','123').field,'phone');
  assert.equal(validateContacts('','call +79111285132').field,'phone');
  assert.equal(validateContacts('','+1234567890123456').field,'phone');
  assert.equal(validateContacts('','++79111285132').field,'phone');
});
