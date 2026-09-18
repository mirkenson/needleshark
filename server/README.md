# Server-side leads and email

## Google-free delivery — 18 September 2026

Current implementation: `/api/leads` → one PostgreSQL transaction (`customers`, `orders`, `lead_submissions`, `lead_files`, `lead_deliveries`) → background SMTP worker. Google Apps Script, Sheets, Drive and SQLite are not used by this runtime. The legacy Google web-app deployment was also archived in the Google UI after SMTP provider acceptance. Historical setup notes below describe the superseded deployment; historical orders and Drive links are not rewritten. Production installation/results are recorded in `docs/verification/20260918-server-mail.json`.

The form API and confirmation semantics stay unchanged: 202 is returned only after durable database commit, not after email. An identical retry returns 200; changed content under the same UUID returns 409. The permanent fingerprint includes file bytes and consent. Reusing a pre-migration Google UUID returns 409 instead of re-sending historical requests whose full fingerprint is unavailable. Limits remain 10 submissions/hour per keyed IP hash and 500 pending submissions. Files (JPG/PNG/PDF, max 2 MiB) are stored privately as PostgreSQL BYTEA and attached to emails; new requests do not have public or Drive links. SQL remains reachable only through localhost/SSH. Attachment retention is managed separately by `ops/maintenance.py`: eligible delivered files expire after 30 days; requests and deduplication fingerprints remain. Installation status is recorded in `docs/PROJECT_CONTEXT.md`.

Each configured recipient gets a separate job. SMTP success means acceptance by the provider, not confirmed inbox delivery. TLS verification is mandatory; both implicit TLS and STARTTLS require authentication. Stable Message-ID helps correlate possible duplicates, but cannot guarantee exactly-once email if a connection/process fails after provider acceptance and before local status commit. Jobs retry with backoff (60 s to 1 h), including provider refusals, without a retry-count cutoff. Workers claim jobs with a five-minute lease; stale workers cannot finalize reclaimed jobs. Exception text is never saved; only neutral error codes. CRM and messenger integration are deliberately deferred.

Settings: `/etc/needle-shark/leads.env`, root-owned 0600; see `leads.env.example`. `MAIL_RECIPIENTS` has no default. During initial verification use only the one recipient explicitly approved by the owner; additional recipients must be enabled separately. Empty SMTP credentials pause sending without stopping intake. `IP_HASH_SECRET` is independent from the removed Google secret. Do not print the environment or SMTP debug logs.

Install committed/pushed code with `bash ops/install-server-mail.sh PRIVATE_SMTP_FILE APPROVED_RECIPIENT`. This backend-only installer does not publish static pages. It stops the previous worker, refuses a switch if the old SQLite queue has pending deliveries, backs up code/environment/unit/database privately, applies the additive SQL migration, grants application access only to new tables/sequence, removes Google settings, checks access as the service user, and switches `/opt/needle-shark/current` atomically. The existing unit retains all hardening; only ExecStart changes to the release symlink. It restarts the service and probes the actual HTTP handler. `previous` preserves the prior backend code; the original unit/environment and database dump are in the printed private backup directory. An automatic install failure restores the prior unit/environment/code pointer. Do not restore the database dump blindly over newer leads. Rolling back specifically to the archived Google-era backend also requires explicitly reactivating its Google deployment; switching code alone is insufficient.

Inspect queue without personal data:

```sql
SELECT status, count(*), max(attempts) FROM lead_deliveries GROUP BY status;
SELECT last_error, count(*) FROM lead_deliveries WHERE status <> 'sent' GROUP BY last_error;
```

Validation: `python3 -m unittest discover -s server -p 'test_*.py'`; `python3 -m unittest discover -s ops -p 'test_*.py'`; `CRM_TEST_DSN=... python3 server/check_delivery_postgres.py`. The integration script uses a disposable schema and never sends mail. Back up PostgreSQL with `pg_dump -Fc`; this now includes attachments and pending jobs. Release snapshots on the same VPS do not provide offsite recovery. Automated external backup remains unconfigured and must not be described as available.

