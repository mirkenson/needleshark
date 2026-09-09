// Configure SPREADSHEET_ID and SHARED_SECRET in Script Properties.
// Run setup once, then deploy as a web app executing as owner.
const RECIPIENT = 'info@neesha.ru';
const HEADERS = ['ID заявки', 'Дата UTC', 'Имя', 'Телефон / email', 'Задача', 'Файл в письме', 'Статус заявки', 'Уведомление'];

function sheet_() {
  const id = PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID');
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
  sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS])
    .setBackground('#BE3E3E').setFontColor('#ffffff').setFontWeight('bold');
  sheet.setFrozenRows(1);
  sheet.setColumnWidths(1, 8, 180);
  sheet.setColumnWidth(5, 420);
  sheet.getRange('A:H').setWrap(true).setVerticalAlignment('top');
  // Request the mail scope during owner setup, not upon the first customer request.
  MailApp.getRemainingDailyQuota();
}

function text_(value) {
  const text = String(value || '');
  return /^[\s]*[=+\-@]/.test(text) ? "'" + text : text;
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
    lock.waitLock(15000);
    const sheet = sheet_();
    let row = 0;
    if (sheet.getLastRow() > 1) {
      const match = sheet.getRange(2, 1, sheet.getLastRow() - 1, 1).createTextFinder(lead.id).matchEntireCell(true).findNext();
      if (match) row = match.getRow();
    }
    if (!row) {
      sheet.appendRow([lead.id, text_(lead.created_at), text_(lead.name), text_(lead.contact), text_(lead.question), text_(lead.attachment ? lead.attachment.name : ''), 'Новая', 'Ожидает отправки']);
      row = sheet.getLastRow();
      SpreadsheetApp.flush();
    }
    if (sheet.getRange(row, 8).getValue() !== 'Отправлено') {
      const mail = {
        to: RECIPIENT,
        name: 'Needle Shark — заявки',
        subject: 'Заявка Needle Shark · ' + lead.id,
        body: 'Имя: ' + lead.name + '\nКонтакт: ' + lead.contact + '\n\nЗадача:\n' + lead.question + '\n\nID: ' + lead.id + '\nТаблица: ' + sheet.getParent().getUrl()
      };
      if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(lead.contact)) mail.replyTo = lead.contact;
      if (lead.attachment) {
        const a = lead.attachment;
        const bytes = Utilities.base64Decode(a.data);
        if (bytes.length > 2 * 1024 * 1024 || !['image/jpeg', 'image/png', 'application/pdf'].includes(a.type)) throw new Error('Invalid attachment');
        mail.attachments = [Utilities.newBlob(bytes, a.type, a.name)];
      }
      MailApp.sendEmail(mail);
      sheet.getRange(row, 8).setValue('Отправлено');
      SpreadsheetApp.flush();
    }
    return json_({ok: true, id: lead.id});
  } catch (error) {
    // Server retains the request and retries. Do not expose contacts or internals.
    return json_({ok: false});
  } finally {
    if (lock.hasLock()) lock.releaseLock();
  }
}
