"""Authenticated TLS SMTP only. No Google services or public attachment links."""
from email.message import EmailMessage
from email.headerregistry import Address
from email.utils import formatdate
import hashlib
import os
import smtplib
import ssl
from lead_context import notification_payload


def mailbox(value):
    if not value or any(ord(c) < 33 for c in value):
        raise ValueError('Invalid mailbox configuration')
    try:
        address = Address(addr_spec=value)
        value.encode('ascii')
    except (ValueError, IndexError, UnicodeError):
        raise ValueError('Invalid mailbox configuration') from None
    if not address.username or not address.domain or '.' not in address.domain or address.addr_spec != value:
        raise ValueError('Invalid mailbox configuration')
    return value


def recipients():
    values = os.environ.get('MAIL_RECIPIENTS', '').split(',')
    result = tuple(dict.fromkeys(mailbox(value.strip()) for value in values))
    if not 1 <= len(result) <= 10:
        raise ValueError('Configure 1 to 10 recipients')
    return result


def smtp_config():
    # Empty credentials suspend only delivery; intake remains available.
    keys = ('SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD', 'MAIL_FROM')
    if not all(os.environ.get(key) for key in keys):
        return None
    sender = mailbox(os.environ['MAIL_FROM'])
    mode = os.environ.get('SMTP_SECURITY', 'ssl')
    if mode not in ('ssl', 'starttls'):
        raise ValueError('SMTP requires TLS')
    port = int(os.environ.get('SMTP_PORT', '465' if mode == 'ssl' else '587'))
    if not 1 <= port <= 65535:
        raise ValueError('Invalid SMTP port')
    return dict(host=os.environ['SMTP_HOST'], user=os.environ['SMTP_USER'],
                password=os.environ['SMTP_PASSWORD'], sender=sender, mode=mode, port=port)


def message(lead, recipient, sender):
    msg = EmailMessage()
    msg['From'] = mailbox(sender)
    msg['To'] = mailbox(recipient)
    msg['Subject'] = 'Needle Shark — заявка №' + str(lead['order_id'])
    msg['Date'] = formatdate(usegmt=True)
    digest = hashlib.sha256(recipient.encode()).hexdigest()[:16]
    msg['Message-ID'] = '<' + lead['id'] + '.' + digest + '@' + sender.split('@')[1] + '>'
    try:
        msg['Reply-To'] = mailbox(lead['contact'])
    except ValueError:
        pass  # Telephone contacts and non-mailbox text belong only in the body.
    msg.set_content('Новая заявка Needle Shark\n\nНомер заявки: ' + str(lead['order_id']) +
                    '\nДата UTC: ' + lead['created_at'] + '\nИмя: ' + lead['name'] +
                    '\nКонтакт: ' + lead['contact'] + '\n\n' + notification_payload(lead)['question'])
    attachment = lead.get('attachment')
    if attachment:
        main, sub = attachment['type'].split('/')
        msg.add_attachment(attachment['content'], maintype=main, subtype=sub, filename=attachment['name'])
    return msg


def send(lead, recipient, config):
    msg = message(lead, recipient, config['sender'])
    context = ssl.create_default_context()
    cls = smtplib.SMTP_SSL if config['mode'] == 'ssl' else smtplib.SMTP
    kwargs = {'host': config['host'], 'port': config['port'], 'timeout': 40}
    if config['mode'] == 'ssl':
        kwargs['context'] = context
    client = cls(**kwargs)
    try:
        if config['mode'] == 'starttls':
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
        client.login(config['user'], config['password'])
        refused = client.send_message(msg, from_addr=config['sender'], to_addrs=[recipient])
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
        # SMTP accepted DATA. QUIT/network shutdown cannot revoke that acknowledgment.
    finally:
        client.close()


def error_code(error):
    # Never store exception messages: SMTP responses can include contacts and credentials.
    if isinstance(error, smtplib.SMTPResponseException):
        return 'smtp_' + str(int(error.smtp_code))
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        return 'smtp_recipient_refused'
    if isinstance(error, ssl.SSLError):
        return 'tls_error'
    if isinstance(error, (TimeoutError, OSError)):
        return 'network_error'
    return 'delivery_error'
