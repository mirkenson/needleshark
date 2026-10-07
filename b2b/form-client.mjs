// Retry the same payload with the same UUID after an uncertain response.
export class LeadClient {
  constructor({send = (...args) => fetch(...args), uuid = () => crypto.randomUUID()} = {}) {
    this.send = send;
    this.uuid = uuid;
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
      const payload = {...fields, id: this.pending.id};
      const response = await this.send('/api/leads', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload), signal: AbortSignal.timeout(30000)
      });
      const result = await response.json().catch(() => null);
      if (![200, 202].includes(response.status) || result?.ok !== true || result?.id !== payload.id) {
        if (response.status === 409) this.pending = null;
        throw new Error(response.status === 429 ? 'Слишком много попыток. Попробуйте позже или напишите на info@neesha.ru.' : 'Не удалось сохранить заявку. Проверьте данные и повторите отправку или напишите на info@neesha.ru.');
      }
      const firstConfirmation = !this.saved.has(payload.id);
      this.saved.add(payload.id);
      return {id: payload.id, firstConfirmation};
    } catch (error) {
      if (error instanceof TypeError || ['TimeoutError', 'AbortError'].includes(error.name)) {
        throw new Error('Не удалось получить подтверждение от сервера. Данные остались в форме. Повторите отправку или напишите на info@neesha.ru.');
      }
      throw error;
    } finally {
      this.busy = false;
    }
  }
  newInquiry() { this.pending = null; }
}

export function leadFields({name, email, phone, description, consent, direction, material, path}) {
  return {
    name: name.trim(), email: email.trim(), phone: phone.trim(),
    contact: email.trim() || phone.trim(), question: description.trim(), consent,
    source_path: path, business_intent: material ? 'materials' : 'custom',
    ...(direction ? {business_direction: direction} : {}),
    ...(material ? {business_material: material} : {})
  };
}
