# Needle Shark VPS


## CRM fields and unified LOOP — 28 October 2026

Backend e915cac49137 installed with --upgrade; current 20261028T141053Z-e915cac49137,
previous 20261024T175828Z-5d8ba9baa122. Static pointers and systemd/Nginx are unchanged.
The installer must execute 20261028_amo_fields_loop.sql and grant its queue/cursor
privileges before app-user validation. The first attempt omitted execution and was
automatically rolled back; test_amo_migration_install.py now covers the complete
uploaded/applied migration set and ordering. Private activation backup:
/opt/needle-shark/backups/amo-fields-loop-activation-20261028/leads.env.
Preserve the four activation keys on ordinary upgrades; legacy LOOP_LEADS_WEBHOOK_URL
remains absent. One form test reached CRM and LOOP; owner confirmed @daniil. SMTP
535 is deferred by the owner: do not change mail or its amoCRM integration.
[Verification and limits](../docs/verification/20261028-amo-fields-loop.json).

## Robot case release — 26 October 2026

Pushed public code 74c9c85 deployed with ops/deploy.sh --from-github: current 20261026T084240Z-67601, previous 20261026T082308Z-64470. 1273 files verified, 21 downloaded/1252 reused. Backend, Nginx and systemd unchanged. Fresh pointers and six active services/timers confirmed; inspect pointers again before rollback.

254 public files match, six GET redirects preserve query, three expected 404s. The cycle passed 147 tests (47 unchanged backend tests before the final analytics fix), build/prepare/check and repeatability. Local responsive/menu checks cover 20 pages at five widths; public desktop checks cover 15 pages, the full public sweep remains incomplete. Synthetic order 34 persisted once; SMTP and amoCRM accepted it, UTM/ClientID read-back matches. Google accepted the case; Yandex accepted case/listing/homepage. Report processing explicitly deferred by the owner. [Evidence](../docs/verification/20261026-robot-case-publication.json). Prototype sections below are historical.

## Правки кейса — только прототип, 26 октября 2026

Код `9cd49e6` переносит черновик из `/blog/.../` в `/cases/.../`, добавляет общую форму главной и повторно использует amo. Публичный dist, сервер, Nginx и backend не менялись. Таблица адресов — `blog/case-page-registry.json`; 301 старого адреса действует только в локальном preview. Перед выпуском согласовать материал, заполнить дату и основной реестр, выполнить штатные сборку/проверки/деплой и проверить новую позицию формы с сохранением/доставкой. [Проверки прототипа](../docs/verification/20261026-robot-case-revision.json).

## Direction content release — 24 October 2026

Pushed **3d952cbc91595ce0dc8048c245e1abda2ee8e6d0** deployed with `ops/deploy.sh --from-github`: static current **20261024T190051Z-94510**, previous **20261024T180418Z-87524**. All 1261 files verified before atomic switch; seven downloaded/1254 reused. Only five direction HTML files, one word in the homepage and sitemap changed. CSS/JS/assets/forms and the live ClientID implementation are preserved; no backend, Nginx or systemd edits. Recheck actual pointers before any rollback.

Fresh public checks: 18 HTML + 223 resources + robots/sitemap match, eight GET 301 redirects preserve query, unknown URL returns 404, six services/timers active. 41 Python and 17 JS tests passed; build repeated byte-identically. Five directions × five widths passed locally and publicly; the changed homepage card also checked at five widths. Explicit direction `updated` supplies sitemap lastmod, never build time. [Verification](../docs/verification/20261024-directions-content.json).

## Structured metadata release — 24 October 2026

Pushed code **4405fb59a3b0cf4126d66d5182f92dba78cd3094** deployed with `ops/deploy.sh --from-github`: static current **20261024T180418Z-87524**, previous **20261024T175952Z-85550**. The already live ClientID code 5d8ba9b was merged before deployment; all 18 body regions and JS/CSS are byte-identical to that release. No backend install or server configuration changes. All 1261 files verified before switch, 19 downloaded/1242 reused. Recheck actual pointers before rollback.

Public HTTPS: 18 HTML, 223 resources, robots/sitemap match the release; eight GET 301s preserve query, an unknown URL returns 404. Six services/timers active. 126 tests passed, rebuild is byte-identical; 18 pages × five widths passed both locally and publicly. Service/catalog/article schema passed schema.org. Search console reads and new recrawl requests were unavailable because Computer Use stopped on the current Chrome URL; no workaround was attempted. [Verification](../docs/verification/20261024-seo-structured-metadata.json).

