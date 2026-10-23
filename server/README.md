# Server-side leads and email

## Public sales mailbox — 23 October 2026

The website and API error messages now point to sales@neesha.ru. Backend code `eeeb5559fe9a23848832899b57a13853e355dbba` was installed through `--upgrade`, preserving SMTP recipient info@neesha.ru and direct amoCRM delivery. Both pending queues are empty and read-only AMO preflight passes; no new public form submission was sent in this release. Current/previous and validation are recorded in [the report](../docs/verification/20261023-sales-mailbox.json).

The separate REG.ru sales mailbox is connected as corporate mail in amoCRM using mail.hosting.reg.ru, SSL ports 993/465. The pipeline source creates a deal for each new mail thread at stage 89534190 in pipeline 11431098, using the subject as its title. Synthetic mail via REG MX created deal 4744149; its body is verified in CRM, and the reply from sales to info is recorded as outgoing. The owner confirmed reply receipt at REG.ru. All three current users have mail access enabled; separate sign-ins as each manager were not tested. The synthetic 64-byte attachment is intact in IMAP, but download from CRM remains unverified (the visible link ended in #file_not_exists). Do not redirect server notification emails into that source without checking duplicate lead behavior.

After the previous account hostname returned 401, only private AMO_BASE_URL changed to https://needleshark.amocrm.ru (same account). Backup: /opt/needle-shark/backups/amo-domain-20261023T185459Z/leads.env. Preflight and running service environment pass; all other environment keys and unit are preserved. Server SMTP still uses smtp.mail.ru, sending to info@neesha.ru. Its first synthetic sales test was not delivered to REG.ru; the owner reported a nonexistent mailbox error. This old-provider route needs separate reconciliation and must not be represented as a verified REG inbox delivery. Preserve old mailboxes/archives; DNS TXT changes alone do not establish removal of provider-internal routing.

## Direct amoCRM delivery — 23 October 2026

Live code `4120631937287c02997833e7bc945608a0018cc3`, backend `20261023T181849Z-412063193728`. Public synthetic order 31 reached deal 4743091 with verified contact/full text/five UTM values; same-UUID public retry returned 200 without an additional job. SMTP accepted the one info@neesha.ru message; inbox unverified. The first release's custom-field filter was unavailable on this account; standard search plus exact UUID checking fixed delivery of the same queued request. The immediate previous release contains that initial filter and is not a working AMO rollback; pre-integration SMTP code `20261014T082411Z-503911b4435a` is retained. [Checks and limits](../docs/verification/20261023-amocrm.json).

`AMO_ENABLED=1` adds one `lead_amo_deliveries` job to the same PostgreSQL transaction as each new submission and its SMTP jobs. No historical backfill is performed. A separate worker creates a deal with a linked contact in the configured pipeline/stage; intake success still means a database commit. Mail recipients and LOOP are independent. Website/mailbox replacement with sales@neesha.ru is recorded above.

The deal includes the numeric order number, permanent submission UUID, full question and available company/product/direction/material/source context in a textarea, plus the five native UTM fields. Contact email/phone are structured fields; an exact match reuses an existing contact without overwriting it. Multiple matching contacts hold the job for review. Files stay private in PostgreSQL and existing mail delivery; no file bytes, names or public links go to amoCRM. The active website form has no upload.

Keep `AMO_BASE_URL`, `AMO_ACCESS_TOKEN`, `AMO_PIPELINE_ID`, `AMO_STATUS_ID`, `AMO_SUBMISSION_FIELD_ID`, `AMO_ORDER_FIELD_ID`, `AMO_DETAILS_FIELD_ID` and optional `AMO_RESPONSIBLE_ID` only in root-owned 0600 `/etc/needle-shark/leads.env`. Only the account's CRM scope is needed. HTTPS certificates are verified; redirects/proxies and secret/error-body logging are disabled. Rotate the current long-lived token before 23 October 2027. No automatic token refresh is implemented.

Create requests are fenced by the queue lease and persisted `create_started` before POST. `request_id` is only an echoed correlation value, not an amoCRM idempotency key. After a lost acknowledgement, retries search the UUID field; a saved remote ID recovers without another POST. If the result remains uncertain, `amo_create_unconfirmed` stays pending and requires operator review; it is never blindly resent. Backoff is 60 seconds to one hour. Existing monitoring watches SMTP, not this new queue: inspect `SELECT status,count(*),max(attempts) FROM lead_amo_deliveries GROUP BY status;` and `last_error` for pending jobs. Never reset `create_started` until the CRM result is conclusively reconciled.

Deploy committed/pushed code using `bash ops/install-server-mail.sh --amo PRIVATE_AMO_ENV`. The private input must contain only complete AMO settings. Read-only API preflight checks account, stage and field types before service stop; the installer backs up environment/unit/database/pointers, applies the additive migration/grants, validates as the application user and switches backend current atomically. SMTP/LOOP/unit/static releases are preserved. `--upgrade` retains the configured integration. To pause, set AMO_ENABLED=0 in an atomic private environment update and restart: pending jobs remain, but new submissions do not queue for amoCRM. Inspect current/previous before rollback; old code leaves AMO jobs unprocessed, and database dumps must never overwrite new submissions.

Checks: server/ops unit suites; `CRM_TEST_DSN=... python3 server/check_amo_postgres.py` in a disposable schema, alongside `check_delivery_postgres.py`; then a labelled public synthetic submission and verification of database, SMTP acknowledgement and CRM deal/contact/UTM fields. Local tests alone do not establish production delivery.

## Current lead recipient: info@neesha.ru — 19 October 2026

The owner replaced direct delivery to the CRM mailbox with **info@neesha.ru only** in private production `MAIL_RECIPIENTS`. Forwarding to the other mailboxes is configured by the owner at the mailbox provider. Preserve this routing during upgrades; do not restore the old CRM-only or four-recipient list. This supersedes the earlier CRM routing entry below. Server-monitor alerts use their independent, unchanged recipient; LOOP remains disabled.

Verified in the running service environment after restart. Only `MAIL_RECIPIENTS` changed; queues were empty before and after, private environment remains root-owned 0600, and SMTP configuration validation passed without sending. Local/public invalid API probes returned 400 without creating a lead; public HTTPS returned 200. Existing backend/static releases, database rows and unit remain unchanged. No test email/submission was sent: inbox receipt, provider forwarding and post-change CRM duplicate prevention are unverified. [Evidence](../docs/verification/20261019-mail-info-only.json).

## UTM — установлен backend 14 октября 2026

Код `503911b4435a`, релиз `20261014T082411Z-503911b4435a`, установлен через `--upgrade` с миграцией `20261014_lead_utm.sql`. Пять необязательных UTM полей валидируются (строки до 500 символов, без управляющих символов) и сохраняются в orders/lead_submissions в существующей транзакции; отсутствующие значения не добавляются в отпечаток, старые клиенты совместимы. Изменённые метки при повторе UUID дают 409. Письма/LOOP сохраняют прежний формат; поля доступны в БД. Тестовая заявка из браузера подтвердила сохранение и sent четырёх email/одного LOOP. Inbox не проверен. [Отчёт](../docs/verification/20261014-lead-utm.json).


Итог 08.10.2026: код `b39667482c08` опубликован; статика `20261007T224458Z-2496`, backend `20261007T224413Z-b39667482c08`. [Фактические проверки и ограничения](../docs/verification/20261008-b2b-release.json). Публичная отправка тестовой заявки остановлена автоматической проверкой разрешений на юридическом чекбоксе; сохранение/очереди проверены в изолированной PostgreSQL-схеме, новый рабочий lead не создавался. Переобход и обработка QA-событий отчётом не подтверждены.

## Four-field B2B form — 8 October 2026

New JSON fields email, phone, business_direction and business_material are optional for backwards compatibility and have separate nullable orders columns. Primary contact is email when supplied, otherwise phone; both supplied contacts are independently validated and preserved in DB and notifications. Description remains the original user text. Directions and materials are enumerated, source_path excludes query. Existing payload fingerprints remain unchanged for old clients, old files/queues stay intact. New frontend has no upload. Install migration 20261008_b2b_contacts.sql before running new backend, with `ops/install-server-mail.sh --upgrade`; this preserves all configured recipients, SMTP, LOOP and systemd. Queue success still means provider acknowledgment, not proof of inbox placement.

## Isolated catalogue preview — 22 September 2026

`python3 server/preview.py --directory outputs/catalog-preview --port 4176` serves the local catalogue drafts on loopback. Custom directories cannot be combined with `--live-api`; submissions return the existing explicit preview error. Production lead handling/database/delivery code is unchanged. New catalogue pack quantities still use the existing contract: number of packs in question text, total items in `quantity`, variant article/options in `question`. Local synthetic checks do not confirm PostgreSQL or SMTP/LOOP delivery. See `docs/verification/20260922-catalog-drafts.json`.

Database reference: [tables and columns](../docs/DATABASE.md), including customer/order IDs, UUID retry semantics, constraints, indexes, payload fields and attachment retention. `orders.id` is the numeric request number; `orders.customer_id` references `customers.id`; `submission_id` remains the technical UUID used by the API, database links and email Message-ID.

## Numeric notification number — 22 September 2026

Email subject uses `Needle Shark — заявка №<orders.id>`; email body and LOOP use `Номер заявки: <orders.id>`. Claim joins the submission UUID to `orders` and adds the numeric ID only to the in-memory delivery payload. Existing queued payloads work without migration, rewriting fingerprints or re-sending completed jobs. The API and stable UUID-based Message-ID remain unchanged. Customer creation/counters, recipients, attachments and retry semantics are unchanged. PostgreSQL checks deliberately separate order/customer/job numbers and reproduce customer ID gaps from the existing contact upsert. See `docs/PROJECT_CONTEXT.md` for installation status.

Installed from pushed commit `1e94096` as `20260922T094139Z-1e940964f438`; previous `20260922T071148Z-6eedb20ef75a`. Synthetic request 15 from the public homepage was saved with its exact PDF and accepted by SMTP and LOOP in one attempt each. Visible formatting was verified using the installed modules and saved fixture; inbox/channel UI receipt was not independently checked. All seven installed Python files match Git, settings/unit are unchanged, public retries return 200/409 without duplicate jobs. See [verification report](../docs/verification/20260922-notification-order-id.json).

## Text-only LOOP leads — 22 September 2026

Owner scope: new leads only, one supplied incoming webhook at `neesha.loop.ru`, no files and no server-monitor messages. `loop_delivery.py` formats Moscow time, contact, name, full question, available company/direction/product/size/quantity and source page/form. Missing context is labelled as missing; no traffic source or product is invented. Homepage `script.js` now supplies `source_path=/`; catalogue/B2B already provide their own paths. UTM/referrer/CTA tracking is not added.

The same intake transaction inserts one `lead_loop_deliveries` job when `LOOP_LEADS_WEBHOOK_URL` is configured. Its migration is additive and never queues historical leads. A separate worker uses the existing lease/backoff implementation against the separate table, so SMTP delivery, its backlog limit, existing email monitor and attachment cleanup keep their prior behavior. LOOP does not load attachment bytes or publish file links/names. Visitor text is literal Markdown code, with Slack parsing disabled, to avoid visitor-controlled mentions/images/formatting.

The private URL is kept only in root-owned `/etc/needle-shark/leads.env` (0600). HTTPS certificate verification is required; only the owner-approved host/path format is accepted, redirects and environment HTTP proxies are disabled. Only HTTP 200 with `ok` confirms a webhook delivery; other responses/timeouts retry from 60 seconds to one hour. Errors in the queue/logs are neutral codes, not provider bodies or URLs. A lost acknowledgement can still cause a repeated LOOP post with the same request number: incoming webhooks do not provide a verified exactly-once guarantee. API success remains confirmation of database commit, not messenger delivery.

Deploy the committed/pushed backend with `bash ops/install-server-mail.sh --loop PRIVATE_LOOP_ENV`. This mode preserves SMTP settings/recipients and the actual systemd unit. The installer backs up the environment/database/pointers, applies the new table and minimal grants, verifies as the service user, and atomically switches the backend release. Static homepage context is published separately with `ops/deploy.sh`. Inspect both current/previous pointers before rollback; switching to the prior SMTP-only code leaves LOOP jobs stored but unprocessed. Do not restore a database dump over new requests. An empty private webhook setting pauses LOOP and stops creation of new LOOP jobs; existing pending jobs remain.

Read-only health query: `SELECT status,count(*),max(attempts) FROM lead_loop_deliveries GROUP BY status;`. An incoming webhook does not grant access to read channel history, so actual channel display/read notifications require owner/UI confirmation. Existing monitor does not watch this new outbox or send to LOOP; that work was explicitly deferred by the owner.

The visitor question still allows 5000 characters. The obsolete Google limit on question-plus-context was removed, so source metadata cannot shorten the allowed message. Safe variable-length code fences preserve the complete question, including many newlines/backticks, within one LOOP post.

Installed code `6eedb20ef75af950f460879a7ad60ad343e29f28`, backend `20260922T071148Z-6eedb20ef75a`, static `20260922T070621Z-52722`. All three public form types passed synthetic PostgreSQL → LOOP/SMTP delivery, one attempt each; owner confirmed catalogue message receipt/readability. The home PDF stayed intact and private. 26 server and 14 ops tests passed, plus real disposable-schema SQL tests without network sends. Public retry returned 200/409 without duplicate outbox jobs. See `docs/verification/20260922-loop-leads.json` for evidence and limitations. The first deployment interruption and subsequent installer recovery fixes are recorded in `ops/README.md`.

## Google-free delivery — 18 September 2026

Current implementation: `/api/leads` → one PostgreSQL transaction (`customers`, `orders`, `lead_submissions`, `lead_files`, `lead_deliveries`) → background SMTP worker. Google Apps Script, Sheets, Drive and SQLite are not used by this runtime. The legacy Google web-app deployment was also archived in the Google UI after SMTP provider acceptance. Historical setup notes below describe the superseded deployment; historical orders and Drive links are not rewritten. Production installation/results are recorded in `docs/verification/20260918-server-mail.json`.

The form API and confirmation semantics stay unchanged: 202 is returned only after durable database commit, not after email. An identical retry returns 200; changed content under the same UUID returns 409. The permanent fingerprint includes file bytes and consent. Reusing a pre-migration Google UUID returns 409 instead of re-sending historical requests whose full fingerprint is unavailable. Limits remain 10 submissions/hour per keyed IP hash and 500 pending submissions. Files (JPG/PNG/PDF, max 2 MiB) are stored privately as PostgreSQL BYTEA and attached to emails; new requests do not have public or Drive links. SQL remains reachable only through localhost/SSH. Attachment retention is managed separately by `ops/maintenance.py`: eligible delivered files expire after 30 days; requests and deduplication fingerprints remain. Installation status is recorded in `docs/PROJECT_CONTEXT.md`.

Each configured recipient gets a separate job. SMTP success means acceptance by the provider, not confirmed inbox delivery. TLS verification is mandatory; both implicit TLS and STARTTLS require authentication. Stable Message-ID helps correlate possible duplicates, but cannot guarantee exactly-once email if a connection/process fails after provider acceptance and before local status commit. Jobs retry with backoff (60 s to 1 h), including provider refusals, without a retry-count cutoff. Workers claim jobs with a five-minute lease; stale workers cannot finalize reclaimed jobs. Exception text is never saved; only neutral error codes. The later LOOP addition is described above; an external CRM integration remains deferred.

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

## Earlier intake: direct email to Bitrix24 — 19 October 2026

Production keeps the existing website → PostgreSQL/outbox → SMTP pipeline. The approved CRM-connected mailbox is now the **only** `MAIL_RECIPIENTS` address. Addresses and credentials remain in the root-owned private environment, not Git. `LOOP_LEADS_WEBHOOK_URL` was removed: intake creates no LOOP jobs and its worker sends nothing. Historical queue rows remain; server-monitor mail is independent and unchanged. No REST integration or reverse property sync is active.

Bitrix24 mailbox settings now create a new lead for every incoming message from the website's service sender. Simple CRM converts it into a deal. Do not treat email body data as populated customer properties: the single verified test linked the Reply-To email, while the name remained in the message text. Phone-only matching and automatic field/UTM extraction were not verified.

Exactly one public-form test (order 29) was performed. It reached PostgreSQL and the CRM mailbox with complete text and a matching contact email. It exposed two mailbox copies/two CRM deals while four legacy recipients were still configured. The recipient list was then reduced to the one CRM mailbox, with an empty old SMTP queue. No second test was sent; duplicate prevention after this recipient change needs observation on a future genuine inquiry. The test created zero LOOP jobs. See [report](../docs/verification/20261019-bitrix-mail.json).

This is a private configuration change, not a backend/static release. Current backend is still `20261014T082411Z-503911b4435a`. Preserve the existing API fingerprint, success-after-commit behavior and closed attachment storage. Do not restore an old environment blindly: it can reactivate LOOP and the four-recipient fan-out. Built-in Bitrix24 mail requires a commercial CRM tariff after the portal demo ends on 30 October 2026; no paid purchase or Marketplace demo was activated.
