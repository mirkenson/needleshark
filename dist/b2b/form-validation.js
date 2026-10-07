// Browser-independent validation for the proposed four-field form.
export function validateContacts(emailValue, phoneValue) {
  const email = emailValue.trim();
  const phone = phoneValue.trim();
  if (!email && !phone) return {field: 'email', message: 'Укажите почту или телефон, чтобы мы могли связаться с вами.'};
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return {field: 'email', message: 'Проверьте адрес почты, например name@company.ru.'};
  if (phone && (!/^\+?[\d\s()\-]+$/.test(phone) || phone.replace(/\D/g, '').length < 10 || phone.replace(/\D/g, '').length > 15)) {
    return {field: 'phone', message: 'Укажите телефон с кодом страны, например +7 999 123-45-67.'};
  }
  return null;
}