`ops/page-registry.json` is the reviewed independent expected contract. Update it deliberately when approving a new route or changing its metadata; do not regenerate it automatically from rendered HTML. `prepare-public.py` and the B2B publish renderer reject missing/extra HTML. `check-site.py` invokes `seo_checks.py` for head-aware canonical, OG/Twitter, entity URLs, visible images/dates/item order and required schema checks; sitemap is compared with the registry. New regressions: `python3 -m unittest discover -s ops -p 'test_seo.py'`. Run the existing build/prepare/check sequence as usual.

## ClientID form release — 24 October 2026

Pushed code 5d8ba9baa12271d9235580b3fec5cc7dd0df2bc0 installed with --upgrade, then ops/deploy.sh --from-github. Backend current 20261024T175828Z-5d8ba9baa122 / previous 20261023T194915Z-ab8b6b9b5c42; static current 20261024T175952Z-85550 / previous 20261024T173415Z-77623. Backup /opt/needle-shark/backups/20261024T175828Z-5d8ba9baa122 includes database/environment/unit and old pointers. The installer adds nullable orders.ym_client_id before switching; environment and unit remain byte-identical, Nginx untouched. All 1261 static files verified before switch; 241 public files and installed backend files match, five services/timers active.

Synthetic order 33 / amoCRM 4787837 verified real SDK identity, persistent snapshot, UTM and a lost-ack retry with one remote deal. Both queues have no pending jobs, SMTP and AMO accepted the test once; inbox/CRM report processing unverified. Inspect pointers again before rollback; keep the column and newer leads, never restore a dump over them. Old clients remain accepted. [Verification](../docs/verification/20261024-form-clientid.json).

## SEO first fixes — 24 October 2026

Pushed **946b54a081d34034bbc0b96196e46fddfca9ba97** deployed through ops/deploy.sh --from-github: current **20261024T173415Z-77623**, previous **20261024T164617Z-69228**. All 1261 files verified before switch; 22 downloaded and 1239 reused. Public HTTPS: 18 HTML, 223 resources and robots/sitemap match; eight redirects preserve query, unknown URL returns 404; nginx, needle-leads, postgresql and needle-cleanup/monitor/metrika timers are active. Backend, Nginx, systemd and lead data unchanged. Inspect current/previous again before rollback. [Verification](../docs/verification/20261024-seo-first-fixes.json).

check-site now rejects missing/duplicate/misplaced homepage ownership markers and local BlogPosting citations to retired pages or missing anchors. Relevant tests: 40 Python + 26 JavaScript pass; final repeated build is byte-identical. Browser regression covers every public page at five widths. Ozon availability and analytics report processing are not confirmed.

## Covers hero image — 24 October 2026

Pushed commit e1865f7f2096fb33e2efea4c49b9f0ae03d1d27e deployed through ops/deploy.sh --from-github. Current 20261024T164617Z-69228, previous 20261024T163118Z-66091. All 1261 files verified before switching; 4 downloaded, 1257 reused. Public HTTPS: 240 files match, two redirects preserve query, five services/timers active. Backend, Nginx, systemd and lead data unchanged. Inspect pointers again before rollback. [Verification](../docs/verification/20261024-covers-composite.json).

## amoCRM site chat — 24 October 2026

Pushed code `9fa0093f398648981fdb27986430b076de6d215e` deployed through `ops/deploy.sh --from-github`. Static current `20261024T163118Z-66091`, previous `20261024T162433Z-65339` (first working chat release). The retained pre-chat release is `20261023T195007Z-48372`. All 1258 files verified before switching; 22 downloaded, 1236 reused. Public HTTPS: 231 files including 18 HTML/robots/sitemap match dist, two redirects preserve query, five services/timers active. Inspect pointers again before rollback. Backend, environment, Nginx, systemd and database were not changed.

The official widget connects visitors directly to amoCRM, independently of the existing lead API/database/mail queues. Widget 451441, source «Чат сайта Needle Shark», trusted domain only `https://needle-shark.ru`. Repeated build is byte-identical; isolated preview excludes the widget. One synthetic conversation A100 / lead 4780059 proves website-to-CRM and CRM-to-website delivery; the final version sent another message into the same conversation. Manager device notifications and attachments were not tested. [Verification and limitations](../docs/verification/20261024-amocrm-site-chat.json).

## Submission protection rollout — 23 October 2026