## Historical Google implementation (superseded)

# Leads integration

Notification recipients are configured privately in the Apps Script property `NOTIFICATION_RECIPIENTS` (comma-separated, up to 10 email addresses). Default: info@neesha.ru. The owner authorized four mailboxes on 18 September 2026. Each receives the full task, attachment and its private Drive link; keep additional recipient addresses out of Git. The Google account executing Apps Script sends notifications; no mailbox password is needed. Replies can go directly to the contact email supplied by the visitor.

1. Import a private Google spreadsheet with a `Заявки` worksheet and these headers: ID заявки, Дата UTC, Имя, Телефон / email, Задача, Файл в письме, Статус заявки, Уведомление.
2. Create an Apps Script project using `google/Code.gs`. Keep the existing spreadsheet ID in `sheet_()` and set a random Script Property `SHARED_SECRET` of at least 32 characters. Keep the secret out of Git and frontend files.
3. Run `setupBusiness` as owner. The updated handler additionally requires Drive access to save private attachments; obtain explicit owner approval at the Google permission prompt. Deploy as a Web app, execute as owner, access Anyone. The handler requires the shared secret for all writes. Do not make the spreadsheet public. Use the deployment URL ending in `/exec`, not `/dev`.
4. On VPS, install `leads.py` in `/opt/needle-shark`, create the unprivileged system account `needleleads`, install `needle-leads.service`. Put matching URL and secret in `/etc/needle-shark/leads.env`, mode 0600, root-owned. Systemd reads the environment before dropping privileges.
5. Add an Nginx exact location `/api/leads`: proxy to `http://127.0.0.1:8091`, pass `X-Real-IP $remote_addr`, allow POST only, set `client_max_body_size 3m`, and rate limit submissions. Keep port 8091 inaccessible externally. Nginx overrides any client-supplied X-Real-IP header.
6. Run local tests, then an explicitly labelled test through the VPS. Confirm one row in Google Sheets, notification delivery to the recipient, and retry/idempotency behavior before enabling the public form.
7. Preserve the current shared `dist/script.js` (including its B2B context); set file input accept to `.jpg,.jpeg,.png,.pdf` and show the 2 MB limit. Add a hidden honeypot input named `website`. Remove the unavailable notice. Publish through the existing GitHub/VPS workflow.

Queue behavior: local SQLite commits before acceptance. Failed Google requests retry with backoff, independently of visitor connection. Same ID/content is idempotent; same ID/changed content is rejected. Sheet rows are deduplicated by ID. Email notification is at-least-once: an interruption after sending but before recording success can produce a duplicate with the same ID. Attachments appear in email and are saved in a private Google Drive folder. Sheets keeps a clickable filename; PostgreSQL `orders.attachment_url` stores the same URL after Google acknowledges delivery. Delivered local payloads expire after seven days, pending ones remain for retry. Google quotas may delay delivery; pending queue entries remain on VPS. No lead payloads or credentials belong in logs, Git or the public web root.

Docs: https://developers.google.com/apps-script/guides/web and https://developers.google.com/apps-script/reference/mail/mail-app

## Google resources created 2026-09-09

Spreadsheet: https://docs.google.com/spreadsheets/d/18ZR-07EYR7zBuULvTD_qVIz2IzlIMDAGk0yHeFtquvU/edit

Apps Script: https://script.google.com/home/projects/1J2O8GOLm7KbrU2n9TTs-baMjG23FuaYMhC-uR-Vy2C7MIm61Cr0FH-pR/edit

Deployment: https://script.google.com/macros/s/AKfycby-E311mZp6MKBZLqoRrwv70PSMG1M63UKwf--JBi3Xf9aMZ4OA3CV9E2gajc4cRGYqVA/exec

Setup completed. Browser version embeds the spreadsheet ID and validates existing headers without restyling them. Deployment created; anonymous POST successfully verified. SHARED_SECRET configured by owner. VPS service installed and active; API test delivered with matching Google acknowledgment. Public form activation: 2026-09-09.

