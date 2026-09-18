# Needle Shark VPS

- Host: 194.87.99.98, Ubuntu 24.04.
- Primary domain: needle-shark.ru; www.needle-shark.ru, needleshark.ru and www.needleshark.ru redirect to it.
- Nginx config: /etc/nginx/sites-available/needle-shark.
- Public root: /var/www/needle-shark/current (symlink to a release).
- Deployment account: needledeploy (no sudo).
- SSH key stays outside this repo: ~/.ssh/needle_shark_ed25519.
- Publish from the local workspace: `bash ops/deploy.sh`.
- Each publish uploads a fresh release, then atomically switches current; previous points to the last release.
- Firewall allows TCP 22, 80, 443. Existing root access preserved for administration.
- The site serves HTTPS with HTTP redirects. Indexing is explicitly authorized by the owner on 11 September 2026. Form submissions use needle-leads on localhost:8091 via /api/leads.
- DNS A records for @ and www point to 194.87.99.98. Let's Encrypt covers all four names; certbot.timer handles renewal. Primary URL: https://needle-shark.ru/.
- GitHub source backup: https://github.com/mirkenson/needleshark. Save and push agreed changes before deploying the VPS. Existing .openai/hosting.json belongs to the separate Sites preview; VPS deployment does not use it.

Do not commit private keys, credentials or user-submitted data.

Before a static release, run `python3 blog/render.py`, `python3 catalog/render.py`, `python3 business/render.py --publish`, then `python3 ops/prepare-public.py`. The last command finalizes external-anchor UTM parameters and canonical URLs and regenerates robots.txt/sitemap.xml from approved blog/catalog data. Do not add draft HTML to dist. Resource URLs and internal links are not UTM-tagged.

Indexing configuration backup for the 11 September launch: `/etc/nginx/sites-available/needle-shark.pre-indexing-20260911`. Before reverting, inspect current/previous and this backup; restore only the matching verified version, run `nginx -t` before reload.

## Primary domain migration, 11 September 2026

The owner changed the two A records for needle-shark.ru (@ and www) to 194.87.99.98. The certificate lineage remains named needleshark.ru and now covers all four names. Keep its renewal active: HTTPS redirects also need valid certificates.

Install ops/needle-shark-leads.nginx.conf as /etc/nginx/snippets/needle-shark-leads.conf before using ops/needle-shark.nginx.conf. The API location is shared by the main HTTPS server and redirect aliases so already-open forms can still submit. Page redirects preserve the path and query. Unknown HTTP hosts retain 404. Prepare and test Nginx configuration before reload; the prior configuration is /etc/nginx/sites-available/needle-shark.pre-domain-20260911.

Publication source uses site_utils.ORIGIN for canonical, sitemap, robots and blog metadata. The backend accepts only the four owned HTTPS origins; new consent records name needle-shark.ru. Existing customer records are unchanged. Update the existing Metrika counter's primary/additional domain settings alongside the migration; do not replace the counter or its goals.

## Typography, images and SEO (11 September 2026)

Shared values: `dist/theme.css`; all typography: `dist/typography.css`; shared catalogue/blog navigation: `dist/navigation.css` + `dist/menu.js`. Instructions for future edits: `docs/TYPOGRAPHY.md` and `docs/SEO.md`. Existing page classes and design remain intact.

After adding/replacing an image, first run `python3 ops/optimize-images.py` with a local Python environment containing Pillow. It reads homepage originals and product images from `catalog/products.json`, creates responsive WebP derivatives and records dimensions/hashes in `ops/image-manifest.json`. The static site and server do not need Pillow. Originals are retained. For unchanged images do not recompress before each release.

Prepare and check a static change:

```sh
python3 blog/render.py
python3 catalog/render.py
python3 business/render.py --publish
python3 ops/prepare-public.py
python3 ops/check-site.py
python3 -m unittest discover -s blog -p 'test_*.py'
python3 -m unittest discover -s catalog -p 'test_*.py'
python3 -m unittest discover -s ops -p 'test_*.py'
python3 -m unittest discover -s business -p 'test_*.py'
python3 server/preview.py --port 4173
```