Installed code `ab8b6b9b5c4281cfb964f310d5300660aadf97be`: backend current `20261023T194915Z-ab8b6b9b5c42`, previous `20261023T184229Z-eeeb5559fe9a`; static current `20261023T195007Z-48372`, previous `20261023T184305Z-41970`. Required flag verified in the running process after activation; private backup `/opt/needle-shark/backups/protection-20261023T195101Z/leads.env`. 14 installed backend files and 235 public files match the checked release; five services/timers active, SMTP/AMO queues empty. [Full report](../docs/verification/20261023-form-antispam.json).

The backend installer now includes `antispam.py`; existing Nginx POST-only route/rate limits, systemd unit, SMTP recipients and amoCRM settings stay in place. Deploy pushed backend using `--upgrade`, publish matching static through `ops/deploy.sh`, then atomically enable `LEAD_PROTECTION_REQUIRED=1` in the backed-up private environment and restart the existing service. Before activation, missing/0 keeps old clients compatible; supplied proofs are still checked. Verify the actual running flag, missing/tampered proof rejection without database writes, and one labelled successful synthetic request through PostgreSQL and configured delivery queues. Preserve current/previous and all live data on rollback. See server README and the dated verification report for limitations.

## Public sales contact — 23 October 2026

Pushed code `eeeb5559fe9a23848832899b57a13853e355dbba` installed with backend `--upgrade`, then `ops/deploy.sh --from-github`. Backend current `20261023T184229Z-eeeb5559fe9a`, previous `20261023T181849Z-412063193728`; static current `20261023T184305Z-41970`, previous `20261016T070519Z-75714`. All 1256 static files verified before switch (20 downloaded, 1236 reused); 13 installed backend files and 80 public files verified afterward. Five services/timers active; SMTP/AMO queues have no pending jobs. The deploy preserved environment and service unit. After the old account hostname returned 401, only `AMO_BASE_URL` changed to `https://needleshark.amocrm.ru`; backup `/opt/needle-shark/backups/amo-domain-20261023T185459Z/leads.env`. API preflight and the running process confirm the new base. Unit and Nginx unchanged. The backend previous now contains the verified amoCRM implementation. Inspect pointers before rollback; never restore the database over newer submissions or restore the obsolete AMO hostname.

Public email is sales@neesha.ru. The corporate mailbox is connected to amoCRM through REG.ru IMAP/SMTP with SSL. Incoming test via REG MX created deal 4744149; the reply from sales was sent inside CRM and the owner confirmed receipt on info at REG.ru. All three current users have mail access enabled. Preserve SMTP recipient info@neesha.ru and the direct AMO queue to avoid feeding form notifications into the sales deal source. Existing server SMTP remains smtp.mail.ru; its first test to sales failed with a nonexistent mailbox report, and the old provider route remains a separate diagnostic item. [Report](../docs/verification/20261023-sales-mailbox.json).

Authoritative DNS is on ns1.reg.ru/ns2.reg.ru. Public MX mxs1.reg.ru/mxs2.reg.ru correctly uses REG enhanced spam protection, whose transport is mx1.hosting.reg.ru/mx2.hosting.reg.ru. The ISPmanager DNS zone is not authoritative; do not copy its hosting A record over the website VPS address. SPF is a single record, DKIM selector dkim matches hosting, DMARC is p=none. No DNS changes were made during this audit. Mail.ru internal routing is suspected from the owner-reported legacy inbox delivery and test failure, not confirmed from its admin panel: browser access to that URL was blocked. Keep old mail data until migration/retention is explicitly resolved.

## Direct amoCRM backend — 23 October 2026

Published pushed code `4120631937287c02997833e7bc945608a0018cc3`: backend current `20261023T181849Z-412063193728`, previous `20261023T181321Z-376d4ec0c75c`; static stays `20261016T070519Z-75714` / `20261014T082454Z-53317`. All 13 backend files match Git, 10 public files match dist, five services/timers are active. Order 31 reached CRM deal 4743091 and SMTP. [Verification](../docs/verification/20261023-amocrm.json). The previous backend contains the first, incompatible CRM search filter; use retained `20261014T082411Z-503911b4435a` only for a deliberate SMTP-only rollback, after inspecting pointers/settings and preserving AMO pending jobs. Backups under both new release names retain private environment/unit/database snapshots. One SSH timeout occurred before remote changes; the retry installed successfully.

