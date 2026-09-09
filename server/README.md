# Leads integration

Recipient: info@neesha.ru. The Google account executing Apps Script sends notifications; no mailbox password is needed. Replies can go directly to the contact email supplied by the visitor.

1. Import a private Google spreadsheet with a `Заявки` worksheet and these headers: ID заявки, Дата UTC, Имя, Телефон / email, Задача, Файл в письме, Статус заявки, Уведомление.
2. Create an Apps Script project using `google/Code.gs`. Set Script Properties `SPREADSHEET_ID` and a random `SHARED_SECRET` of at least 32 characters. Keep the secret out of Git and frontend files.
3. Run `setup` and authorize only spreadsheet access and mail sending. Deploy as a Web app, execute as owner, access Anyone. The handler requires the shared secret for all writes. Do not make the spreadsheet public. Use the deployment URL ending in `/exec`, not `/dev`.
4. On VPS, install `leads.py` in `/opt/needle-shark`, create the unprivileged system account `needleleads`, install `needle-leads.service`. Put matching URL and secret in `/etc/needle-shark/leads.env`, mode 0600, root-owned. Systemd reads the environment before dropping privileges.
5. Add an Nginx exact location `/api/leads`: proxy to `http://127.0.0.1:8091`, pass `X-Real-IP $remote_addr`, allow POST only, set `client_max_body_size 3m`, and rate limit submissions. Keep port 8091 inaccessible externally. Nginx overrides any client-supplied X-Real-IP header.
6. Run local tests, then an explicitly labelled test through the VPS. Confirm one row in Google Sheets, notification delivery to the recipient, and retry/idempotency behavior before enabling the public form.
7. Install `server/form.js` as `dist/script.js`; enable submit; set file input accept to `.jpg,.jpeg,.png,.pdf` and show the 2 MB limit. Add a hidden honeypot input named `website`. Remove the unavailable notice. Publish through the existing GitHub/VPS workflow.

Queue behavior: local SQLite commits before acceptance. Failed Google requests retry with backoff, independently of visitor connection. Same ID/content is idempotent; same ID/changed content is rejected. Sheet rows are deduplicated by ID. Email notification is at-least-once: an interruption after sending but before recording success can produce a duplicate with the same ID. Attachments appear in email; only filename is stored in Sheets. Delivered local payloads expire after seven days, pending ones remain for retry. Google quotas may delay delivery; pending queue entries remain on VPS. No lead payloads or credentials belong in logs, Git or the public web root.

Docs: https://developers.google.com/apps-script/guides/web and https://developers.google.com/apps-script/reference/mail/mail-app

## Google resources created 2026-09-09

Spreadsheet: https://docs.google.com/spreadsheets/d/18ZR-07EYR7zBuULvTD_qVIz2IzlIMDAGk0yHeFtquvU/edit

Apps Script: https://script.google.com/home/projects/1J2O8GOLm7KbrU2n9TTs-baMjG23FuaYMhC-uR-Vy2C7MIm61Cr0FH-pR/edit

Deployment: https://script.google.com/macros/s/AKfycby-E311mZp6MKBZLqoRrwv70PSMG1M63UKwf--JBi3Xf9aMZ4OA3CV9E2gajc4cRGYqVA/exec

Setup completed. Browser version embeds the spreadsheet ID and validates existing headers without restyling them. Deployment created; anonymous POST successfully verified. SHARED_SECRET configured by owner. VPS service installed and active; API test delivered with matching Google acknowledgment. Public form activation: 2026-09-09.