`check-site.py` is local and read-only. It validates page metadata/JSON-LD, sitemap, links, anchors, assets, image hashes and CSS tokens. Browser checks on the five documented widths are still required. The preview now resolves extensionless legal URLs like production. It does not send real submissions unless explicitly started with `--live-api`.

The optimization was installed on 11 September. The expanded three-product catalogue was published on 14 September from commit `2f098b0`, release `20260914T080537Z-8230`; public verification is recorded in `docs/verification/20260914-catalog-publication.json`. Save/push each checked commit before publishing with `ops/deploy.sh`; local browser tests do not count as a production or Google/email delivery check.


## Backend without Google

Use `ops/install-server-mail.sh PRIVATE_SMTP_FILE APPROVED_RECIPIENT` for the new PostgreSQL/SMTP backend. `ops/install-leads.sh` now forwards to this installer and requires the same two arguments. Static publication still uses `ops/deploy.sh` independently. Backend code has its own `/opt/needle-shark/current` and `previous`; the service points to current. The installer backs up the actual unit and environment before changing ExecStart, preserves hardening and does not change Nginx. See `server/README.md` for queue semantics, verification and rollback constraints.


## Attachment retention and server alerts — 18 September 2026

Independent maintenance release: `bash ops/install-maintenance.sh APPROVED_MONITOR_RECIPIENT`. Commit and push first. Installation snapshots actual systemd units/configuration, switches `/opt/needle-maintenance/current` atomically, and restores prior unit configuration on failure; `previous` is kept on subsequent updates. It does not publish static files or restart/change the lead backend, Nginx or PostgreSQL. Rollback never restores a database dump over new leads.

`needle-cleanup.timer`: daily 03:20 UTC (06:20 Moscow), up to five minutes jitter; missed runs execute after boot. Deletes only `lead_files` for submissions older than 30 days where all existing delivery jobs are `sent` with a timestamp. No-job, pending, sending and partially delivered files remain. Up to 1,000 files per run in transactions of 100; orders, payload metadata and permanent deduplication fingerprints stay. PostgreSQL autovacuum reuses freed space; immediate reduction in filesystem usage is not guaranteed. No VACUUM FULL or deletions of backups, Google or mailbox copies. Cleanup runs as postgres using local peer authentication; code is root-owned, no new database password.

`needle-monitor.timer`: every five minutes, checks disk (80% used or <1 GiB free), inodes (<15% free), available RAM (<32 MiB), Nginx/API/PostgreSQL/cleanup timer, public HTTPS, a harmless invalid API probe, email jobs older than 15 minutes, and successful cleanup within 36 hours. Alerts on issue-set changes, six-hour reminders, recovery mail; no periodic all-clear mail. SMTP failure does not mark the alert sent and retries next run. Recipient is exclusively `MONITOR_RECIPIENT` in root-only `/etc/needle-shark/monitor.env`; existing authenticated TLS SMTP configuration is reused. Lead recipients are unchanged. State and logs contain no lead content.

Send an explicitly labelled test with the same environment as the monitor and `maintenance.py test-email`; SMTP acceptance is not proof of inbox placement. Local monitoring cannot report total VPS/network/SMTP failure, nor its own stopped timer. Independent monitoring and external backup are deferred in `docs/BACKLOG.md`.

Checks: `python3 -m unittest discover -s ops -p 'test_*.py'`, existing server tests, `CRM_TEST_DSN=... python3 ops/check_maintenance_postgres.py` (disposable schema, synthetic data, no email), `systemd-analyze verify`, actual timer/SQL/HTTPS and SMTP verification. Stop automation with `systemctl disable --now needle-cleanup.timer needle-monitor.timer`; this does not restore expired file bytes.