Use `bash ops/install-server-mail.sh --amo PRIVATE_AMO_ENV` for the approved direct server integration. It requires committed/pushed code, validates CRM account/stage/fields before stopping the handler, adds `20261023_amo_delivery.sql` and its minimal grants, merges only AMO settings and preserves mail/LOOP configuration, the actual service unit and static current/previous. The existing backup and atomic backend switch/rollback apply; no Nginx change or static `ops/deploy.sh` run is needed. Schema additions are retained on rollback; never restore a database dump over newer requests.

Runtime/configuration, queue reconciliation and token renewal are described in [server/README.md](../server/README.md). Scope is new submissions only, CRM account data without file access. Existing SMTP monitoring does not cover this queue. Inspect its pending count/errors during maintenance; ambiguous creation outcomes require CRM reconciliation before any manual reset. The later sales@neesha.ru website/mailbox change is recorded above.

## Lead mail routed through info@neesha.ru — 19 October 2026

The only production lead recipient is now `info@neesha.ru`; the owner handles onward forwarding at the mailbox provider. An atomic update changed only private `MAIL_RECIPIENTS`, with the lead service stopped and the empty queue rechecked before the update. The running process was verified after restart. All other environment settings, monitor configuration, unit and backend/static current/previous pointers are unchanged; no deployment script or source release was needed.

Root-only backup: `/opt/needle-shark/backups/info-only-20261019T075954Z/leads.env`. It contains the superseded CRM recipient: do not restore it wholesale or re-enable the older four-recipient fan-out. Preserve the current routing in future upgrades. HTTPS 200, local/public invalid API 400, five active services/timers and zero pending SMTP jobs were checked. No test emails/submissions or historical replay; actual forwarding/inbox delivery remains unverified. [Report](../docs/verification/20261019-mail-info-only.json).

## Контактный телефон — выпуск 16 октября 2026

Код `0918b1a7d69f6d6685d49c7be100c98bf9b22883` отправлен до `ops/deploy.sh --from-github`. Current `20261016T070519Z-75714`, previous `20261014T082454Z-53317`: 18 HTML скачаны, 1238 файлов использованы повторно, все 1256 проверены до переключения. Backend `20261014T082411Z-503911b4435a` и конфигурация прежние, шесть служб/таймеров active. [Проверки и прежняя проблема мобильного меню](../docs/verification/20261016-contact-phone.json).

## UTM — выпуск 14 октября 2026

Проверенный коммит `503911b4435a` отправлен до установки. `ops/install-server-mail.sh --upgrade` устанавливает добавляющую миграцию `20261014_lead_utm.sql`, затем `ops/deploy.sh --from-github` публикует статику. Current: backend `20261014T082411Z-503911b4435a`, static `20261014T082454Z-53317`; previous: backend `20261007T224413Z-b39667482c08`, static `20261008T070613Z-7544`. Env/unit сохранены побайтово, Nginx не менялся. При откате старый backend игнорирует UTM; колонки/новые заявки не удалять и dump поверх БД не восстанавливать. [Проверки и ограничения](../docs/verification/20261014-lead-utm.json).


## Ткани без внешних ссылок — 08.10.2026

Опубликован код `4288670391c27f1ab52f602e1b709ce467706627` через `ops/deploy.sh --from-github`: current `20261008T070613Z-7544`, previous `20261007T224458Z-2496`. Проверены все 1256 файлов перед переключением, скачаны только семь HTML. HTTPS: 238 совпадений SHA-256; все шесть служб active. Backend/Nginx/systemd прежние. Владелец подтвердил, что самостоятельно проверил форму и всё работает; новых заявок агент не отправлял. [Отчёт](../docs/verification/20261008-material-links.json).

Итог 08.10.2026: код `b39667482c08` опубликован; статика `20261007T224458Z-2496`, backend `20261007T224413Z-b39667482c08`. [Фактические проверки и ограничения](../docs/verification/20261008-b2b-release.json). Публичная отправка тестовой заявки остановлена автоматической проверкой разрешений на юридическом чекбоксе; сохранение/очереди проверены в изолированной PostgreSQL-схеме, новый рабочий lead не создавался. Переобход и обработка QA-событий отчётом не подтверждены.

## B2B release — 8 October 2026

Approved B2B code is built with `python3 b2b/render.py --publish` (18 indexable HTML pages), then prepare/check-site. Existing blog/catalog/business CLI entry points retain this build; legacy renderer functions and product sources remain available for restoration. Deploy committed/pushed backend first using `bash ops/install-server-mail.sh --upgrade`, preserving existing environment and systemd. Then deploy static through the existing `ops/deploy.sh --from-github` and install the narrowly scoped product redirects with `bash ops/install-b2b-redirects.sh`. The latter backs up actual Nginx config, preserves all aliases including neesha.ru, tests and reloads with rollback on failure. See [B2B instructions](../b2b/README.md) for backup/rollback. Final live evidence and the blocked submission check are recorded in the release report above.

