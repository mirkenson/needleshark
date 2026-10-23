import {browserProof} from './form-protection.mjs';

// Only campaign labels are retained; never store the full URL or arbitrary query fields.
export const UTM_FIELDS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];
export function captureUtm(search, storage) {
  const params = new URLSearchParams(search);
  const clean = input => Object.fromEntries(UTM_FIELDS.flatMap(key => {
    const value = input?.[key];
    return typeof value === 'string' && value.length <= 500 && !/[\x00-\x1f\x7f]/.test(value) && value.trim()
      ? [[key, value.trim()]] : [];
  }));
  const key = 'needle_utm_v1';
  if (UTM_FIELDS.some(field => params.has(field))) {
    const campaign = clean(Object.fromEntries(UTM_FIELDS.map(field => [field, params.get(field)])));
    try { storage?.setItem(key, JSON.stringify(campaign)); } catch { /* Storage must never block a lead. */ }
    return campaign;
  }
  try { return clean(JSON.parse(storage?.getItem(key) || '{}')); } catch { return {}; }
}

// Retry the same payload with the same UUID after an uncertain response.
export class LeadClient {
  constructor({send = (...args) => fetch(...args), uuid = () => crypto.randomUUID(), protect = browserProof} = {}) {
    this.send = send;
    this.uuid = uuid;
    this.protect = protect;
    this.pending = null;
    this.busy = false;
    this.saved = new Set();
  }
  async submit(fields) {
    if (this.busy) return {busy: true};
    this.busy = true;
    try {
      const signature = JSON.stringify(fields);
      if (this.pending?.signature !== signature) this.pending = {signature, id: this.uuid()};
      const protection = await this.protect(this.send, this.pending.id);
      const payload = {...fields, id: this.pending.id, protection};
      const response = await this.send('/api/leads', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload), signal: AbortSignal.timeout(30000)
      });
      const result = await response.json().catch(() => null);
      if (![200, 202].includes(response.status) || result?.ok !== true || result?.id !== payload.id) {
        if (response.status === 409) this.pending = null;
        throw new Error(response.status === 429 ? 'Слишком много попыток. Попробуйте позже или напишите на sales@neesha.ru.' : response.status === 403 ? 'Не удалось пройти проверку отправки. Данные остались в форме. Обновите страницу или повторите попытку.' : 'Не удалось сохранить заявку. Проверьте данные и повторите отправку или напишите на sales@neesha.ru.');
      }
      const firstConfirmation = !this.saved.has(payload.id);
      this.saved.add(payload.id);
      return {id: payload.id, firstConfirmation};
    } catch (error) {
      if (error instanceof TypeError || ['TimeoutError', 'AbortError'].includes(error.name)) {
        throw new Error('Не удалось получить подтверждение от сервера. Данные остались в форме. Повторите отправку или напишите на sales@neesha.ru.');
      }
      throw error;
    } finally {
      this.busy = false;
    }
  }
  newInquiry() { this.pending = null; }
}

export function leadFields({name, email, phone, description, consent, direction, material, path, utm = {}, website = ''}) {
  return {
    name: name.trim(), email: email.trim(), phone: phone.trim(),
    contact: email.trim() || phone.trim(), question: description.trim(), consent, website,
    ...Object.fromEntries(UTM_FIELDS.filter(key => utm[key]).map(key => [key, utm[key]])),
    source_path: path, business_intent: material ? 'materials' : 'custom',
    ...(direction ? {business_direction: direction} : {}),
    ...(material ? {business_material: material} : {})
  };
}
