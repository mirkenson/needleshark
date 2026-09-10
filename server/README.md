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

## Catalogue request context

The same `/api/leads` endpoint accepts optional `product_slug`, `product_name`, `product_size`, `inquiry_type` (`direct`, `sizing`, `wholesale`), integer `quantity` (1–1000000) and relative `source_path`. Older homepage requests omit these fields and remain compatible. The product size currently uses `Д × Ш × В` in centimetres. These are visitor-submitted enquiry details, not a trusted price or confirmed order.

`lead_context.py` validates context and prepares Google delivery. PostgreSQL `orders` stores each field in its own nullable column. Apply `migrations/20260910_catalog_context.sql` before installing the new backend. No existing data is rewritten. The queue keeps the original comment and context; during Google delivery the fields are added to the existing `Задача` text, so all information also appears in the existing email. Apps Script and its eight-column sheet need no change. Validation checks the complete Google task against its 5000-character limit before acceptance.

Retry IDs cover the context as well as the comment, both in the queue and in the permanent registry. A changed size or quantity under the same ID is rejected. `ops/install-leads.sh` installs the backend separately from the site, creates a private VPS database dump and code backup, applies the additive migration and restarts the existing service. No Nginx or systemd configuration changes are required. Listing a dump is not a restore test or an external backup policy.

Local preview: `python3 server/preview.py --port 4173` serves static pages with submission disabled. Add `--live-api` explicitly to proxy real submissions to the production API; use clearly labelled test data when verifying. The proxy listens only on loopback, accepts only local Host/Origin values, forwards only `/api/leads` to the fixed production address, and never reads server secrets. Do not deploy this preview server.