## B2B prototype — 8 October 2026, not deployed

`python3 b2b/render.py` builds an isolated review into `outputs/b2b-preview`; serve it with `python3 b2b/preview.py --port 4190`. No changes to production `dist/`, backend or VPS. Never deploy this preview: indexing, analytics and API submission are deliberately disabled. The local 301 product redirects are a review of the future migration, not an installed Nginx change. See [b2b/README.md](../b2b/README.md) and [verification](../docs/verification/20261008-b2b-prototype.json).

## B2B search-content release — 24 September 2026

Published pushed commit `477a0d43729585b0e283405d705ab7a2018fd89f` with `ops/deploy.sh --from-github`: current `20260924T073408Z-14797`, previous `20260924T064707Z-11896`. One HTML downloaded, 1265 files reused, all 1266 verified before the switch. Public 39 HTML files and 51 assets match; two aliases preserve query; Nginx, leads, PostgreSQL and cleanup/monitor/Metrika timers are active. No backend, Nginx or systemd change. [Verification](../docs/verification/20260924-business-seo.json).

## Homepage latest articles — 24 September 2026

Published `9d5d6032ad4989a4a32d5e6e0e112277f38c3a30` through `ops/deploy.sh --from-github`: current `20260924T064707Z-11896`, previous `20260923T190839Z-8792`. All 1266 files verified before switching; two changed assets downloaded and 1264 reused. Public homepage and 36 other files match the release. Five services/timers active; backend/configuration unchanged. [Verification](../docs/verification/20260924-home-latest-articles.json).

## B2B heading release — 23 September 2026

Static current `20260923T190839Z-8792`, previous `20260923T181352Z-5967`; pushed code `bd8b972e4b3edebfe0a568160c00bf403c13faa6`. Five whitespace fixes, deployed using the existing GitHub transport with all 1266 files verified before switch. Public HTML matches; 49 resources and five services/timers pass. Backend/configuration unchanged. [Report](../docs/verification/20260923-b2b-heading-preflight.json). Older current/previous entries below are historical.

## UX and blog publication — 23 September 2026

Production static release `20260923T181352Z-5967` comes from pushed commit `ea4b9005a9e3711ffc7f6bea436d1f13ab5f1860` on `codex/ux-blog-release`, using `ops/deploy.sh --from-github`. All 1266 files verified before switching current; 54 public files matched SHA-256, 117 resource URLs returned 200, five alias redirects preserved path/query. Five configured services/timers remain active. Backend/configuration/schema unchanged.

Previous static release is `20260922T181556Z-89524`, also retained through `/var/www/needle-shark/rollback-before-ux-blog-20260923`. Do not edit or delete either release. Before any rollback, read current/previous/this safety link again; use the existing atomic rollback procedure below, never restore an old database dump over newer leads. [Release verification](../docs/verification/20260923-ux-blog-publication.json). Sections below describe earlier preparation/releases.

## Local UX prototype — 23 September 2026

Branch `codex/ux-prototype` is a review build, not a VPS release. Its isolated copy is `outputs/ux-prototype-20260923/` in the main project. Restart with `python3 server/preview.py --directory outputs/ux-prototype-20260923 --port 4183`; do not pass `--live-api`. Preview HTML has noindex and no analytics SDK. Do not deploy this preview directory. See [scope and verification](../docs/UX_PROTOTYPE_20260923.md).

## Catalogue publication — 22 September 2026

Published all 26 products / 33 HTML pages from pushed commit `fee19198d352509d9eed44914b205ac07295e2cf` through `ops/deploy.sh --from-github`. Static current: `20260922T181556Z-89524`; previous: `20260922T070621Z-52722`. All 1259 release files verified before atomic switch; 48 public files matched by SHA-256, 270 resources returned 200, services/timers active. Backend `20260922T094139Z-1e940964f438` and configuration unchanged. Two slow, incomplete transfer directories remain from aborted attempts before current switched. See [publication report](../docs/verification/20260922-catalog-publication.json). Earlier draft sections below are historical.

## Catalogue drafts — 22 September 2026

