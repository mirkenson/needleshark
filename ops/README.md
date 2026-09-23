# Needle Shark VPS

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
