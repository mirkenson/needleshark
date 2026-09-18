# Needle Shark VPS

- Host: 194.87.99.98, Ubuntu 24.04.
- Primary domain: needle-shark.ru; www.needle-shark.ru, needleshark.ru, www.needleshark.ru, neesha.ru and www.neesha.ru redirect to it.
- Nginx config: /etc/nginx/sites-available/needle-shark.
- Public root: /var/www/needle-shark/current (symlink to a release).
- Deployment account: needledeploy (no sudo).
- SSH key stays outside this repo: ~/.ssh/needle_shark_ed25519.
- Publish from the local workspace: `bash ops/deploy.sh`.
- Each publish uploads a fresh release, then atomically switches current; previous points to the last release.
- Firewall allows TCP 22, 80, 443. Existing root access preserved for administration.
- The site serves HTTPS with HTTP redirects. Indexing is explicitly authorized by the owner on 11 September 2026. Form submissions use needle-leads on localhost:8091 via /api/leads.
- DNS A records for @ and www on all three domains point to 194.87.99.98. Let's Encrypt covers all six names through the needleshark.ru and neesha.ru certificate lineages; certbot.timer handles renewal. Primary URL: https://needle-shark.ru/.
- GitHub source backup: https://github.com/mirkenson/needleshark. Save and push agreed changes before deploying the VPS. Existing .openai/hosting.json belongs to the separate Sites preview; VPS deployment does not use it.

Do not commit private keys, credentials or user-submitted data.

Before a static release, run `python3 blog/render.py`, `python3 catalog/render.py`, then `python3 ops/prepare-public.py`. The last command finalizes external-anchor UTM parameters and canonical URLs and regenerates robots.txt/sitemap.xml from approved blog/catalog data. Do not add draft HTML to dist. Resource URLs and internal links are not UTM-tagged.

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
python3 ops/prepare-public.py
python3 ops/check-site.py
python3 -m unittest discover -s blog -p 'test_*.py'
python3 -m unittest discover -s catalog -p 'test_*.py'
python3 -m unittest discover -s ops -p 'test_*.py'
python3 server/preview.py --port 4173
```

`check-site.py` is local and read-only. It validates page metadata/JSON-LD, sitemap, links, anchors, assets, image hashes and CSS tokens. Browser checks on the five documented widths are still required. The preview now resolves extensionless legal URLs like production. It does not send real submissions unless explicitly started with `--live-api`.

The optimization was installed on 11 September. The expanded three-product catalogue was published on 14 September from commit `2f098b0`, release `20260914T080537Z-8230`; public verification is recorded in `docs/verification/20260914-catalog-publication.json`. Save/push each checked commit before publishing with `ops/deploy.sh`; local browser tests do not count as a production or Google/email delivery check.

## neesha.ru redirects, 18 September 2026

The owner pointed neesha.ru and www.neesha.ru to 194.87.99.98. Both HTTP and HTTPS now return 301 to `https://needle-shark.ru$request_uri`, preserving the path and query. These two aliases serve redirects only, including `/api/leads`; the existing four backend origins and the previous aliases' API behavior are unchanged. The main website, canonical URLs, analytics configuration, and static release were not changed.

`ops/needle-shark.nginx.conf` contains a separate server block for the two new names. Its certificate lineage is `/etc/letsencrypt/live/neesha.ru/`, valid until 17 December 2026 when first issued. It was obtained with `certbot certonly --nginx --non-interactive --cert-name neesha.ru -d neesha.ru -d www.neesha.ru --deploy-hook 'nginx -t && systemctl reload nginx'`. The saved renewal hook tests and reloads Nginx after successful renewal. `certbot renew --cert-name neesha.ru --dry-run --run-deploy-hooks --no-random-sleep-on-renew` passed. Keep the redirect inside `location /` so the Nginx authenticator can temporarily add an HTTP-01 challenge location.

The pre-change Nginx backup is `/root/needle-shark-backups/neesha-20260918T055236Z/nginx/`. The candidate was syntax-checked on the VPS, committed as `0a89b9e`, and pushed before atomic installation of the configuration and a successful `nginx -t` / reload. This was a server configuration change: `ops/deploy.sh` was not run because no static release was published. Before any rollback, compare the live configuration with this snapshot to avoid overwriting subsequent changes; test before reloading. The two pre-existing static release links stayed unchanged.

REG.RU remains authoritative with ns1.reg.ru/ns2.reg.ru. The MX remains `10 emx.mail.ru.`; no DNS or mailbox settings were modified by the server installation. Mail delivery was not tested. Public verification is recorded in `docs/verification/20260918-neesha-redirect.json`.