`catalog/render.py --preview` writes the complete local review to `outputs/catalog-preview`; never deploy that directory. Normal rendering and `prepare-public.py` include only catalog entries with `status: published` or the pre-existing default status. New original/responsive images stay in the source tree for reproducible rendering. `optimize-images.py` reuses unchanged manifest entries when original SHA-256 and generated file sizes match; do not rerun full recompression unnecessarily. No VPS release/configuration was changed for this draft preparation. Audit: `docs/catalog-ozon-20260922.md`.

- Host: 194.87.99.98, Ubuntu 24.04.
- Primary domain: needle-shark.ru; www.needle-shark.ru, needleshark.ru and www.needleshark.ru redirect to it.
- Nginx config: /etc/nginx/sites-available/needle-shark.
- Public root: /var/www/needle-shark/current (symlink to a release).
- Deployment account: needledeploy (no sudo).
- SSH key stays outside this repo: ~/.ssh/needle_shark_ed25519.
- Publish from the local workspace: `bash ops/deploy.sh`.
- If the computer-to-VPS upload is slow, use `bash ops/deploy.sh --from-github`: the VPS reuses matching files from current and downloads missing `dist/` files from the exact pushed public GitHub commit over verified HTTPS, with four workers and per-file SHA-256. No repository credential, build, or new dependency is installed on the VPS. Both transfer modes require committed/pushed assets and verify every local SHA-256 on the remote release before switching `current`; a failed transfer/check leaves the current site untouched. Run `python3 -m unittest discover -s ops -p 'test_deploy.py'` and `python3 -m unittest discover -s ops -p 'test_static_fetch.py'` for isolated transport/failure checks. The archive endpoint can be much slower than individual raw files; the final implementation uses raw files.
- Each publish uploads a fresh release, then atomically switches current; previous points to the last release.
- Firewall allows TCP 22, 80, 443. Existing root access preserved for administration.
- The site serves HTTPS with HTTP redirects. Indexing is explicitly authorized by the owner on 11 September 2026. Form submissions use needle-leads on localhost:8091 via /api/leads.
- DNS A records for @ and www point to 194.87.99.98. Let's Encrypt covers all four names; certbot.timer handles renewal. Primary URL: https://needle-shark.ru/.
- GitHub source backup: https://github.com/mirkenson/needleshark. Save and push agreed changes before deploying the VPS. Existing .openai/hosting.json belongs to the separate Sites preview; VPS deployment does not use it.

Do not commit private keys, credentials or user-submitted data.

## Local Obsidian knowledge mirror

After updating project context and committing the final documentation, run `python3 ops/sync-obsidian.py` and `python3 ops/sync-obsidian.py --check`. This copies the committed Git tree and generates readable indexes/reports in the owner's local Needle Shark vault project. Existing manual edits cause a conflict instead of an overwrite; personal project notes remain separate. No VPS deployment or background schedule is involved. See [docs/OBSIDIAN.md](../docs/OBSIDIAN.md) for paths, scope and conflict handling.

Before a static release, run `python3 blog/render.py`, `python3 catalog/render.py`, `python3 business/render.py --publish`, then `python3 ops/prepare-public.py`. The last command finalizes external-anchor UTM parameters and canonical URLs and regenerates robots.txt/sitemap.xml from approved blog/catalog data. Do not add draft HTML to dist. Resource URLs and internal links are not UTM-tagged.

Indexing configuration backup for the 11 September launch: `/etc/nginx/sites-available/needle-shark.pre-indexing-20260911`. Before reverting, inspect current/previous and this backup; restore only the matching verified version, run `nginx -t` before reload.

## Primary domain migration, 11 September 2026

The owner changed the two A records for needle-shark.ru (@ and www) to 194.87.99.98. The certificate lineage remains named needleshark.ru and now covers all four names. Keep its renewal active: HTTPS redirects also need valid certificates.

Install ops/needle-shark-leads.nginx.conf as /etc/nginx/snippets/needle-shark-leads.conf before using ops/needle-shark.nginx.conf. The API location is shared by the main HTTPS server and redirect aliases so already-open forms can still submit. Page redirects preserve the path and query. Unknown HTTP hosts retain 404. Prepare and test Nginx configuration before reload; the prior configuration is /etc/nginx/sites-available/needle-shark.pre-domain-20260911.

Publication source uses site_utils.ORIGIN for canonical, sitemap, robots and blog metadata. The backend accepts only the four owned HTTPS origins; new consent records name needle-shark.ru. Existing customer records are unchanged. Update the existing Metrika counter's primary/additional domain settings alongside the migration; do not replace the counter or its goals.