## Catalogue request context

The same `/api/leads` endpoint accepts optional `product_slug`, `product_name`, `product_size`, `inquiry_type` (`direct`, `sizing`, `wholesale`), integer `quantity` (1–1000000) and relative `source_path`. Older homepage requests omit these fields and remain compatible. The product size currently uses `Д × Ш × В` in centimetres. These are visitor-submitted enquiry details, not a trusted price or confirmed order.

`lead_context.py` validates context and prepares Google delivery. PostgreSQL `orders` stores each field in its own nullable column. Apply `migrations/20260910_catalog_context.sql` before installing the new backend. No existing data is rewritten. The queue keeps the original comment and context; during Google delivery the fields are added to the existing `Задача` text, so all information also appears in the existing email. Catalogue context still uses the existing task column; B2B fields and private file links use the extension described below. Validation checks the complete Google task against its 5000-character limit before acceptance.

Retry IDs cover the context as well as the comment, both in the queue and in the permanent registry. A changed size or quantity under the same ID is rejected. `ops/install-leads.sh` installs the backend separately from the site, creates a private VPS database dump and code backup, applies the additive migration and restarts the existing service. No Nginx or systemd configuration changes are required. Listing a dump is not a restore test or an external backup policy.

Local preview: `python3 server/preview.py --port 4173` serves static pages with submission disabled. Add `--live-api` explicitly to proxy real submissions to the production API; use clearly labelled test data when verifying. The proxy listens only on loopback, accepts only local Host/Origin values, forwards only `/api/leads` to the fixed production address, and never reads server secrets. Do not deploy this preview server.

## B2B fields and attachment links — 18 September 2026

`business_intent` accepts `ready`, `custom`, or `materials`; `business_company` is optional (160 characters). Both remain structured through validation, SQLite and PostgreSQL, and are included in email task text. `description` keeps the original customer comment. Sheets adds columns I/J: `Компания / сфера`, `Направление B2B`; the original eight columns and formatting remain unchanged.

Apply `migrations/20260918_business_attachments.sql` before installing the backend (`ops/install-leads.sh` does this). First update and authorize the Google handler, run `setupBusiness`, then update the existing web-app deployment without changing its URL/access settings. `ATTACHMENTS_FOLDER_ID` is stored only in Script Properties. Files are private; only the owner or explicitly authorized Google accounts can open them. The code never enables public/link sharing.

The worker validates the returned Drive URL and saves it to PostgreSQL before marking an attachment request delivered. Missing link or CRM write failure retains the queue for retry. Under a script lock, deterministic UUID-prefixed filenames prevent duplicate files on retry; existing rows and sent-mail status are reused. Rich-text links avoid interpreting uploaded filenames as formulas. Files persist independently of seven-day queue cleanup. Older already-purged attachments cannot be restored from a filename alone.

Checks: `python3 -m unittest discover -s server -p 'test_*.py'`; `node google/test_code.cjs`; `CRM_TEST_DSN=... python3 server/check_crm_postgres.py` (requires psycopg2; disposable schema only). The PostgreSQL check was run against the VPS in an isolated schema, not its public order tables. It verifies all three directions, an older form payload, exact company/comment fields, saved links and retries. Google contract tests simulate services and do not prove real Drive/Sheets/mail delivery.

Installed 18 September 2026 from code `a353fc6`, retaining the existing Google web-app URL. A synthetic B2B form submission through the browser/live HTTPS API verified PostgreSQL fields, queue delivery, the test row in Sheets and its rich-text attachment URL; the PDF opens in the private Drive viewer. The owner confirmed receipt on all four configured mailboxes. This does not publish the B2B static page. Test record and verification details are in `docs/verification/20260918-business-revision.json`.

Installed release `20260918T085337Z-9fbb60120094`, code `9fbb601`: public browser form → PostgreSQL/file → SMTP acceptance verified with the single approved recipient. Initial authentication failure was resolved with an owner-supplied application password; the pending request was retried, not recreated. The owner confirmed inbox receipt and that the PDF opens.
