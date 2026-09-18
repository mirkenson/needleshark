// SHARED_SECRET remains in Script Properties. Run setupBusiness once as owner,
// then update the existing web-app deployment (same URL and access settings).
const RECIPIENT = 'info@neesha.ru';
const HEADERS = ['ID заявки', 'Дата UTC', 'Имя', 'Телефон / email', 'Задача', 'Файл в письме', 'Статус заявки', 'Уведомление'];
const BUSINESS_HEADERS = ['Компания / сфера', 'Направление B2B'];
const BUSINESS_LABELS = {ready: 'Партия готовых изделий', custom: 'Изделие на заказ', materials: 'Ткани и стропы'};

function sheet_() {
  const id = '18ZR-07EYR7zBuULvTD_qVIz2IzlIMDAGk0yHeFtquvU';
  if (!id) throw new Error('SPREADSHEET_ID is missing');
  const book = SpreadsheetApp.openById(id);
  const sheet = book.getSheetByName('Заявки');
  if (!sheet) throw new Error('Worksheet Заявки is missing');
  return sheet;
}

function setup() {
  const sheet = sheet_();
  const current = sheet.getRange(1, 1, 1, HEADERS.length).getValues()[0];
  if (current.some((cell, i) => cell && cell !== HEADERS[i])) throw new Error('Unexpected sheet headers');
  // Preserve the live table's formatting and existing columns.
  MailApp.getRemainingDailyQuota();
  notificationRecipients_();
}

function setupBusiness() {
  setup();
  const lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    businessHeaders_(sheet_());
    attachmentFolder_(); // Requests Drive permission during owner setup.
  } finally { lock.releaseLock(); }
}

function businessHeaders_(sheet) {
  const range = sheet.getRange(1, 9, 1, 2);
  const values = range.getValues()[0];
  if (values.some((value, i) => value && value !== BUSINESS_HEADERS[i])) throw new Error('Unexpected business headers');
  if (values.some(value => !value)) range.setValues([BUSINESS_HEADERS]);
}

function attachmentFolder_() {
  const properties = PropertiesService.getScriptProperties();
  const id = properties.getProperty('ATTACHMENTS_FOLDER_ID');
  const folder = id ? DriveApp.getFolderById(id) : DriveApp.createFolder('Needle Shark — вложения заявок');
  // Never enable access by link or to the public. Explicit collaborators can be
  // added by the owner later; possession of the URL alone does not grant access.
  if (folder.isTrashed() || folder.getSharingAccess() !== DriveApp.Access.PRIVATE) throw new Error('Attachment folder must be private');
  if (!id) properties.setProperty('ATTACHMENTS_FOLDER_ID', folder.getId());
  return folder;
}

function attachment_(lead) {
  if (!lead.attachment) return null;
  const a = lead.attachment;
  if (typeof a.name !== 'string' || !a.name || a.name.length > 160 || /[\x00-\x1f/\\]/.test(a.name) ||
      typeof a.data !== 'string' || !['image/jpeg', 'image/png', 'application/pdf'].includes(a.type)) throw new Error('Invalid attachment');
  const bytes = Utilities.base64Decode(a.data);
  if (!bytes.length || bytes.length > 2 * 1024 * 1024) throw new Error('Invalid attachment');
  const blob = Utilities.newBlob(bytes, a.type, a.name);
  const folder = attachmentFolder_();
  const storedName = lead.id + ' — ' + a.name;
  const matches = folder.getFilesByName(storedName);
  // Script lock + deterministic name make retries reuse the same Drive file,
  // including retries after file creation but before the sheet write succeeds.
  const file = matches.hasNext() ? matches.next() : folder.createFile(blob.copyBlob().setName(storedName));
  if (file.isTrashed() || file.getSharingAccess() !== DriveApp.Access.PRIVATE) throw new Error('Attachment must be private');
  return {blob: blob, url: 'https://drive.google.com/file/d/' + file.getId() + '/view', name: a.name};
}

function text_(value) {
  const text = String(value || '');
  return /^[\s]*[=+\-@]/.test(text) ? "'" + text : text;
}

function notificationRecipients_() {
  const value = PropertiesService.getScriptProperties().getProperty('NOTIFICATION_RECIPIENTS') || RECIPIENT;
  const recipients = value.split(',').map(address => address.trim());
  if (recipients.length > 10 || recipients.some(address => !/^[^\s@,]+@[^\s@,]+\.[^\s@,]+$/.test(address))) throw new Error('Invalid notification recipients');
  return recipients.join(', ');
}

function json_(value) {
  return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    const input = JSON.parse(e.postData.contents);
    const secret = PropertiesService.getScriptProperties().getProperty('SHARED_SECRET');
    if (!secret || secret.length < 32 || input.token !== secret) return json_({ok: false});
    const lead = input.lead;
    if (!lead || !/^[0-9a-f-]{36}$/.test(lead.id) || typeof lead.name !== 'string' || typeof lead.contact !== 'string' || typeof lead.question !== 'string') return json_({ok: false});
    if (lead.name.length > 120 || lead.contact.length > 254 || lead.question.length > 5000) return json_({ok: false});
    if (lead.business_company != null && (typeof lead.business_company !== 'string' || lead.business_company.length > 160)) return json_({ok: false});
    if (lead.business_intent != null && !Object.prototype.hasOwnProperty.call(BUSINESS_LABELS, lead.business_intent)) return json_({ok: false});
    lock.waitLock(15000);
    const sheet = sheet_();
    businessHeaders_(sheet);
    const attachment = attachment_(lead);
    let row = 0;
    if (sheet.getLastRow() > 1) {
      const match = sheet.getRange(2, 1, sheet.getLastRow() - 1, 1).createTextFinder(lead.id).matchEntireCell(true).findNext();
      if (match) row = match.getRow();
    }
    if (!row) {
      sheet.appendRow([lead.id, text_(lead.created_at), text_(lead.name), text_(lead.contact), text_(lead.question), text_(lead.attachment ? lead.attachment.name : ''), 'Новая', 'Ожидает отправки', text_(lead.business_company), text_(BUSINESS_LABELS[lead.business_intent])]);
      row = sheet.getLastRow();
      SpreadsheetApp.flush();
    }
    if (attachment) {
      sheet.getRange(row, 6).setRichTextValue(SpreadsheetApp.newRichTextValue().setText(attachment.name).setLinkUrl(attachment.url).build());
      SpreadsheetApp.flush();
    }
    if (sheet.getRange(row, 8).getValue() !== 'Отправлено') {
      const mail = {
        to: notificationRecipients_(),
        name: 'Needle Shark — заявки',
        subject: 'Заявка Needle Shark · ' + lead.id,
        body: 'Имя: ' + lead.name + '\nКонтакт: ' + lead.contact + '\n\nЗадача:\n' + lead.question + '\n\nID: ' + lead.id + '\nТаблица: ' + sheet.getParent().getUrl()
      };
      if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(lead.contact)) mail.replyTo = lead.contact;
      if (attachment) {
        mail.attachments = [attachment.blob];
        mail.body += '\nФайл: ' + attachment.url;
      }
      MailApp.sendEmail(mail);
      sheet.getRange(row, 8).setValue('Отправлено');
      SpreadsheetApp.flush();
    }
    return json_({ok: true, id: lead.id, attachment_url: attachment ? attachment.url : null});
  } catch (error) {
    // Server retains the request and retries. Do not expose contacts or internals.
    return json_({ok: false});
  } finally {
    if (lock.hasLock()) lock.releaseLock();
  }
}