## Typography, images and SEO (11 September 2026)

Shared values: `dist/theme.css`; all typography: `dist/typography.css`; shared catalogue/blog navigation: `dist/navigation.css` + `dist/menu.js`. Instructions for future edits: `docs/TYPOGRAPHY.md` and `docs/SEO.md`. Existing page classes and design remain intact.

After adding/replacing an image, first run `python3 ops/optimize-images.py` with a local Python environment containing Pillow. It reads homepage originals and product images from `catalog/products.json`, creates responsive WebP derivatives and records dimensions/hashes in `ops/image-manifest.json`. Embedded XMP is preserved in derivatives, including the IPTC DigitalSourceType marker on generated catalog images. Native generation PNGs remain untouched locally; optimized studio masters live in `dist/catalog-assets/studio-*.webp`. The static site and server do not need Pillow. Originals are retained. For unchanged images do not recompress before each release.

Prepare and check a static change:

```sh
python3 blog/render.py
python3 catalog/render.py
python3 business/render.py --publish
python3 ops/prepare-public.py
python3 ops/check-site.py
node --test ops/test_analytics.mjs
python3 -m unittest discover -s blog -p 'test_*.py'
python3 -m unittest discover -s catalog -p 'test_*.py'
python3 -m unittest discover -s ops -p 'test_*.py'
python3 -m unittest discover -s business -p 'test_*.py'
python3 server/preview.py --port 4173
```

`check-site.py` is local and read-only. It validates page metadata/JSON-LD, sitemap, links, anchors, assets, image hashes and CSS tokens; each public HTML must include exactly one shared counter/analytics script and the current noscript pixel. Browser checks on the five documented widths are still required. The preview now resolves extensionless legal URLs like production. It does not send real submissions unless explicitly started with `--live-api`.

The optimization was installed on 11 September. The expanded three-product catalogue was published on 14 September from commit `2f098b0`, release `20260914T080537Z-8230`; public verification is recorded in `docs/verification/20260914-catalog-publication.json`. Save/push each checked commit before publishing with `ops/deploy.sh`; local browser tests do not count as a production or Google/email delivery check.


## Backend without Google

22 September numeric notification update: pushed code `1e94096`, backend current `20260922T094139Z-1e940964f438`, previous `20260922T071148Z-6eedb20ef75a`. Installed via the existing `--loop` mode with the unchanged private webhook; environment and unit match the backup byte-for-byte. No static deployment, Nginx changes or new migration. Request 15 passed public intake and both delivery queues; see [report](../docs/verification/20260922-notification-order-id.json).

Use `ops/install-server-mail.sh PRIVATE_SMTP_FILE APPROVED_RECIPIENT` for the new PostgreSQL/SMTP backend. `ops/install-leads.sh` now forwards to this installer and requires the same two arguments. Static publication still uses `ops/deploy.sh` independently. Backend code has its own `/opt/needle-shark/current` and `previous`; the service points to current. The installer backs up the actual unit and environment before changing ExecStart, preserves hardening and does not change Nginx. See `server/README.md` for queue semantics, verification and rollback constraints.

For the approved text-only LOOP lead channel, use `bash ops/install-server-mail.sh --loop PRIVATE_LOOP_ENV` (22 September 2026). The file must contain only `LOOP_LEADS_WEBHOOK_URL`, outside Git/public files. The mode preserves all current mail settings and the service unit, adds the independent `lead_loop_deliveries` outbox and runs a separate worker; historical leads are not replayed. Both installer modes now require a committed revision already present in the branch upstream. Monitor/cleanup code and configuration are unchanged. See `server/README.md` for acknowledgements, duplicate limitations and rollback.


Installed final code `6eedb20` in backend `20260922T071148Z-6eedb20ef75a` and static release `20260922T070621Z-52722`; all seven Python modules/222 public files match local hashes. Backend previous is `20260922T070503Z-6bc0fdb34c73`; static previous is `20260918T083901Z-35018`. The first attempt failed because SSH dropped an empty positional argument and `set -u` bypassed the old ERR trap. Service downtime was 07:02:02–07:03:33 UTC (91 seconds), with no `/api/leads` requests in the Nginx log during that interval. The original service was restored. The final installer uses a nonempty placeholder and arms an EXIT recovery trap before stopping the service, disarming only after success; false-command/unbound-variable/success paths are regression-tested. Current/previous pointers, environment and unit are restored on failure; additive tables are retained. Report: `docs/verification/20260922-loop-leads.json`.

## Attachment retention and server alerts — 18 September 2026

Independent maintenance release: `bash ops/install-maintenance.sh APPROVED_MONITOR_RECIPIENT`. Commit and push first. Installation snapshots actual systemd units/configuration, switches `/opt/needle-maintenance/current` atomically, and restores prior unit configuration on failure; `previous` is kept on subsequent updates. It does not publish static files or restart/change the lead backend, Nginx or PostgreSQL. Rollback never restores a database dump over new leads.

`needle-cleanup.timer`: daily 03:20 UTC (06:20 Moscow), up to five minutes jitter; missed runs execute after boot. Deletes only `lead_files` for submissions older than 30 days where all existing delivery jobs are `sent` with a timestamp. No-job, pending, sending and partially delivered files remain. Up to 1,000 files per run in transactions of 100; orders, payload metadata and permanent deduplication fingerprints stay. PostgreSQL autovacuum reuses freed space; immediate reduction in filesystem usage is not guaranteed. No VACUUM FULL or deletions of backups, Google or mailbox copies. Cleanup runs as postgres using local peer authentication; code is root-owned, no new database password.

`needle-monitor.timer`: every five minutes, checks disk (80% used or <1 GiB free), inodes (<15% free), available RAM (<32 MiB), Nginx/API/PostgreSQL/cleanup timer, public HTTPS, a harmless invalid API probe, email jobs older than 15 minutes, and successful cleanup within 36 hours. Alerts on issue-set changes, six-hour reminders, recovery mail; no periodic all-clear mail. SMTP failure does not mark the alert sent and retries next run. Recipient is exclusively `MONITOR_RECIPIENT` in root-only `/etc/needle-shark/monitor.env`; existing authenticated TLS SMTP configuration is reused. Lead recipients are unchanged. State and logs contain no lead content.

Send an explicitly labelled test with the same environment as the monitor and `maintenance.py test-email`; SMTP acceptance is not proof of inbox placement. Local monitoring cannot report total VPS/network/SMTP failure, nor its own stopped timer. Independent monitoring and external backup are deferred in `docs/BACKLOG.md`.

Checks: `python3 -m unittest discover -s ops -p 'test_*.py'`, existing server tests, `CRM_TEST_DSN=... python3 ops/check_maintenance_postgres.py` (disposable schema, synthetic data, no email), `systemd-analyze verify`, actual timer/SQL/HTTPS and SMTP verification. Stop automation with `systemctl disable --now needle-cleanup.timer needle-monitor.timer`; this does not restore expired file bytes.

## Header contacts release — 1 October 2026

Public code `ddfef17397c37082eee94fdb0dd0535ac3688db0` was pushed before `ops/deploy.sh --from-github`. Current static release: `20261001T151439Z-62875`; previous: `20260924T073408Z-14797`. Existing backend and infrastructure unchanged. Visible email/request controls are shared by home, business, catalogue and blog; preserve them in source templates and rebuild. Verification: [20261001-header-contacts.json](../docs/verification/20261001-header-contacts.json).

## Earlier CRM mail routing / LOOP disabled — 19 October 2026

The owner deferred paid REST integration. Production continues to archive website requests in PostgreSQL and deliver email to the existing Bitrix24-connected mailbox. Only that mailbox remains in private `MAIL_RECIPIENTS`; `LOOP_LEADS_WEBHOOK_URL` is absent. Monitor recipient/SMTP settings, database schema, units, Nginx and all code/static release pointers are unchanged.

Configuration backups (root-only): `/opt/needle-shark/backups/20261019-loop-off-061236/leads.env` before disabling LOOP, and `/opt/needle-shark/backups/20261019-crm-mail-only-061856/leads.env` before reducing recipients. The service was stopped during each atomic environment update and restarted; old queues were empty. Rollback must account for the owner's current routing decision: the first backup restores LOOP, both backups restore the earlier four recipients. Do not restore either wholesale as routine maintenance.

Exactly one production form submission was made, order 29. SMTP accepted all four originally configured deliveries once; two copies reached the CRM mailbox and became deals 25/27. The complete message and contact email were checked in CRM. The later one-recipient change is verified in configuration only, not by another submission. Zero LOOP jobs were created. No public page or runtime source changed, so static deployment/SEO/adaptive release checks do not apply. [Evidence and remaining limits](../docs/verification/20261019-bitrix-mail.json).
